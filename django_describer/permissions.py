from django.utils.translation import ugettext_lazy as _

from .utils import AttrDict


class BasePermission:
    def permission_statement(self):
        raise NotImplementedError

    def has_permission(self):
        for clas in reversed(self.__class__.__mro__):
            if clas in (object, BasePermission, Permission, OrResolver):
                continue
            if not clas.permission_statement(self):
                return False
        return True

    def error_message(self):
        return _("You don't have permission to do this.")


class Permission(BasePermission):
    def __init__(self, request, obj=None, data=None, qs=None):
        self.request = request
        self.obj = obj

        if data is None:
            self.data = AttrDict()
        elif isinstance(data, dict):
            self.data = AttrDict(data)
        else:
            self.data = data

        self.qs = qs


class OrResolver(Permission):
    def __init__(self, permission_classes, request, obj=None, data=None, qs=None):
        super().__init__(request=request, obj=obj, data=data, qs=qs)
        self.permission_classes = permission_classes
        self.errors = []

    def has_permission(self):
        for permission_class in self.permission_classes:
            pc = permission_class(self.request, obj=self.obj, data=self.data, qs=self.qs)
            if pc.has_permission():
                return True
            self.errors.append(pc.error_message())
        return False

    def error_message(self):
        err = str(self.errors[0])
        for i in range(1, len(self.errors)):
            err += " "
            err += str(_("OR"))
            err += " "
            err += str(self.errors[i])
        return err


class Or:
    def __init__(self, *permissions):
        self.permissions = permissions

    def __call__(self, request, obj=None, data=None, qs=None):
        return OrResolver(self.permissions, request, obj=obj, data=data, qs=qs)


class AllowAll(Permission):
    def permission_statement(self):
        return True


class AllowNone(Permission):
    def permission_statement(self):
        return False


class IsAuthenticated(Permission):
    def permission_statement(self):
        return self.request.user and self.request.user.is_authenticated

    def error_message(self):
        return _("Log in to access this.")
