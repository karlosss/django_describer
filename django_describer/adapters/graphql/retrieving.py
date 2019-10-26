import django.db.models
import graphene
from graphene_django_extras import DjangoObjectType, DjangoListObjectType
from graphene_django_extras.settings import graphql_api_settings

from django_describer.adapters.utils import register_action_name
from ...datatypes import String, Integer, Float, Boolean, NullType, get_instantiated_type
from .converter import convert_local_fields
from .pagination import LimitOffsetOrderingGraphqlPagination
from ...utils import field_names, get_all_model_fields


# mapping of alien types to django_describer ones
_reverse_field_map = {
    # Django types
    django.db.models.fields.CharField: String,
    django.db.models.fields.TextField: String,
    django.db.models.fields.IntegerField: Integer,
    django.db.models.fields.FloatField: Float,
    django.db.models.fields.BooleanField: Boolean,
    django.db.models.fields.AutoField: Integer,
}


class Query:
    """
    A type for local graphene Query classes. Intentionally blank, serves only for type checking.
    """


def create_type_class(describer):
    """
    Creates a DjangoObjectType and a DjangoListObjectType for a model, and links them together.
    Must be in this order!!!
    """
    type_meta = type(
        "Meta",
        (object,),
        {
            "model": describer.model,
            "filter_fields": create_filter_fields(describer),
            "only_fields": describer.get_fields(),
        }
    )

    type_class = type(
        "{}Type".format(describer.model.__name__),
        (DjangoObjectType,),
        {
            "Meta": type_meta,
            "get_list_type": lambda: type_list_class,
            **convert_local_fields(describer.model, describer.get_fields())
        }
    )

    type_list_meta = type(
        "Meta",
        (object,),
        {
            "model": describer.model,
            "pagination": LimitOffsetOrderingGraphqlPagination(
                default_limit=describer.default_page_size or graphql_api_settings.DEFAULT_PAGE_SIZE,
                max_limit=describer.max_page_size or graphql_api_settings.DEFAULT_PAGE_SIZE
            ),
        }
    )

    type_list_class = type(
        "{}ListType".format(describer.model.__name__),
        (DjangoListObjectType,),
        {
            "Meta": type_list_meta,
        }
    )

    return type_class


def create_filter_fields(describer):
    """
    Creates dictionary of filters based on field types.
    """
    filter_fields = {}
    field_names = (f.name for f in describer.model._meta.fields)

    for field_name in field_names:
        if isinstance(describer.model._meta.get_field(field_name), django.db.models.ForeignKey):
            # handle foreign keys
            filter_fields[field_name + "_id"] = Integer.filters()
        else:
            # get the filters for each field based on their types (NullType stands for unknown field type)
            field_type = _reverse_field_map.get(describer.model._meta.get_field(field_name).__class__, NullType)

            # add the filters to the output
            filter_fields[field_name] = field_type.filters()

    # add custom filters
    for field_name, field_type in describer.extra_filters.items():
        filter_fields[field_name] = field_type.filters()

    return filter_fields


def create_query_class(adapter, actions):
    """
    Creates a Query class, featuring listing and detail methods.
    """

    attrs = {}

    for action in actions:
        if not action.read_only:
            continue

        name = action.get_name()
        register_action_name(adapter, name)

        attrs[name] = action.convert(adapter)

        if action.get_permissions():
            attrs["resolve_{}".format(name)] = create_permissions_check_method(
                permission_classes=action.get_permissions())

    query_class = type(
        "Query",
        (Query,),
        attrs,
    )

    return query_class


def add_permissions_to_type_class(describer, type_class):
    """
    Adds permissions to the given DjangoObjectType class.
    """
    for field in describer.get_fields():
        permissions = None

        if field in describer.get_field_permissions():
            permissions = describer.get_field_permissions()[field]
        elif describer.get_default_field_permissions():
            permissions = describer.get_default_field_permissions()

        if permissions:
            setattr(type_class,
                    "resolve_{}".format(field),
                    create_permissions_check_method(field, permissions))


def add_extra_fields_to_type_class(adapter, describer, type_class):
    """
    Adds extra fields to the given DjangoObjectType class. Ensures no base fields get overwritten.
    """
    existing_fields = field_names(get_all_model_fields(describer.model))

    for field_name, return_type in describer.get_extra_fields().items():
        if field_name in existing_fields:
            raise ValueError("This field already exists.")

        type_class._meta.fields[field_name] = get_instantiated_type(return_type).convert(
            adapter, property_name=field_name)


def create_global_query_class(query_classes, non_model_query_class):
    return type("Query", query_classes.values() + (non_model_query_class,) + (graphene.ObjectType,), {})


def create_permissions_check_method(field_name=None, permission_classes=()):
    """
    Generator of methods to check permissions for both ListFields and Fields.
    """
    def method(root, info, results=None, **kwargs):
        for permission_class in permission_classes:
            pc = permission_class(info.context, obj=root, qs=results)
            if not pc.has_permission():
                raise PermissionError(pc.error_message())

        # return only for non-list Fields
        if field_name and hasattr(root, field_name):
            return getattr(root, field_name)

    # necessary flag for ListFields
    method.permissions_check = True
    return method
