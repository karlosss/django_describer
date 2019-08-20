def create_permissions_check_method(field_name=None, permission_classes=()):
    """
    Generator of methods to check permissions for both ListFields and Fields.
    """

    def method(root, info, results=None, **kwargs):
        for permission_class in permission_classes:
            pc = permission_class(info.context, obj=root, qs=results)
            if not pc.has_permission():
                raise PermissionError(pc.error_message())

        # return only for non-list Fields
        if field_name and hasattr(root, field_name):
            return getattr(root, field_name)

    # necessary flag for ListFields
    method.permissions_check = True
    return method
