import graphene
from graphene import ObjectType
from graphene_django_extras import DjangoInputObjectType


def create_mutation_classes_for_describer(adapter, describer):
    mutation_classes = []
    for action in describer.get_actions():
        if action.read_only:
            continue
        mutation_classes.append(create_mutation_class(adapter, action, has_model=action.has_model))
    return mutation_classes


def create_mutate_method(action, has_model=True):
    """
    Creates the mutate method based on fn. Adds permissions as well.
    """

    @classmethod
    def mutate(cls, root, info, *args, **kwargs):
        obj = None
        if has_model and "id" in kwargs["data"]:
            obj = action.get_fetch_fn()(info.context, kwargs["data"]["id"])

        for permission_class in action.permissions:
            pc = permission_class(info.context, obj=obj, data=kwargs["data"])
            if not pc.has_permission():
                raise PermissionError(pc.error_message())

        if obj is not None:
            return action.get_exec_fn()(info.context, obj, kwargs["data"])
        return action.get_exec_fn()(info.context, kwargs["data"])

    return mutate


def create_return_fields(adapter, action):
    ret = {}
    for name, type in action.get_return_fields().items():
        ret[name] = type.convert(adapter)
    return ret


def create_mutation_class(adapter, action, has_model=True):
    if has_model:
        input_meta = type(
            "Meta",
            (object,),
            {
                "model": action._describer.model,
                "only_fields": action.determine_fields(),
                "input_for": action._name,
            }
        )

        input_class = type(
            "{}{}Input".format(action._describer.model.__name__, action._name.capitalize()),
            (DjangoInputObjectType,),
            {
                "Meta": input_meta
            }
        )

        # add extra fields to input type
        for name, return_type in action.extra_fields.items():
            if name in input_class._meta.input_fields:
                raise ValueError("Duplicate field: `{}`".format(name))
            input_class._meta.input_fields[name] = return_type.convert(adapter, input=True)
    else:
        input_class = action.input_type.convert(adapter, input=True)

    arguments_class = type(
        "Arguments",
        (object,),
        {
            "data": graphene.Argument(input_class, required=True)
        }
    )

    return_fields = create_return_fields(adapter, action)

    mutation_class = type(
        "{}{}Mutation".format(action._describer.model.__name__, action._name.capitalize()),
        (graphene.Mutation,),
        {
            **return_fields,
            "Arguments": arguments_class,
            "mutate": create_mutate_method(action, has_model=has_model),
        }
    )

    mutation_class._name = action._name.capitalize()

    return mutation_class


def create_global_mutation_class(mutation_classes):
    attrs = {}
    for model, mutations in mutation_classes.items():
        for mutation in mutations:
            attrs["{}_{}".format(model.__name__, mutation._name)] = mutation.Field()

    mutation_class = type(
        "Mutation",
        (ObjectType,),
        attrs
    )

    return mutation_class
