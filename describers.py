from copy import deepcopy

from actions import Retrieve, CreateAction, ListDetailAction
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

            if cls.list_action is not None:
                cls.list_action = deepcopy(cls.list_action)
                cls.list_action.set_retrieve(cls.retrieve)

            if cls.detail_action is not None:
                cls.detail_action = deepcopy(cls.detail_action)
                cls.detail_action.set_retrieve(cls.retrieve)

        return cls


class Describer(metaclass=DescriberMeta):
    @classmethod
    def is_abstract(cls):
        return cls.model is None

    model = None

    default_page_size = None
    max_page_size = None

    retrieve = Retrieve()

    list_action = ListDetailAction()
    detail_action = ListDetailAction()
