import graphene
from graphene_django_extras import DjangoInputObjectType

from utils import model_singular_name


def create_model_input_class(describer, mode):
    meta = type(
        "Meta",
        (object,),
        {
            "model": describer.model,
            "only_fields": describer.determine_fields(mode)
        }
    )

    input_class = type(
        "{}{}InputType".format(describer.model.__name__, mode.name),
        (DjangoInputObjectType,),
        {
            "Meta": meta,
            "get_mode": lambda: input_class.mode
        }
    )

    input_class.mode = mode

    return input_class


def create_model_mutation_class(describer, input_class, type_classes):
    arguments = type(
        "Arguments",
        (object,),
        {
            "data": graphene.Argument(input_class)
        }
    )

    meta = type(
        "Meta",
        (object,),
        {
            "description": "{} a {}".format(input_class.get_mode().name, describer.model.__name__)
        }
    )

    mutation_class = type(
        "{}{}Mutation".format(describer.model.__name__, input_class.get_mode().name),
        (graphene.Mutation,),
        {
            model_singular_name(describer.model): graphene.Field(type_classes[describer.model], required=False),
            "Arguments": arguments,
            "Meta": meta,
            "mutate": create_mutate_method(),
        }
    )

    return mutation_class


def create_mutate_method():
    @classmethod
    def mutate(cls, root, info, *args, **kwargs):
        print(cls, root, info, *args, **kwargs)
    return mutate
