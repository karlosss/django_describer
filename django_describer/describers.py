from copy import deepcopy

from .datatypes import model_type_mapping, ModelType
from .utils import determine_fields, ensure_tuple, build_field_permissions, build_extra_fields
from .actions import ListAction, DetailAction, ActionName, CreateAction, UpdateAction, DeleteAction


def get_describers():
    return tuple(DescriberMeta.all_describers.values())


class DescriberMeta(type):
    all_describers = {}
    """
    Automatically registers each describer and prevents multiple describers for a model.
    """
    def __new__(mcs, name, bases, attrs, **kwargs):
        cls = super().__new__(mcs, name, bases, attrs)
        if not cls.is_abstract():

            # create a ModelType off of the model
            if cls.model in model_type_mapping:
                raise ValueError("Multiple describers for `{}` model".format(cls.model.__name__))
            model_type_mapping[cls.model] = ModelType(cls.model)

            # save the describer
            DescriberMeta.all_describers[cls.model] = cls

            cls._fields = determine_fields(cls.model,
                                           ensure_tuple(cls.only_fields, convert_none=False),
                                           ensure_tuple(cls.exclude_fields, convert_none=False))
            cls._field_permissions = build_field_permissions(cls.field_permissions)
            cls._default_field_permissions = ensure_tuple(cls.default_field_permissions)
            cls._default_action_permissions = ensure_tuple(cls.default_action_permissions)

            cls._actions = []

            if cls.list_action is not None:
                cls.list_action = deepcopy(cls.list_action)
                cls.list_action.set_describer(cls)
                cls.list_action.set_name(ActionName.LIST.name)
                cls._actions.append(cls.list_action)

            if cls.detail_action is not None:
                cls.detail_action = deepcopy(cls.detail_action)
                cls.detail_action.set_describer(cls)
                cls.detail_action.set_name(ActionName.DETAIL.name)
                cls._actions.append(cls.detail_action)

            if cls.create_action is not None:
                cls.create_action = deepcopy(cls.create_action)
                cls.create_action.set_describer(cls)
                cls.create_action.set_name(ActionName.CREATE.name)
                cls._actions.append(cls.create_action)

            if cls.update_action is not None:
                cls.update_action = deepcopy(cls.update_action)
                cls.update_action.set_describer(cls)
                cls.update_action.set_name(ActionName.UPDATE.name)
                cls._actions.append(cls.update_action)

            if cls.delete_action is not None:
                cls.delete_action = deepcopy(cls.delete_action)
                cls.delete_action.set_describer(cls)
                cls.delete_action.set_name(ActionName.DELETE.name)
                cls._actions.append(cls.delete_action)

            for name, action in cls.extra_actions.items():
                if name in ActionName.values():
                    raise ValueError("`{}` is a reserved action name.".format(name))
                action.set_describer(cls)
                action.set_name(name)
                cls._actions.append(action)

        return cls


class Describer(metaclass=DescriberMeta):
    @classmethod
    def is_abstract(cls):
        return cls.model is None

    @classmethod
    def get_fields(cls):
        return cls._fields

    @classmethod
    def get_field_permissions(cls):
        return cls._field_permissions

    @classmethod
    def get_default_field_permissions(cls):
        return cls._default_field_permissions

    @classmethod
    def get_default_action_permissions(cls):
        return cls._default_action_permissions

    @classmethod
    def get_actions(cls):
        return cls._actions

    @classmethod
    def get_extra_fields(cls):
        if not hasattr(cls, "_extra_fields"):
            cls._extra_fields = build_extra_fields(cls.extra_fields)
        return cls._extra_fields

    model = None

    only_fields = None
    exclude_fields = None
    extra_filters = {}
    extra_fields = None
    field_permissions = None
    default_field_permissions = None

    default_page_size = None
    max_page_size = None

    list_action = ListAction()
    detail_action = DetailAction()

    create_action = CreateAction()
    update_action = UpdateAction()
    delete_action = DeleteAction()

    extra_actions = {}

    default_action_permissions = None
