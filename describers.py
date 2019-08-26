from copy import deepcopy

from actions import Retrieve, CreateAction, ListAction, DetailAction, UpdateAction, DeleteAction
from datatypes import model_type_mapping, ModelType


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

            # add own copy of each container into the describer and inject information to them
            cls.retrieve = deepcopy(cls.retrieve)
            cls.retrieve.set_describer(cls)

            cls._actions = []

            if cls.list_action is not None:
                cls.list_action = deepcopy(cls.list_action)
                cls.list_action.set_retrieve(cls.retrieve)
                cls._actions.append(cls.list_action)

            if cls.detail_action is not None:
                cls.detail_action = deepcopy(cls.detail_action)
                cls.detail_action.set_retrieve(cls.retrieve)
                cls._actions.append(cls.detail_action)

            if cls.create_action is not None:
                cls.create_action = deepcopy(cls.create_action)
                cls.create_action.set_describer(cls)
                cls._actions.append(cls.create_action)

            if cls.update_action is not None:
                cls.update_action = deepcopy(cls.update_action)
                cls.update_action.set_describer(cls)
                cls._actions.append(cls.update_action)

            if cls.delete_action is not None:
                cls.delete_action = deepcopy(cls.delete_action)
                cls.delete_action.set_describer(cls)
                cls._actions.append(cls.delete_action)

        return cls


class Describer(metaclass=DescriberMeta):
    @classmethod
    def is_abstract(cls):
        return cls.model is None

    @classmethod
    def get_actions(cls):
        return cls._actions

    model = None

    default_page_size = None
    max_page_size = None

    retrieve = Retrieve()

    list_action = ListAction()
    detail_action = DetailAction()

    create_action = CreateAction()
    update_action = UpdateAction()
    delete_action = DeleteAction()
