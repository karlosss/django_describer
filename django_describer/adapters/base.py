class Adapter:
    def string_type(self, type, **kwargs):
        raise NotImplementedError

    def integer_type(self, type, **kwargs):
        raise NotImplementedError

    def float_type(self, type, **kwargs):
        raise NotImplementedError

    def id_type(self, type, **kwargs):
        raise NotImplementedError

    def boolean_type(self, type, **kwargs):
        raise NotImplementedError

    def queryset_type(self, type, **kwargs):
        raise NotImplementedError

    def model_type(self, type, **kwargs):
        raise NotImplementedError

    def composite_type(self, type, **kwargs):
        raise NotImplementedError

    def list_action(self, action, **kwargs):
        raise NotImplementedError

    def detail_action(self, action, **kwargs):
        raise NotImplementedError

    def create_action(self, action, **kwargs):
        raise NotImplementedError

    def update_action(self, action, **kwargs):
        raise NotImplementedError

    def delete_action(self, action, **kwargs):
        raise NotImplementedError

    def custom_action(self, action, **kwargs):
        raise NotImplementedError

    def custom_object_action(self, action, **kwargs):
        raise NotImplementedError

    def generate(self, **kwargs):
        raise NotImplementedError
