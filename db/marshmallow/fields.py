"""
    marshmallow.fields
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Custom fields.

    See the `marshmallow.fields` module for the list of all fields
    available from the marshmallow library.
"""
from anthill.framework.utils.urls import reverse as url_for
from marshmallow.compat import iteritems
from marshmallow import fields

__all__ = [
    'URLFor',
    'AbsoluteURLFor',
    'Hyperlinks',
]


class URLFor(fields.Field):
    """
    Field that outputs the URL for an endpoint.

    Usage: ::

        url = URLFor('author_get', id='15')
        external_url = URLFor('author_get', id='15', external=True)

    :param str endpoint: Endpoint name.
    :param kwargs: Keyword arguments.
    """
    _CHECK_ATTRIBUTE = False

    def __init__(self, endpoint, **kwargs):
        self.endpoint = endpoint
        self.params = kwargs
        fields.Field.__init__(self, **kwargs)

    def _format(self, val):
        return val

    def _serialize(self, value, key, obj):
        """
        Output the URL for the endpoint, given the kwargs passed to ``__init__``.
        """
        return url_for(self.endpoint, **self.params)


class AbsoluteURLFor(URLFor):
    """Field that outputs the absolute URL for an endpoint."""

    def __init__(self, endpoint, **kwargs):
        kwargs['external'] = True
        URLFor.__init__(self, endpoint=endpoint, **kwargs)

    def _format(self, val):
        return val


def _rapply(d, func, *args, **kwargs):
    """
    Apply a function to all values in a dictionary or list of dictionaries, recursively.
    """
    if isinstance(d, (tuple, list)):
        return [_rapply(each, func, *args, **kwargs) for each in d]
    if isinstance(d, dict):
        return {
            key: _rapply(value, func, *args, **kwargs)
            for key, value in iteritems(d)
        }
    else:
        return func(d, *args, **kwargs)


def _url_val(val, key, obj, **kwargs):
    """
    Function applied by `HyperlinksField` to get the correct value in the schema.
    """
    if isinstance(val, URLFor):
        return val.serialize(key, obj, **kwargs)
    else:
        return val


class Hyperlinks(fields.Field):
    """
    Field that outputs a dictionary of hyperlinks,
    given a dictionary schema with :class:`~marshmallow.fields.URLFor`
    objects as values.

    Example: ::

        _links = Hyperlinks({
            'self': URLFor('author', id='<id>'),
            'collection': URLFor('author_list'),
            }
        })

    `URLFor` objects can be nested within the dictionary. ::

        _links = Hyperlinks({
            'self': {
                'href': URLFor('book', id='<id>'),
                'title': 'book detail'
            }
        })

    :param dict schema: A dict that maps names to
        :class:`~marshmallow.fields.URLFor` fields.
    """
    _CHECK_ATTRIBUTE = False

    def __init__(self, schema, **kwargs):
        self.schema = schema
        fields.Field.__init__(self, **kwargs)

    def _format(self, val):
        return val

    def _serialize(self, value, attr, obj):
        return _rapply(self.schema, _url_val, key=attr, obj=obj)
