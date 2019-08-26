from inspect import isclass

from utils import AttrDict


class Type:
    def __init__(self, required=True, **kwargs):
        self.kwargs = kwargs
        self.kwargs["required"] = required

    def convert(self, to, **kwargs):
        raise NotImplementedError

    @staticmethod
    def filters():
        return ()


class String(Type):
    def convert(self, to, **kwargs):
        return to.string_type(self, **kwargs)

    @staticmethod
    def filters():
        return (
            "contains",
            "endswith",
            "exact",
            "icontains",
            "iendswith",
            "iexact",
            "iregex",
            "isnull",
            "istartswith",
            "regex",
            "startswith",
        )


class Integer(Type):
    def convert(self, to, **kwargs):
        return to.integer_type(self, **kwargs)

    @staticmethod
    def filters():
        return (
            "exact",
            "gt",
            "gte",
            "isnull",
            "lt",
            "lte",
        )


class Float(Type):
    def convert(self, to, **kwargs):
        return to.float_type(self, **kwargs)


class ID(Type):
    def convert(self, to, **kwargs):
        return to.id_type(self, **kwargs)


class Boolean(Type):
    def convert(self, to, **kwargs):
        return to.boolean_type(self, **kwargs)


class ModelType(Type):
    def __init__(self, model, **kwargs):
        self.model = model
        super().__init__(**kwargs)

    def convert(self, to, **kwargs):
        return to.model_type(self, **kwargs)


model_type_mapping = AttrDict()  # key: Model, value: ModelType


class QuerySet(Type):
    def __init__(self, of_type, **kwargs):
        self.of_type = of_type
        super().__init__(**kwargs)

    @property
    def type(self):
        return model_type_mapping[self.of_type] or self.of_type

    def convert(self, to, **kwargs):
        return to.queryset_type(self, **kwargs)


class NullType(Type):
    """
    Null object for types. convert() raises an exception. Useful when converting an unknown type for filters.
    """

    def convert(self, to, **kwargs):
        raise ValueError("Trying to convert NullType.")


class CompositeType(Type):
    """
    Technically, this is an Object type without Django model.
    """

    def __init__(self, field_map, **kwargs):
        super().__init__(**kwargs)
        self.field_map = field_map

    def convert(self, to, **kwargs):
        return to.composite_type(self, **kwargs)


def get_instantiated_type(maybe_type):
    if maybe_type in model_type_mapping:
        return model_type_mapping[maybe_type]
    if isclass(maybe_type):
        return maybe_type()
    return maybe_type
