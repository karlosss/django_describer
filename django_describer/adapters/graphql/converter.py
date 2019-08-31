from collections import OrderedDict
from copy import deepcopy

import graphene
from django.contrib.contenttypes.fields import GenericRel
import django.db.models
from graphene_django.fields import DjangoListField
from graphene_django_extras.converter import convert_django_field, convert_django_field_with_choices
from graphene_django_extras.registry import get_global_registry
from graphene_django_extras.utils import is_required

from .fields import DjangoNestableListObjectPermissionsField
from ...utils import get_local_fields


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
                return DjangoNestableListObjectPermissionsField(
                    _type,
                    required=is_required(field) and input_flag == "create",
                    filterset_class=_type._meta.filterset_class,
                )
            else:
                return DjangoListField(
                    _type, required=is_required(field) and input_flag == "create"
                )

    return graphene.Dynamic(dynamic_type)


def convert_local_fields(model, convertable_fields):
    """
    Converts user-specified model fields as if they were nullable.
    Also transforms ID to integer field, since it is (usually) an integer.
    """

    # define how each field shall be converted
    field_conversions = {
        django.db.models.fields.AutoField: django.db.models.IntegerField
    }

    fields = [[name, deepcopy(field)] for name, field in get_local_fields(model)]

    for i in range(len(fields)):
        # change a field's type if necessary
        new_field = field_conversions.get(fields[i][1].__class__, None)
        if new_field is not None:
            fields[i][1] = new_field()

        # set all fields as nullable
        fields[i][1].null = True

    # convert the fields
    ret = OrderedDict()

    for name, field in fields:
        if name not in convertable_fields:
            continue
        converted = convert_django_field_with_choices(field, get_global_registry())
        ret[name] = converted

    return ret