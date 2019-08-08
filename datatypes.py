from django.db.models import Model

from registry import Registry


class Type:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

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


modeltype_registry = Registry(key_type=Model, value_type=ModelType)


class List(Type):
    def __init__(self, of_type, **kwargs):
        self.of_type = of_type
        super().__init__(**kwargs)

    @property
    def type(self):
        return modeltype_registry[self.of_type] or self.of_type

    def convert(self, to, **kwargs):
        return to.list_type(self, **kwargs)


class NullType(Type):
    """
    Null object for types. convert() raises an exception. Useful for types with no filters.
    """

    def convert(self, to, **kwargs):
        raise ValueError("Trying to convert NullType.")
