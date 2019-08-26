import graphene
from graphene import ObjectType, Boolean
from graphene_django_extras import DjangoInputObjectType

from datatypes import get_instantiated_type
from utils import get_object_or_none


def create_mutation_classes_for_describer(adapter, describer):
    mutation_classes = []
    for action in describer.get_actions():
        if action.read_only:
            continue
        mutation_classes.append(create_mutation_class(adapter, action))
    return mutation_classes


def create_mutate_method(action):
    """
    Creates the mutate method based on fn. Adds permissions as well.
    """
    fn = action.get_fn()
    @classmethod
    def mutate(cls, root, info, *args, **kwargs):
        obj = None
        if "id" in kwargs["data"]:
            obj = get_object_or_none(action._describer.model, kwargs["data"]["id"])

        for permission_class in action.get_permissions():
            pc = permission_class(info.context, obj=obj, data=kwargs["data"])
            if not pc.has_permission():
                raise PermissionError(pc.error_message())

        return fn(info.context, obj, kwargs["data"])

    return mutate


def create_return_params(adapter, action):
    ret = {}
    for name, type in action.get_return_params().items():
        ret[name] = get_instantiated_type(type).convert(adapter)
    return ret


def create_mutation_class(adapter, action):
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
    for name, return_type in action.get_extra_fields().items():
        if name in input_class._meta.input_fields:
            raise ValueError("Duplicate field: `{}`".format(name))
        input_class._meta.input_fields[name] = return_type.convert(adapter, input=True)

    arguments_class = type(
        "Arguments",
        (object,),
        {
            "data": graphene.Argument(input_class)
        }
    )

    return_params = create_return_params(adapter, action)

    mutation_class = type(
        "{}{}Mutation".format(action._describer.model.__name__, action._name.capitalize()),
        (graphene.Mutation,),
        {
            **return_params,
            "Arguments": arguments_class,
            "mutate": create_mutate_method(action),
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
