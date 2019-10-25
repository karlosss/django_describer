from enum import Enum

from django_describer.permissions import AllowAll
from .utils import ensure_tuple, set_param_if_unset, get_object_or_raise, build_extra_fields, determine_fields


class ActionName(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    DETAIL = "detail"

    @classmethod
    def values(cls):
        return set(item.value for item in cls)


def default_create(model):
    def fn(request, data):
        obj = model(**data)
        obj.save()
        return {"object": obj}
    return fn


def default_update(request, instance, data):
    for k, v in data:
        setattr(instance, k, v)
    instance.save()
    return {"object": instance}


def default_delete(request, instance, data):
    instance.delete()
    return {"object": instance}


class BaseAction:
    read_only = False
    has_model = True

    def __init__(self, permissions=None):
        self.permissions = ensure_tuple(permissions)
        self._describer = None
        self._name = None

    def set_describer(self, describer):
        set_param_if_unset(self, "_describer", describer)

    def set_name(self, name):
        set_param_if_unset(self, "_name", name)

    def get_name(self):
        if self._name is None:
            raise ValueError("_name is not set.")

        if self._describer is not None:
            model = self._describer.model.__name__
            return "{}_{}".format(model, self._name)
        return self._name

    def get_permissions(self):
        if self.permissions:
            return self.permissions
        if self._describer is not None:
            return self._describer.get_default_action_permissions()
        return AllowAll,

    def convert(self, to, **kwargs):
        raise NotImplementedError


class RetrieveAction(BaseAction):
    read_only = True

    def __init__(self, permissions=None, fetch_fn=None):
        super().__init__(permissions=permissions)
        self.fetch_fn = fetch_fn

    def get_fetch_fn(self):
        return self.fetch_fn or self.get_default_fetch_fn()

    def get_default_fetch_fn(self):
        raise NotImplementedError


class ListAction(RetrieveAction):
    def get_default_fetch_fn(self):
        def fn(request):
            return self._describer.model.objects.all()
        return fn

    def convert(self, to, **kwargs):
        return to.list_action(self, **kwargs)


class DetailAction(RetrieveAction):
    def __init__(self, permissions=None, fetch_fn=None, id_arg=True):
        super().__init__(permissions=permissions, fetch_fn=fetch_fn)
        self.id_arg = id_arg

    def get_default_fetch_fn(self):
        def fn(request, pk):
            return get_object_or_raise(self._describer.model, pk)
        return fn

    def convert(self, to, **kwargs):
        return to.detail_action(self, **kwargs)


class ModifyAction(BaseAction):
    def __init__(self, permissions=None, only_fields=None, exclude_fields=None, extra_fields=None, exec_fn=None,
                 return_fields=None, field_kwargs=None):
        super().__init__(permissions=permissions)
        self.only_fields = ensure_tuple(only_fields, convert_none=False)
        self.exclude_fields = ensure_tuple(exclude_fields, convert_none=False)
        self.extra_fields = build_extra_fields(extra_fields)
        self.exec_fn = exec_fn
        self.return_fields = build_extra_fields(return_fields)
        self.field_kwargs = field_kwargs or {}

    def get_exec_fn(self):
        return self.exec_fn or self.get_default_exec_fn()

    def get_default_exec_fn(self):
        raise NotImplementedError

    def get_return_fields(self):
        return self.return_fields or build_extra_fields(self.get_default_return_fields())

    def get_default_return_fields(self):
        raise NotImplementedError

    def determine_fields(self):
        return determine_fields(self._describer.model, self.only_fields, self.exclude_fields, no_reverse=True)


class CreateAction(ModifyAction):
    def get_default_exec_fn(self):
        return default_create(self._describer.model)

    def get_default_return_fields(self):
        return {"object": self._describer.model}

    def determine_fields(self):
        fields = super().determine_fields()
        fields_without_id = tuple(f for f in fields if f != "id")
        return fields_without_id

    def convert(self, to, **kwargs):
        return to.create_action(self, **kwargs)


class FetchModifyAction(ModifyAction):
    def __init__(self, permissions=None, only_fields=None, exclude_fields=None, extra_fields=None, exec_fn=None,
                 return_fields=None, field_kwargs=None, fetch_fn=None):
        super().__init__(permissions=permissions, only_fields=only_fields, exclude_fields=exclude_fields,
                         extra_fields=extra_fields, exec_fn=exec_fn, return_fields=return_fields,
                         field_kwargs=field_kwargs)
        self.fetch_fn = fetch_fn

    def get_fetch_fn(self):
        return self.fetch_fn or self.get_default_fetch_fn()

    def get_default_fetch_fn(self):
        def fn(request, pk):
            return get_object_or_raise(self._describer.model, pk)
        return fn


class UpdateAction(FetchModifyAction):
    def get_default_exec_fn(self):
        return default_update

    def get_default_return_fields(self):
        return {"object": self._describer.model}

    def determine_fields(self):
        fields = super().determine_fields()
        if "id" not in fields:
            fields = fields + ("id",)
        return fields

    def convert(self, to, **kwargs):
        return to.update_action(self, **kwargs)


class DeleteAction(FetchModifyAction):
    def __init__(self, permissions=None, extra_fields=None, exec_fn=None, return_fields=None, field_kwargs=None,
                 fetch_fn=None):
        super().__init__(permissions=permissions, extra_fields=extra_fields, exec_fn=exec_fn,
                         return_fields=return_fields, field_kwargs=field_kwargs, fetch_fn=fetch_fn)

    def get_default_exec_fn(self):
        return default_delete

    def get_default_return_fields(self):
        return {"object": self._describer.model}

    def determine_fields(self):
        return "id",

    def convert(self, to, **kwargs):
        return to.delete_action(self, **kwargs)


class CustomAction(ModifyAction):
    has_model = False

    def __init__(self, input_type, return_fields, exec_fn, permissions=None):
        super().__init__(permissions=permissions, exec_fn=exec_fn, return_fields=return_fields)
        self.input_type = input_type

    def get_default_exec_fn(self):
        raise ValueError("No default exec_fn, you need to provide one.")

    def get_default_return_fields(self):
        raise ValueError("No default return fields, you need to provide some.")

    def convert(self, to, **kwargs):
        return to.custom_action(self, **kwargs)


class CustomObjectAction(UpdateAction):
    def __init__(self, permissions=None, extra_fields=None, exec_fn=None, return_fields=None, fetch_fn=None):
        super().__init__(permissions=permissions, only_fields=(), exclude_fields=None,
                         extra_fields=extra_fields, exec_fn=exec_fn, return_fields=return_fields, fetch_fn=fetch_fn)

    def get_default_exec_fn(self):
        raise ValueError("No default exec_fn, you need to provide one.")

    def convert(self, to, **kwargs):
        return to.custom_object_action(self, **kwargs)
