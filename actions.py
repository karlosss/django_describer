from enum import Enum
from inspect import isclass

from django.db.models import Model

from datatypes import ModelType
from utils import determine_fields


class ActionName(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

    @classmethod
    def values(cls):
        return set(item.value for item in cls)


class Action:
    def __init__(self, read_only=False, only_fields=None, exclude_fields=None,
                 extra_fields=None, permissions=(), fn=None):
        self.extra_fields = extra_fields if extra_fields is not None else {}
        self.only_fields = only_fields
        self.exclude_fields = exclude_fields
        self.permissions = permissions
        self.fn = fn
        self.read_only = read_only

        self._describer = None
        self._name = None

    def set_describer(self, describer):
        if self._describer is not None:
            raise ValueError("Describer is already set")
        self._describer = describer

    def set_name(self, name):
        if self._name is not None:
            raise ValueError("Name is already set")
        self._name = name

    def determine_fields(self):
        return determine_fields(self._describer.model, self.only_fields,
                                self.exclude_fields, no_reverse=not self.read_only)

    def get_extra_fields(self):
        """
        A small wrapper around extra_fields, converting return_types of Django models to ModelTypes.
        Also instantiates all types, if they aren't yet.
        """
        ret = {}
        for name, return_type in self.extra_fields.items():
            if isclass(return_type):
                if issubclass(return_type, Model):
                    ret[name] = ModelType(return_type)
                else:
                    ret[name] = return_type()
            else:
                ret[name] = return_type
        return ret

    def get_permissions(self):
        """
        A small wrapper around permissions, handles inconsistencies of one class and a tuple of classes.
        """

        if not isinstance(self.permissions, (list, tuple)):
            return self.permissions,
        return self.permissions


class Retrieve(Action):
    def __init__(self, only_fields=None, exclude_fields=None, extra_fields=None, field_permissions=None):
        super().__init__(read_only=True, only_fields=only_fields,
                         exclude_fields=exclude_fields, extra_fields=extra_fields)

        self.field_permissions = field_permissions
        if field_permissions is None:
            self.field_permissions = {}

    def get_field_permissions(self):
        """
        A small wrapper around field_permissions, handles inconsistencies of one class and a tuple of classes.
        """
        ret = {}
        for field, permissions in self.field_permissions.items():
            if not isinstance(permissions, (list, tuple)):
                ret[field] = (permissions,)
            else:
                ret[field] = tuple(permissions)
        return ret


class ListDetailAction:
    def __init__(self, permissions=()):
        self.permissions = permissions
        self._retrieve = None

    def set_retrieve(self, retrieve):
        if self._retrieve is not None:
            raise ValueError("Retrieve is already set")
        self._retrieve = retrieve

    def __getattr__(self, item):
        if item == "__setstate__":  # workaround of Python bug: deepcopy with __getattr__
            raise AttributeError
        return getattr(self._retrieve, item)


class CreateAction(Action):
    def __init__(self, only_fields=None, exclude_fields=None, extra_fields=None, permissions=(), fn=None):
        super().__init__(only_fields=only_fields, exclude_fields=exclude_fields, extra_fields=extra_fields,
                         permissions=permissions, fn=fn)
        self._name = ActionName.CREATE.name

    def determine_fields(self):
        fields = super().determine_fields()

        # remove id from the fields
        filtered_fields = tuple(f for f in fields if f != "id")
        return filtered_fields
