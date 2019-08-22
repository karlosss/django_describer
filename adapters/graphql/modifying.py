import graphene
from graphene import ObjectType
from graphene_django_extras import DjangoInputObjectType
from graphene_django_extras.registry import get_global_registry

from actions import CreateAction


def create_mutation_classes_for_describer(describer):
    mutation_classes = []
    for action in describer.get_actions():
        if action.read_only:
            continue
        mutation_classes.append(create_mutation_class(action))
    return mutation_classes


def create_default_fn(action_class, model):
    if action_class == CreateAction:
        def fn(request, data):
            instance = model(**data)
            instance.save()
            return instance
        return fn

    raise ValueError("{} has no default fn, you need to provide one.".format(action_class))


def create_mutate_method(action):
    fn = action.fn or create_default_fn(action.__class__, action._describer.model)
    @classmethod
    def mutate(cls, root, info, *args, **kwargs):
        object = fn(info.context, kwargs["data"])

        return {
            "object": object,
            "ok": True
        }

    return mutate


def create_mutation_class(action):
    input_meta = type(
        "Meta",
        (object,),
        {
            "model": action._describer.model,
            "only_fields": action.determine_fields(),
        }
    )

    input_class = type(
        "{}{}Input".format(action._describer.model.__name__, action._name.capitalize()),
        (DjangoInputObjectType,),
        {
            "Meta": input_meta
        }
    )

    arguments_class = type(
        "Arguments",
        (object,),
        {
            "data": graphene.Argument(input_class)
        }
    )

    mutation_class = type(
        "{}{}Mutation".format(action._describer.model.__name__, action._name.capitalize()),
        (graphene.Mutation,),
        {
            "object": graphene.Field(get_global_registry().get_type_for_model(action._describer.model), required=False),
            "ok": graphene.Field(graphene.Boolean, required=False),
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
