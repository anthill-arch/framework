def str_to_list(string, sep=',', options=None):
    """Convert string to list."""
    res = string.split(sep)
    options = options or {}
    if 'len' in options and options['len'] != len(res):
        raise ValueError(
            'Length %s is must, got %s' % (options['len'], len(res)))
    return res
