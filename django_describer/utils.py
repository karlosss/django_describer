import re

from django.db.models import ManyToOneRel, ManyToManyRel

from .datatypes import get_instantiated_type


class AttrDict(dict):
    """
    A dictionary with keys accessible as attributes
    """
    def __getattr__(self, item):
        return self[item]

    def keys(self):
        return tuple(super().keys())

    def values(self):
        return tuple(super().values())


def as_dict(**kwargs):
    return kwargs


def __reverse_fields(model, local_field_names):
    for name, attr in model.__dict__.items():
        # Don't duplicate any local fields
        if name in local_field_names:
            continue

        # Django =>1.9 uses 'rel', django <1.9 uses 'related'
        related = getattr(attr, "rel", None) or getattr(attr, "related", None)
        if isinstance(related, ManyToOneRel):
            yield (name, related)
        elif isinstance(related, ManyToManyRel) and not related.symmetrical:
            yield (name, related)


def _reverse_fields(model, local_field_names):
    return list(__reverse_fields(model, local_field_names))


def get_local_fields(model):
    return [
        (field.name, field)
        for field in sorted(
            list(model._meta.fields) + list(model._meta.local_many_to_many)
        )
    ]


def get_reverse_fields(model):
    local_fields = get_local_fields(model)

    # Make sure we don't duplicate local fields with "reverse" version
    local_field_names = [field[0] for field in local_fields]
    return _reverse_fields(model, local_field_names)


def get_all_model_fields(model):
    return get_local_fields(model) + get_reverse_fields(model)


def field_names(field_tuple):
    return tuple(f[0] for f in field_tuple)


def determine_fields(model, only_fields, exclude_fields, no_reverse=False):
    if no_reverse:
        all_fields = field_names(get_local_fields(model))
    else:
        all_fields = field_names(get_all_model_fields(model))

    if only_fields is None and exclude_fields is None:
        exclude_fields = ()

    if only_fields is not None and exclude_fields is not None:
        raise ValueError("Cannot define both only_fields and exclude_fields.")

    if only_fields is not None:
        if not isinstance(only_fields, (list, tuple)):
            only_fields = only_fields,
        for field in only_fields:
            if field not in all_fields:
                raise ValueError("Unknown field: {}.".format(field))
        return only_fields

    for field in exclude_fields:
        if not isinstance(exclude_fields, (list, tuple)):
            only_fields = only_fields,
        if field not in all_fields:
            raise ValueError("Unknown field: {}.".format(field))
    return tuple(f for f in all_fields if f not in exclude_fields)


def model_plural_name(model):
    return str(model._meta.verbose_name_plural)


def model_singular_name(model):
    return str(model._meta.verbose_name)


def get_object_or_none(model, pk):
    qs = model.objects.filter(pk=pk)
    if not qs.exists():
        return None
    return qs.get()


def get_object_or_raise(model, pk):
    qs = model.objects.filter(pk=pk)
    if not qs.exists():
        raise ValueError("`{}` with pk={} does not exist.".format(model, pk))
    return qs.get()


def ensure_tuple(maybe_tuple, convert_none=True):
    if maybe_tuple is None:
        if convert_none:
            return tuple()
        return None
    if isinstance(maybe_tuple, (list, tuple)):
        return tuple(maybe_tuple)
    return maybe_tuple,


def build_extra_fields(extra_fields):
    if extra_fields is None:
        return {}
    ret = {}
    for name, return_type in extra_fields.items():
        ret[name] = get_instantiated_type(return_type)
    return ret


def build_field_permissions(field_permissions):
    if field_permissions is None:
        return {}
    ret = {}
    for field, permissions in field_permissions.items():
        ret[field] = ensure_tuple(permissions)
    return ret


def set_param_if_unset(obj, param, value):
    if hasattr(obj, param) and getattr(obj, param) is not None:
        raise ValueError("`{}` is already set.".format(param))
    setattr(obj, param, value)


def in_kwargs_and_true(kwargs, param):
    return param in kwargs and kwargs[param]


def in_kwargs_and_false(kwargs, param):
    return param in kwargs and not kwargs[param]


def to_camelcase(string, capitalize=True):
    out = ''.join(a.capitalize() for a in re.split('([^a-zA-Z0-9])', string) if a.isalnum())
    if capitalize:
        return out
    return out[0].lower() + out[1:]
