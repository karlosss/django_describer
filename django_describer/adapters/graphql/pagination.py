from math import fabs

from graphene_django_extras import LimitOffsetGraphqlPagination
from graphene_django_extras.paginations.utils import _nonzero_int


class LimitOffsetOrderingGraphqlPagination(LimitOffsetGraphqlPagination):
    def paginate_queryset(self, qs, **kwargs):
        """
        The original method is not sorting when limit = None
        """
        order = kwargs.pop(self.ordering_param, None) or self.ordering

        if order:
            if "," in order:
                order = order.strip(",").replace(" ", "").split(",")
                if order.__len__() > 0:
                    qs = qs.order_by(*order)
            else:
                qs = qs.order_by(order)

        limit = _nonzero_int(
            kwargs.get(self.limit_query_param, None), strict=True, cutoff=self.max_limit
        )

        if limit is None:
            return qs

        offset = kwargs.get(self.offset_query_param, 0)

        return qs[offset: offset + fabs(limit)]
