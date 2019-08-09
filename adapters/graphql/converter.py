import graphene
from django.contrib.contenttypes.fields import GenericRel
import django.db.models
from graphene import Int
from graphene_django.fields import DjangoListField
from graphene_django_extras.converter import convert_django_field
from graphene_django_extras.utils import is_required

from adapters.graphql.fields import DjangoNestableListObjectField


@convert_django_field.register(django.db.models.AutoField)
def convert_field_to_id(field, registry=None, input_flag=None, nested_field=False):
    if input_flag:
        return Int(
            description=field.help_text or "Django object unique identification field",
            required=input_flag == "update",
        )
    return Int(
        description=field.help_text or "Django object unique identification field",
        required=not field.null,
    )


@convert_django_field.register(GenericRel)
@convert_django_field.register(django.db.models.ManyToManyRel)
@convert_django_field.register(django.db.models.ManyToOneRel)
def convert_many_rel_to_djangomodel(
    field, registry=None, input_flag=None, nested_field=False
):
    """
    An override of the original convert function. Takes into account improved fields with ordering and pagination.
    """

    model = field.related_model

    def dynamic_type():
        if input_flag and not nested_field:
            return DjangoListField(graphene.ID)
        else:
            _type = registry.get_type_for_model(model, for_input=input_flag)

            # get list type of the object if it has one
            if hasattr(_type, "get_list_type"):
                _type = _type.get_list_type()

            if not _type:
                return
            elif input_flag and nested_field:
                return DjangoListField(_type)
            elif _type._meta.filter_fields or _type._meta.filterset_class:
                # return nested relations as a field with pagination
                return DjangoNestableListObjectField(
                    _type,
                    required=is_required(field) and input_flag == "create",
                    filterset_class=_type._meta.filterset_class,
                )
            else:
                return DjangoListField(
                    _type, required=is_required(field) and input_flag == "create"
                )

    return graphene.Dynamic(dynamic_type)
