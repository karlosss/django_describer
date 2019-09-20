def register_action_name(adapter, name):
    if not hasattr(adapter, "_action_names"):
        adapter._action_names = set()
    if name in adapter._action_names:
        raise ValueError("Duplicate action name: `{}`".format(name))
    adapter._action_names.add(name)


non_model_actions = []


def register_non_model_action(name, action):
    action.set_name(name)
    non_model_actions.append(action)


def generate(adapter):
    return adapter().generate()


