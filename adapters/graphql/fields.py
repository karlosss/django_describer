import graphene
from graphene import Argument
from graphene_django.utils import maybe_queryset, is_valid_django_model
from graphene_django_extras import DjangoFilterListField, DjangoListObjectField
from graphene_django_extras.base_types import DjangoListObjectBase
from graphene_django_extras.utils import queryset_factory, get_extra_filters


class OrderingMixin:
    """
    A mixin to add ordering feature to graphene_django_extra fields.

    Usage:

    query{
      books(ordering: "name"){
        id
        name
      }

      books(ordering: "name,-id"){
        id
        name
      }
    }
    """

    def __init__(self, *args, **kwargs):
        kwargs["args"] = {"ordering": Argument(graphene.String,
                                               description="String of comma-sepratated fields to order by.")}
        super().__init__(*args, **kwargs)

    @staticmethod
    def list_resolver(*args, **kwargs):
        qs = DjangoFilterListField.list_resolver(*args, **kwargs)
        if "ordering" in kwargs:
            ordering_fields = [field.strip() for field in kwargs["ordering"].split(",")]
            qs = qs.order_by(*ordering_fields)
        return qs


class DjangoFilterOrderingListField(OrderingMixin, DjangoFilterListField):
    """
    DjangoFilterListField with ordering feature.
    """


class DjangoNestableListObjectField(DjangoListObjectField):
    """
    Similar to DjangoListObjectField, except it can be nested into ManyToOneRel. Also can handle permissions.
    """
    def list_resolver(self, manager, filterset_class, filtering_args, root, info, **kwargs):
        qs = queryset_factory(manager, info.field_asts, info.fragments, **kwargs)

        filter_kwargs = {k: v for k, v in kwargs.items() if k in filtering_args}

        qs = filterset_class(data=filter_kwargs, queryset=qs, request=info.context).qs

        if root and is_valid_django_model(root._meta.model):
            extra_filters = get_extra_filters(root, manager.model)
            qs = qs.filter(**extra_filters)

        count = qs.count()
        results = maybe_queryset(qs)

        if hasattr(self, "permission_check_method"):
            self.permission_check_method(root, info, results, **kwargs)

        return DjangoListObjectBase(
            count=count,
            results=results,
            results_field_name=self.type._meta.results_field_name,
        )

    def get_resolver(self, parent_resolver):
        if hasattr(parent_resolver, "permissions_check"):
            self.permission_check_method = parent_resolver
        return super().get_resolver(parent_resolver)
