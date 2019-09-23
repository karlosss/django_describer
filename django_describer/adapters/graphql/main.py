import logging

import graphene
from graphene.types.utils import get_field_as
from graphene_django.views import GraphQLView

from django_describer.adapters.utils import non_model_actions
from ..base import Adapter
from .fields import DjangoNestableListObjectPermissionsField, DjangoObjectPermissionsField
from ...datatypes import get_instantiated_type
from ...describers import get_describers
from ...utils import AttrDict, in_kwargs_and_true
from .retrieving import create_type_class, add_extra_fields_to_type_class, add_permissions_to_type_class, \
    create_query_class, create_global_query_class
from .modifying import create_mutation_classes, create_global_mutation_class

create_class = type


class GraphQL(Adapter):
    def _convert_primitive_type(self, type, **kwargs):
        """
        A helper for converting primitive types to Graphene.
        """
        if in_kwargs_and_true(kwargs, "input"):
            return type
        if in_kwargs_and_true(kwargs, "input_field"):
            return get_field_as(type, _as=graphene.InputField)
        return get_field_as(type, _as=graphene.Field)

    def string_type(self, type, **kwargs):
        return self._convert_primitive_type(graphene.types.String(required=type.kwargs["required"]), **kwargs)

    def integer_type(self, type, **kwargs):
        return self._convert_primitive_type(graphene.types.Int(required=type.kwargs["required"]), **kwargs)

    def float_type(self, type, **kwargs):
        return self._convert_primitive_type(graphene.types.Float(required=type.kwargs["required"]), **kwargs)

    def id_type(self, type, **kwargs):
        return self._convert_primitive_type(graphene.types.ID(required=type.kwargs["required"]), **kwargs)

    def boolean_type(self, type, **kwargs):
        return self._convert_primitive_type(graphene.types.Boolean(required=type.kwargs["required"]), **kwargs)

    def queryset_type(self, type, **kwargs):
        """
        Returns a field for listing. If the data shall be fetched from a queryset returned by its property,
        the property name is passed via kwargs.
        """
        if in_kwargs_and_true(kwargs, "input") or in_kwargs_and_true(kwargs, "input_field"):
            raise ValueError("Cannot convert QuerySet as input parameter.")

        property_name = kwargs.get("property_name", None)

        return graphene.Dynamic(lambda: DjangoNestableListObjectPermissionsField(
            type.type.convert(self, list=True),  # listing type is derived from the type passed as the of_type argument
            property_name=property_name))

    def model_type(self, type, **kwargs):
        """
        Returns a DjangoListObjectType if converting for lists, Field otherwise.
        """
        if in_kwargs_and_true(kwargs, "list"):
            return self.type_classes[type.model].get_list_type()

        if in_kwargs_and_true(kwargs, "input") or in_kwargs_and_true(kwargs, "input_field"):
            raise ValueError("Cannot convert ModelType as input parameter.")

        return graphene.Dynamic(lambda: graphene.Field(self.type_classes[type.model]))

    def composite_type(self, type, **kwargs):
        attrs = {}
        for name, return_type in type.field_map.items():
            attrs[name] = get_instantiated_type(return_type).convert(
                self, input=in_kwargs_and_true(kwargs, "input"), input_field=in_kwargs_and_true(kwargs, "input_field"))

        if in_kwargs_and_true(kwargs, "input") or in_kwargs_and_true(kwargs, "input_field"):
            input_class = create_class(
                "{}Input".format(type.type_name),
                (graphene.InputObjectType,),
                attrs,
            )(required=type.kwargs["required"])

            if in_kwargs_and_true(kwargs, "input"):
                return input_class
            return get_field_as(input_class, _as=graphene.InputField)

        type_class = create_class(
            "{}ObjectType".format(type.type_name),
            (graphene.ObjectType,),
            attrs
        )
        return graphene.Field(type_class)

    def list_action(self, action, **kwargs):
        return DjangoNestableListObjectPermissionsField(
            self.type_classes[action._describer.model].get_list_type(), fetch_fn=action.get_fetch_fn())

    def detail_action(self, action, **kwargs):
        return DjangoObjectPermissionsField(self.type_classes[action._describer.model], fetch_fn=action.get_fetch_fn(),
                                            id_arg=action.id_arg)

    def create_action(self, action, **kwargs):
        if in_kwargs_and_true(kwargs, "input_flag"):
            return "create"

    def update_action(self, action, **kwargs):
        if in_kwargs_and_true(kwargs, "input_flag"):
            return "update"

    def delete_action(self, action, **kwargs):
        if in_kwargs_and_true(kwargs, "input_flag"):
            return "delete"

    def custom_object_action(self, action, **kwargs):
        if in_kwargs_and_true(kwargs, "input_flag"):
            return "update"

    def generate(self):
        # silence GraphQL exception logger
        # logging.getLogger("graphql.execution.utils").setLevel(logging.CRITICAL)

        describers = get_describers()

        self.type_classes = AttrDict()  # key: Model, value: DjangoObjectType
        self.query_classes = AttrDict()  # key: Model, value: Query
        self.mutation_classes = AttrDict()  # key: Model, value: Mutation

        for describer in describers:
            # create a DjangoObjectType for the model
            self.type_classes[describer.model] = create_type_class(describer)

            # add extra fields to each DjangoObjectType class
            add_extra_fields_to_type_class(self, describer, self.type_classes[describer.model])

            # add permissions to each DjangoObjectType class (object fields)
            add_permissions_to_type_class(describer, self.type_classes[describer.model])

        for describer in describers:
            # create a Query class for each model (need to create all of them first)
            self.query_classes[describer.model] = create_query_class(self, describer.get_actions())

            # create mutation classes for the describer, including permissions and extra fields
            self.mutation_classes[describer.model] = create_mutation_classes(self, describer.get_actions())

        non_model_query_class = create_query_class(self, non_model_actions)
        non_model_mutation_classes = create_mutation_classes(self, non_model_actions)

        # create GraphQL schema
        schema = graphene.Schema(
            query=create_global_query_class(self.query_classes, non_model_query_class),
            mutation=create_global_mutation_class(self.mutation_classes, non_model_mutation_classes)
        )

        # create GraphQL view
        return GraphQLView.as_view(graphiql=True, schema=schema)
