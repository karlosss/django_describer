from inspect import isclass

import graphene
from django.db.models import ForeignKey
from graphene import ObjectType, InputField, NonNull
from graphene.types.utils import get_field_as
from graphene_django_extras import DjangoInputObjectType

from django_describer.adapters.utils import register_action_name
from django_describer.datatypes import get_instantiated_type
from django_describer.utils import to_camelcase, in_kwargs_and_true, in_kwargs_and_false


def create_mutation_classes(adapter, actions):
    mutation_classes = []
    for action in actions:
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

        for permission_class in action.get_permissions():
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
        ret[name] = get_instantiated_type(type).convert(adapter)
    return ret


def update_foreign_key_fields(action, input_class):
    updated_fields = {}
    deleted_fields = set()
    for name, field in input_class._meta.fields.items():
        django_field = action._describer.model._meta.get_field(name)
        if isinstance(django_field, ForeignKey):
            updated_fields["{}_id".format(name)] = field
            deleted_fields.add(name)

    for name in deleted_fields:
        del input_class._meta.fields[name]

    for name, field in updated_fields.items():
        input_class._meta.fields[name] = field


def create_mutation_class(adapter, action, has_model=True):
    if has_model:
        input_meta = type(
            "Meta",
            (object,),
            {
                "model": action._describer.model,
                "only_fields": action.determine_fields(),
                "input_for": action.convert(adapter, input_flag=True),
            }
        )

        input_class = type(
            "{}{}Input".format(action._describer.model.__name__, action._name.capitalize()),
            (DjangoInputObjectType,),
            {
                "Meta": input_meta
            }
        )

        # consider field_kwargs
        for field, kwargs in action.field_kwargs.items():
            if field not in input_class._meta.input_fields:
                raise ValueError("Unknown field: `{}`".format(field))

            old_type = input_class._meta.input_fields[field].type

            if isinstance(old_type, NonNull):
                was_required = True
                new_type = old_type.of_type
            elif isclass(old_type):
                was_required = False
                new_type = NonNull(old_type)
            else:
                if in_kwargs_and_true(kwargs, "required"):
                    was_required = False
                    new_type = NonNull(graphene.ID)
                elif in_kwargs_and_false(kwargs, "required"):
                    was_required = True
                    new_type = graphene.ID
                else:
                    raise ValueError("Invalid field kwargs.")

            if (was_required and in_kwargs_and_false(kwargs, "required")) or (
                    not was_required and in_kwargs_and_true(kwargs, "required")):
                input_class._meta.input_fields[field] = InputField(new_type)

        # append _id to foreign key names
        update_foreign_key_fields(action, input_class)

        # add extra fields to input type
        for name, return_type in action.extra_fields.items():
            if name in input_class._meta.input_fields:
                raise ValueError("Duplicate field: `{}`".format(name))
            input_class._meta.input_fields[name] = get_instantiated_type(return_type).convert(adapter, input_field=True)
        input_type = input_class(required=True)
    else:
        input_type = get_instantiated_type(action.input_type).convert(adapter, input=True)

    arguments_class = type(
        "Arguments",
        (object,),
        {
            "data": input_type
        }
    )

    return_fields = create_return_fields(adapter, action)

    mutation_class = type(
        "{}Mutation".format(to_camelcase(action.get_name())),
        (graphene.Mutation,),
        {
            **return_fields,
            "Arguments": arguments_class,
            "mutate": create_mutate_method(action, has_model=has_model),
        }
    )

    name = action.get_name()
    register_action_name(adapter, name)
    mutation_class._name = name

    return mutation_class


def create_global_mutation_class(mutation_classes, non_model_mutation_classes):
    attrs = {}
    for model, mutations in mutation_classes.items():
        for mutation in mutations:
            attrs[mutation._name] = mutation.Field()

    for mutation in non_model_mutation_classes:
        attrs[mutation._name] = mutation.Field()

    mutation_class = type(
        "Mutation",
        (ObjectType,),
        attrs
    )

    return mutation_class
