from enum import Enum

from datatypes import get_instantiated_type, Boolean
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
                 extra_fields=None, permissions=(), fn=None, return_params=None):
        self.extra_fields = extra_fields if extra_fields is not None else {}
        self.only_fields = only_fields
        self.exclude_fields = exclude_fields
        self.permissions = permissions
        self.fn = fn
        self.read_only = read_only
        self.return_params = return_params

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
            ret[name] = get_instantiated_type(return_type)
        return ret

    def get_permissions(self):
        """
        A small wrapper around permissions, handles inconsistencies of one class and a tuple of classes.
        """

        if not isinstance(self.permissions, (list, tuple)):
            return self.permissions,
        return self.permissions

    def get_return_params(self):
        """
        A hook which can be used to provide a default value in subclasses.
        """
        return self.return_params

    def get_fn(self):
        """
        A hook which can be used to provide a default value in subclasses.
        """
        return self.fn


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


class ListOrDetail:
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


class ListAction(ListOrDetail):
    pass


class DetailAction(ListOrDetail):
    pass


class CreateAction(Action):
    def __init__(self, only_fields=None, exclude_fields=None, extra_fields=None, permissions=(), fn=None,
                 return_params=None):
        super().__init__(only_fields=only_fields, exclude_fields=exclude_fields, extra_fields=extra_fields,
                         permissions=permissions, fn=fn, return_params=return_params)
        self._name = ActionName.CREATE.name

    def determine_fields(self):
        fields = super().determine_fields()

        # remove id from the fields
        filtered_fields = tuple(f for f in fields if f != "id")
        return filtered_fields

    def get_return_params(self):
        return super().get_return_params() or {"object": self._describer.model, "ok": Boolean}

    def get_fn(self):
        super_fn = super().get_fn()
        if super_fn is not None:
            return super_fn

        def fn(request, instance, data):
            obj = self._describer.model(**data)
            obj.save()
            return {"object": obj, "ok": True}
        return fn


class UpdateAction(Action):
    def __init__(self, only_fields=None, exclude_fields=None, extra_fields=None, permissions=(), fn=None,
                 return_params=None):
        super().__init__(only_fields=only_fields, exclude_fields=exclude_fields, extra_fields=extra_fields,
                         permissions=permissions, fn=fn, return_params=return_params)
        self._name = ActionName.UPDATE.name

    def determine_fields(self):
        fields = super().determine_fields()

        # add id to the fields
        if "id" not in fields:
            return fields + ("id",)
        return fields

    def get_return_params(self):
        return super().get_return_params() or {"object": self._describer.model, "ok": Boolean}

    def get_fn(self):
        super_fn = super().get_fn()
        if super_fn is not None:
            return super_fn

        def fn(request, instance, data):
            for k, v in data.items():
                setattr(instance, k, v)
            instance.save()
            return {"object": instance, "ok": True}
        return fn


class DeleteAction(Action):
    def __init__(self, extra_fields=None, permissions=(), fn=None, return_params=None):
        super().__init__(only_fields=None, exclude_fields=None, extra_fields=extra_fields,
                         permissions=permissions, fn=fn, return_params=return_params)
        self._name = ActionName.DELETE.name

    def determine_fields(self):
        return "id",

    def get_return_params(self):
        return super().get_return_params() or {"object": self._describer.model, "ok": Boolean}

    def get_fn(self):
        super_fn = super().get_fn()
        if super_fn is not None:
            return super_fn

        def fn(request, instance, data):
            instance.delete()
            return {"object": instance, "ok": True}
        return fn
