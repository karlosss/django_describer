from django.utils.translation import ugettext_lazy as _


class AttrDict(dict):
    def __getattr__(self, item):
        return self[item]


class Permission:
    def __init__(self, request, obj=None, data=None):
        self.request = request
        self.obj = obj
        self.data = AttrDict(data) if data else AttrDict()

    def has_permission(self):
        raise NotImplementedError

    def error_message(self):
        return _("You don't have permission to access this.")


class AllowAll(Permission):
    def has_permission(self):
        return True


class AllowNone(Permission):
    def has_permission(self):
        return False


class IsAuthenticated(Permission):
    def has_permission(self):
        return self.request.user and self.request.user.is_authenticated

    def error_message(self):
        return _("Log in to access this.")
