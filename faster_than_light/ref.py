

def deref(host, ref_or_value):
    if isinstance(ref_or_value, Ref):
        path = get_host_path(ref_or_value)
        return get_host_value(host, path)
    else:
        return ref_or_value


def get_host_path(ref):

    path = []
    while ref._parent is not None:
        path.append(ref._name)
        ref = ref._parent

    return path[::-1]


def get_host_value(host, path):

    value = host
    for part in path:
        value = value[part]

    return value



class Ref(object):

    def __init__(self, parent, name):
        self._parent = parent
        self._name = name

    def __getattr__(self, name):
        ref = Ref(self, name)
        setattr(self, name, ref)
        return ref
