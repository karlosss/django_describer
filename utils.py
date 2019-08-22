from django.db.models import ManyToOneRel, ManyToManyRel


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
