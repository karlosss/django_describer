from enum import Enum
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


class Mode(Enum):
    LIST = 0
    DETAIL = 1
    CREATE = 2
    UPDATE = 3
    DELETE = 4


class Describer(metaclass=DescriberMeta):
    @classmethod
    def is_abstract(cls):
        return cls.model is None

    @classmethod
    def determine_fields(cls, mode):
        """
        Constructs a tuple of fields based on the model and user specification.
        """
        if mode in (Mode.LIST, Mode.DETAIL):
            return determine_fields(cls.model, cls.retrieve_only_fields, cls.retrieve_exclude_fields)
        elif mode == Mode.DETAIL:
            raise

    @classmethod
    def get_extra_fields(cls, mode):
        """
        A small wrapper around extra_fields, converting return_types of Django models to ModelTypes.
        Also instantiates all types, if they aren't yet.
        """
        iterable = None
        if mode in (Mode.LIST, Mode.DETAIL):
            iterable = cls.retrieve_extra_fields.items()

        ret = {}
        for name, return_type in iterable:
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
        for field, permissions in cls.retrieve_field_permissions.items():
            if not isinstance(permissions, (list, tuple)):
                ret[field] = (permissions,)
            else:
                ret[field] = tuple(permissions)
        return ret

    @classmethod
    def get_permissions(cls, mode):
        """
        A small wrapper around listing_permissions, handles inconsistencies of one class and a tuple of classes.
        """
        permissions = None
        if mode == Mode.LIST:
            permissions = cls.list_permissions
        elif mode == Mode.DETAIL:
            permissions = cls.detail_permissions

        if not isinstance(permissions, (list, tuple)):
            return permissions,
        return permissions

    model = None

    default_page_size = None
    max_page_size = None

    enable_list = True
    enable_detail = True
    enable_create = True
    enable_update = True
    enable_delete = True

    retrieve_only_fields = None
    retrieve_exclude_fields = None
    retrieve_extra_fields = {}
    retrieve_field_permissions = {}

    list_permissions = ()
    detail_permissions = ()

    create_only_fields = None
    create_exclude_fields = None
    create_extra_fields = {}
    create_permissions = ()
    create_fn = None
