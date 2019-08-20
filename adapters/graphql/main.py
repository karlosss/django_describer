import logging

import graphene
from django.db.models import Model
from graphene.types.utils import get_field_as
from graphene_django_extras import DjangoObjectType
from graphene_django.views import GraphQLView

from adapters.base import Adapter
from adapters.graphql.fields import DjangoNestableListObjectPermissionsField
from adapters.graphql.retrieving import Query, create_type_class, add_permissions_to_type_class, \
    add_extra_fields_to_type_class, create_query_class, add_permissions_to_query_class, create_global_query_class
from describers import get_describers
from registry import Registry


class GraphQL(Adapter):
    def _convert_primitive_type(self, type, **kwargs):
        """
        A helper for converting primitive types to Graphene.
        """
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
        """
        Returns a field for listing. If the data shall be fetched from a queryset returned by its property,
        the property name is passed via kwargs.
        """
        property_name = kwargs.get("property_name", None)

        return graphene.Dynamic(lambda: DjangoNestableListObjectPermissionsField(
            type.type.convert(self, list=True),  # listing type is derived from the type passed as the of_type argument
            property_name=property_name))

    def model_type(self, type, **kwargs):
        """
        Returns a DjangoListObjectType if converting for lists, Field otherwise.
        """
        if "list" in kwargs and kwargs["list"]:
            return self.type_classes[type.model].get_list_type()

        return graphene.Dynamic(lambda: graphene.Field(self.type_classes[type.model]))

    def generate(self):
        # silence GraphQL exception logger
        logging.getLogger("graphql.execution.utils").setLevel(logging.CRITICAL)

        describers = get_describers()

        self.type_classes = Registry(key_type=Model, value_type=DjangoObjectType)
        self.query_classes = Registry(key_type=Model, value_type=Query)

        for describer in describers:
            # create a DjangoObjectType for the model
            self.type_classes[describer.model] = create_type_class(describer)

            # add extra fields to each DjangoObjectType class
            add_extra_fields_to_type_class(self, describer, self.type_classes[describer.model])

            # add permissions to each DjangoObjectType class (object fields)
            add_permissions_to_type_class(describer, self.type_classes[describer.model])

        for describer in describers:
            # create a Query class for each model (need to create all of them first)
            self.query_classes[describer.model] = create_query_class(describer, self.type_classes)

            # add permissions to each Query class (listing, detail)
            add_permissions_to_query_class(describer, self.query_classes[describer.model])

        # create GraphQL schema
        schema = graphene.Schema(query=create_global_query_class(self.query_classes))

        # create GraphQL view
        return GraphQLView.as_view(graphiql=True, schema=schema)
