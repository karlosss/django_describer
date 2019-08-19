from inspect import isclass

from django.db.models import Model

from datatypes import ModelType, modeltype_registry
from utils import determine_fields

all_describers = {}


def get_describers():
    return list(all_describers.values())


class DescriberMeta(type):
    """
    Automatically registers each describer and prevents multiple describers for a model.
    """
    def __new__(mcs, name, bases, attrs, **kwargs):
        cls = super().__new__(mcs, name, bases, attrs)
        if not cls.is_abstract():
            # create a ModelType off of the model
            if cls.model in modeltype_registry:
                raise ValueError("Multiple describers for `{}` model".format(cls.model.__name__))
            modeltype_registry[cls.model] = ModelType(cls.model)

            all_describers[cls.model] = cls
        return cls


class Describer(metaclass=DescriberMeta):
    @classmethod
    def is_abstract(cls):
        return cls.model is None

    @classmethod
    def determine_fields(cls):
        """
        Constructs a tuple of retrievable fields based on the model and user specification.
        """
        return determine_fields(cls.model, cls.only_fields, cls.exclude_fields)

    @classmethod
    def get_extra_fields_names(cls):
        return tuple(cls.extra_fields.keys())

    @classmethod
    def get_extra_fields(cls):
        """
        A small wrapper around extra_fields, converting return_types of Django models to ModelTypes.
        Also instantiates all types, if they aren't yet.
        """
        ret = {}
        for name, return_type in cls.extra_fields.items():
            if isclass(return_type):
                if issubclass(return_type, Model):
                    ret[name] = ModelType(return_type)
                else:
                    ret[name] = return_type()
            else:
                ret[name] = return_type
        return ret

    @classmethod
    def get_field_permissions(cls):
        """
        A small wrapper around field_permissions, handles inconsistencies of one class and a tuple of classes.
        """
        ret = {}
        for field, permissions in cls.field_permissions.items():
            if not isinstance(permissions, (list, tuple)):
                ret[field] = (permissions,)
            else:
                ret[field] = tuple(permissions)
        return ret

    @classmethod
    def get_listing_permissions(cls):
        """
        A small wrapper around listing_permissions, handles inconsistencies of one class and a tuple of classes.
        """
        if not isinstance(cls.listing_permissions, (list, tuple)):
            return cls.listing_permissions,
        return cls.listing_permissions

    @classmethod
    def get_detail_permissions(cls):
        """
        A small wrapper around detail_permissions, handles inconsistencies of one class and a tuple of classes.
        """
        if not isinstance(cls.detail_permissions, (list, tuple)):
            return cls.detail_permissions,
        return cls.detail_permissions

    model = None

    only_fields = None
    exclude_fields = None

    extra_fields = {}

    field_permissions = {}
    listing_permissions = ()
    detail_permissions = ()

    default_page_size = None
    max_page_size = None
