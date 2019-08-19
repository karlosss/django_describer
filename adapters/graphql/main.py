import django
import graphene
from django.db.models import Model
from graphene.types.utils import get_field_as
from graphene_django_extras import DjangoObjectType, LimitOffsetGraphqlPagination, DjangoListObjectType
from graphene_django.views import GraphQLView
from graphene_django_extras.settings import graphql_api_settings

from adapters.base import Adapter
from adapters.graphql.converter import convert_local_fields
from adapters.graphql.fields import DjangoNestableListObjectPermissionsField, \
    DjangoObjectPermissionsField
from datatypes import String, Integer, Float, Boolean, NullType
from describers import get_describers
from registry import Registry
from utils import model_singular_name, model_plural_name, field_names, get_all_model_fields


class GraphQL(Adapter):
    _reverse_field_map = {
        # Django types
        django.db.models.fields.CharField: String,
        django.db.models.fields.TextField: String,
        django.db.models.fields.IntegerField: Integer,
        django.db.models.fields.FloatField: Float,
        django.db.models.fields.BooleanField: Boolean,
        django.db.models.fields.AutoField: Integer,
    }

    def _convert_primitive_type(self, type, **kwargs):
        """
        A helper for converting primitive types to Graphene.
        """

        # for filters, do not create a graphene field, return just the argument
        if "arg" in kwargs and kwargs["arg"]:
            return type

        return get_field_as(type, _as=graphene.Field)

    def string_type(self, type, **kwargs):
        return self._convert_primitive_type(graphene.types.String(), **kwargs)

    def integer_type(self, type, **kwargs):
        return self._convert_primitive_type(graphene.types.Int(), **kwargs)

    def float_type(self, type, **kwargs):
        return self._convert_primitive_type(graphene.types.Float(), **kwargs)

    def id_type(self, type, **kwargs):
        return self._convert_primitive_type(graphene.types.ID(), **kwargs)

    def boolean_type(self, type, **kwargs):
        return self._convert_primitive_type(graphene.types.Boolean(), **kwargs)

    def queryset_type(self, type, **kwargs):
        property_name = kwargs.get("property_name", None)
        return graphene.Dynamic(lambda: DjangoNestableListObjectPermissionsField(type.type.convert(self, list=True),
                                                                                 property_name=property_name))

    def model_type(self, type, **kwargs):
        if "list" in kwargs and kwargs["list"]:
            return self.type_classes[type.model].get_list_type()

        return graphene.Dynamic(lambda: graphene.Field(self.type_classes[type.model]))

    class _Query:
        """
        A type for local graphene Query classes. Intentionally blank, serves only for type checking.
        """

    def _create_type_class(self, describer):
        """
        Creates a DjangoObjectType and a DjangoListObjectType for a model, and links them together.
        Must be in this order!!!
        """
        type_meta = type(
            "Meta",
            (object,),
            {
                "model": describer.model,
                "filter_fields": self._create_filter_fields(describer),
                "only_fields": describer.determine_fields(),
            }
        )

        type_class = type(
            "{}Type".format(describer.model.__name__),
            (DjangoObjectType,),
            {
                "Meta": type_meta,
                "get_list_type": lambda: type_list_class,
                **convert_local_fields(describer.model, describer.determine_fields())
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

    def _create_filter_fields(self, describer):
        """
        Creates dictionary of filters based on field types.
        """
        filter_fields = {}

        for field_name in describer.determine_fields():

            # get the filters for each field based on their types
            field_type = self._reverse_field_map.get(describer.model._meta.get_field(field_name).__class__, NullType)

            # add the filters to the output
            filter_fields[field_name] = list(field_type.filters())

        return filter_fields

    def _create_permissions_check_method(self, field_name=None, permission_classes=()):
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

    def _create_query_class(self, describer, type_classes):
        model_singular = model_singular_name(describer.model)
        model_plural = model_plural_name(describer.model)

        query_class = type(
            "Query",
            (GraphQL._Query,),
            {
                model_singular: DjangoObjectPermissionsField(type_classes[describer.model],
                                                             description="Single {} query.".format(model_singular)),

                model_plural: DjangoNestableListObjectPermissionsField(
                    type_classes[describer.model].get_list_type(),
                    description="Multiple {} query.".format(model_plural)),
            }
        )

        return query_class

    def _add_permissions_to_query_class(self, describer, query_class):
        if describer.listing_permissions:
            field_name = "resolve_{}".format(model_plural_name(describer.model))
            setattr(query_class,
                    field_name,
                    self._create_permissions_check_method(permission_classes=describer.get_listing_permissions()))

        if describer.detail_permissions:
            field_name = "resolve_{}".format(model_singular_name(describer.model))
            setattr(query_class,
                    field_name,
                    self._create_permissions_check_method(permission_classes=describer.get_detail_permissions()))

    def _add_permissions_to_type_class(self, describer, type_class):
        for field_name, permission_classes in describer.get_field_permissions().items():
            setattr(type_class,
                    "resolve_{}".format(field_name),
                    self._create_permissions_check_method(field_name, permission_classes))

    def _add_extra_fields_to_type_class(self, describer, type_class):
        existing_fields = field_names(get_all_model_fields(describer.model))

        for field_name, return_type in describer.get_extra_fields().items():
            if field_name in existing_fields:
                raise ValueError("This field already exists.")

            type_class._meta.fields[field_name] = return_type.convert(self, property_name=field_name)

    def _create_global_query_class(self, query_classes):
        return type("Query", query_classes.values() + (graphene.ObjectType,), {})

    def generate(self):
        describers = get_describers()

        self.type_classes = Registry(key_type=Model, value_type=DjangoObjectType)
        self.query_classes = Registry(key_type=Model, value_type=GraphQL._Query)

        for describer in describers:
            # create a DjangoObjectType for the model
            self.type_classes[describer.model] = self._create_type_class(describer)

            # add extra fields to each DjangoObjectType class
            self._add_extra_fields_to_type_class(describer, self.type_classes[describer.model])

            # add permissions to each DjangoObjectType class (object fields)
            self._add_permissions_to_type_class(describer, self.type_classes[describer.model])

        for describer in describers:
            # create a Query class for each model (need to create all of them first)
            self.query_classes[describer.model] = self._create_query_class(describer, self.type_classes)

            # add permissions to each Query class (listing, detail)
            self._add_permissions_to_query_class(describer, self.query_classes[describer.model])

        # create GraphQL schema
        schema = graphene.Schema(query=self._create_global_query_class(self.query_classes))

        # create GraphQL view
        return GraphQLView.as_view(graphiql=True, schema=schema)
