class Registry:
    @staticmethod
    def _match(what, to):
        return isinstance(what, to) or issubclass(what, to)

    def __init__(self, key_type=None, value_type=None):
        self._key_type = key_type
        self._value_type = value_type
        self._storage = {}

    def __setitem__(self, key, value):
        if key in self._storage:
            raise ValueError("Key `{}` is already present.".format(key))

        if self._key_type is not None and not Registry._match(key, self._key_type):
            raise ValueError("Key `{}` is of incorrect type: expected `{}`, got `{}`.".format(
                key, self._key_type.__name__, type(key).__name__))

        if self._value_type is not None and not Registry._match(value, self._value_type):
            raise ValueError("Value `{}` is of incorrect type: expected `{}`, got `{}`.".format(
                value, self._value_type.__name__, type(value).__name__))

        self._storage[key] = value

    def __getitem__(self, item):
        if item in self._storage:
            return self._storage[item]

    def __contains__(self, item):
        return item in self._storage

    def __str__(self):
        return "Registry <{}>".format(self._storage)

    def keys(self):
        return tuple(self._storage.keys())

    def values(self):
        return tuple(self._storage.values())
