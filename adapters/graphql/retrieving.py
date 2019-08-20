import django.db.models
import graphene
from graphene_django_extras import DjangoObjectType, LimitOffsetGraphqlPagination, DjangoListObjectType
from graphene_django_extras.settings import graphql_api_settings

from adapters.graphql.converter import convert_local_fields
from adapters.graphql.fields import DjangoObjectPermissionsField, DjangoNestableListObjectPermissionsField
from datatypes import NullType, String, Integer, Float, Boolean
from describers import Mode
from utils import model_singular_name, model_plural_name, field_names, get_all_model_fields


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
            "only_fields": describer.determine_fields(Mode.DETAIL),
        }
    )

    type_class = type(
        "{}Type".format(describer.model.__name__),
        (DjangoObjectType,),
        {
            "Meta": type_meta,
            "get_list_type": lambda: type_list_class,
            **convert_local_fields(describer.model, describer.determine_fields(Mode.DETAIL))
        }
    )

    type_list_meta = type(
        "Meta",
        (object,),
        {
            "model": describer.model,
            "pagination": LimitOffsetGraphqlPagination(
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

    for field_name in describer.determine_fields(Mode.LIST):

        # get the filters for each field based on their types
        field_type = _reverse_field_map.get(describer.model._meta.get_field(field_name).__class__, NullType)

        # add the filters to the output
        filter_fields[field_name] = field_type.filters()

    return filter_fields


def create_query_class(describer, type_classes):
    """
    Creates a Query class for a type, featuring listing and detail methods.
    """
    model_singular = model_singular_name(describer.model)
    model_plural = model_plural_name(describer.model)

    attrs = {}

    if describer.enable_list:
        attrs[model_plural] = DjangoNestableListObjectPermissionsField(
            type_classes[describer.model].get_list_type(), description="Multiple {} query.".format(model_plural))

    if describer.enable_detail:
        attrs[model_singular] = DjangoObjectPermissionsField(type_classes[describer.model],
                                                             description="Single {} query.".format(model_singular))

    query_class = type(
        "Query",
        (Query,),
        attrs,
    )

    return query_class


def add_permissions_to_query_class(describer, query_class):
    """
    Adds permissions to the given Query class.
    """
    if describer.enable_list and describer.get_permissions(Mode.LIST):
        field_name = "resolve_{}".format(model_plural_name(describer.model))
        setattr(query_class,
                field_name,
                create_permissions_check_method(permission_classes=describer.get_permissions(Mode.LIST)))

    if describer.enable_detail and describer.get_permissions(Mode.DETAIL):
        field_name = "resolve_{}".format(model_singular_name(describer.model))
        setattr(query_class,
                field_name,
                create_permissions_check_method(permission_classes=describer.get_permissions(Mode.DETAIL)))


def add_permissions_to_type_class(describer, type_class):
    """
    Adds permissions to the given DjangoObjectType class.
    """
    for field_name, permission_classes in describer.get_field_permissions().items():
        setattr(type_class,
                "resolve_{}".format(field_name),
                create_permissions_check_method(field_name, permission_classes))


def add_extra_fields_to_type_class(adapter, describer, type_class):
    """
    Adds extra fields to the given DjangoObjectType class. Ensures no base fields get overwritten.
    """
    existing_fields = field_names(get_all_model_fields(describer.model))

    for field_name, return_type in describer.get_extra_fields(Mode.DETAIL).items():
        if field_name in existing_fields:
            raise ValueError("This field already exists.")

        type_class._meta.fields[field_name] = return_type.convert(adapter, property_name=field_name)


def create_global_query_class(query_classes):
    return type("Query", query_classes.values() + (graphene.ObjectType,), {})


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
