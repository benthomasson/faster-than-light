import os


def ensure_directory(d):
    d = os.path.abspath(os.path.expanduser(d))
    if not os.path.exists(d):
        os.makedirs(d)
    return d


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
