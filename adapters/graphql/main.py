import django
import graphene
from django.db.models import Model
from graphene.types.utils import get_field_as
from graphene_django_extras import DjangoObjectType, DjangoObjectField, LimitOffsetGraphqlPagination, \
    DjangoListObjectType
from graphene_django.views import GraphQLView
from graphene_django_extras.settings import graphql_api_settings

from adapters.graphql.converter import convert_local_fields
from adapters.base import Adapter
from adapters.graphql.fields import DjangoNestableListObjectField
from datatypes import String, Integer, Float, Boolean, NullType
from describers import get_describers
from registry import Registry


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

        """

        type_list_meta = type(
            "Meta",
            (object,),
            {
                "model": describer.model,
                "pagination": LimitOffsetGraphqlPagination(
                    default_limit=describer.default_page_size or graphql_api_settings.DEFAULT_PAGE_SIZE,
                    max_limit=describer.max_page_size or graphql_api_settings.DEFAULT_PAGE_SIZE
                ),
                "filter_fields": self._create_filter_fields(describer),
            }
        )
        type_list_class = type(
            "{}ListType".format(describer.model.__name__),
            (DjangoListObjectType,),
            {
                "Meta": type_list_meta
            }
        )

        type_meta = type(
            "Meta",
            (object,),
            {
                "model": describer.model,
                "only_fields": describer.determine_fields(),
            }
        )

        type_class = type(
            "{}Type".format(describer.model.__name__),
            (DjangoObjectType,),
            {
                "Meta": type_meta,
                "get_list_type": lambda: type_list_class,
                **convert_local_fields(describer.model, describer.determine_fields()),
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

    def _create_query_class(self, describer, type_classes):
        """
        Creates such a class:

        class Query(object):
            all_categories = graphene.List(CategoryType)

            def resolve_all_categories(self, info, **kwargs):
                return Category.objects.all()
        """

        model_plural = describer.model._meta.verbose_name_plural
        model_singular = describer.model._meta.verbose_name

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

    def _create_global_query_class(self, query_classes):
        """
        Creates such a class:

        class Query(cookbook.ingredients.schema.Query, graphene.ObjectType):
            pass
        """

        return type("Query", query_classes.values() + (graphene.ObjectType,), {})

    def generate(self):
        describers = get_describers()

        self.type_classes = Registry(key_type=Model, value_type=DjangoObjectType)
        self.query_classes = Registry(key_type=Model, value_type=GraphQL._Query)

        for describer in describers:
            # create a DjangoObjectType for the model
            self.type_classes[describer.model] = self._create_type_class(describer)

        for describer in describers:
            # create a Query class for each model (need to create all of them first)
            self.query_classes[describer.model] = self._create_query_class(describer, self.type_classes)

        # create GraphQL schema
        schema = graphene.Schema(query=self._create_global_query_class(self.query_classes))

        # create GraphQL view
        return GraphQLView.as_view(graphiql=True, schema=schema)
