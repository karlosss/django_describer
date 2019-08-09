import django
import graphene
from django.db.models import Model
from graphene.types.utils import get_field_as
from graphene_django_extras import DjangoObjectType, DjangoObjectField, LimitOffsetGraphqlPagination, \
    DjangoListObjectType
from graphene_django.views import GraphQLView
from graphene_django_extras.settings import graphql_api_settings

from adapters.base import Adapter
import adapters.graphql.converter  # IMPORTANT!!!
from adapters.graphql.fields import DjangoNestableListObjectField
from datatypes import String, Integer, Float, Boolean, NullType
from describers import get_describers
from registry import Registry
from utils import model_singular_name, model_plural_name, get_local_fields, field_names


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

    def list_type(self, type, **kwargs):
        return get_field_as(graphene.types.List(type.type.convert(self, list=True)), _as=graphene.Field)

    def model_type(self, type, **kwargs):
        if "list" in kwargs and kwargs["list"]:
            return self.type_classes[type.model]
        return graphene.Dynamic(lambda: graphene.Field(self.type_classes[type.model]))

    class _Query:
        """
        A type for local graphene Query classes. Intentionally blank, serves only for type checking.
        """

    def _create_type_class(self, describer):
        """
        Creates a DjangoObjectType and a DjangoListObjectType for a model. Must be in this order!!!
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

    def _create_permissions_check_resolver(self, permission_classes=()):
        def resolver(self, info, results, **kwargs):
            for permission_class in permission_classes:
                pc = permission_class(info.context, qs=results)
                if not pc.has_permission():
                    raise PermissionError(pc.error_message())
        resolver.permissions_check = True
        return resolver

    def _create_permissions_check_method(self, field_name, permission_classes=()):
        def resolve_method(self, info):
            for permission_class in permission_classes:
                pc = permission_class(info.context, obj=self)
                if not pc.has_permission():
                    raise PermissionError(pc.error_message())
            return getattr(self, field_name)
        return resolve_method

    def _create_query_class(self, describer, type_classes):
        model_singular = model_singular_name(describer.model)
        model_plural = model_plural_name(describer.model)

        query_class = type(
            "Query",
            (GraphQL._Query,),
            {
                model_singular: DjangoObjectField(type_classes[describer.model],
                                                  description="Single {} query.".format(model_singular)),
                model_plural: DjangoNestableListObjectField(
                    type_classes[describer.model].get_list_type(),
                    description="Multiple {} query.".format(model_plural)),
            }
        )

        return query_class

    def _add_permissions_to_query_class(self, describer, query_class):
        if describer.listing_permissions:
            model_plural = model_plural_name(describer.model)
            setattr(query_class,
                    "resolve_{}".format(model_plural),
                    self._create_permissions_check_resolver(describer.get_listing_permissions()))

    def _add_permissions_to_type_class(self, describer, type_class):
        local_fields = field_names(get_local_fields(describer.model))

        for field_name, permission_classes in describer.get_field_permissions().items():
            if field_name in local_fields:
                setattr(type_class,
                        "resolve_{}".format(field_name),
                        self._create_permissions_check_method(field_name, permission_classes))
            else:
                setattr(type_class,
                        "resolve_{}".format(field_name),
                        self._create_permissions_check_resolver(permission_classes))

    def _create_global_query_class(self, query_classes):
        return type("Query", query_classes.values() + (graphene.ObjectType,), {})

    def generate(self):
        describers = get_describers()

        self.type_classes = Registry(key_type=Model, value_type=DjangoObjectType)
        self.query_classes = Registry(key_type=Model, value_type=GraphQL._Query)

        for describer in describers:
            # create a DjangoObjectType for the model
            self.type_classes[describer.model] = self._create_type_class(describer)

            # add permissions to each DjangoObjectType class (object fields)
            self._add_permissions_to_type_class(describer, self.type_classes[describer.model])

        for describer in describers:
            # create a Query class for each model (need to create all of them first)
            self.query_classes[describer.model] = self._create_query_class(describer, self.type_classes)

            # add permissions to each Query class (listing, detail)
            # self._add_permissions_to_query_class(describer, self.query_classes[describer.model])

        # create GraphQL schema
        schema = graphene.Schema(query=self._create_global_query_class(self.query_classes))

        # create GraphQL view
        return GraphQLView.as_view(graphiql=True, schema=schema)
