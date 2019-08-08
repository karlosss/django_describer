def generate(adapter):
    return adapter().generate()


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

    def list_type(self, type, **kwargs):
        raise NotImplementedError

    def model_type(self, type, **kwargs):
        raise NotImplementedError

    def generate(self, **kwargs):
        raise NotImplementedError
