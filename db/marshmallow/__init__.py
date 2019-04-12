"""
    db.marshmallow
    ~~~~~~~~~~~~~~~~~

    Integrates the marshmallow serialization/deserialization library
    with application.
"""
from marshmallow import fields as base_fields, exceptions, pprint
from . import fields, sqla
from .schema import Schema
import logging

__all__ = [
    'EXTENSION_NAME',
    'Marshmallow',
    'Schema',
    'fields',
    'exceptions',
    'pprint'
]

logger = logging.getLogger('anthill.application')

EXTENSION_NAME = 'marshmallow'


def _attach_fields(obj):
    """
    Attach all the marshmallow fields classes to ``obj``,
    including db.marshmallow's custom fields.
    """
    for attr in base_fields.__all__:
        if not hasattr(obj, attr):
            setattr(obj, attr, getattr(base_fields, attr))
    for attr in fields.__all__:
        setattr(obj, attr, getattr(fields, attr))


class Marshmallow:
    """
    Wrapper class that integrates Marshmallow with an application.

    To use it, instantiate with an application::

        ma = Marshmallow(app)

    The object provides access to the :class:`Schema` class,
    all fields in :mod:`marshmallow.fields`, as well as the specific
    fields in :mod:`marshmallow.fields`.

    You can declare schema like so::

        class BookSchema(ma.Schema):
            class Meta:
                fields = ('id', 'title', 'author', 'links')

            author = ma.Nested(AuthorSchema)

            links = ma.Hyperlinks({
                'self': ma.URLFor('book_detail', id='<id>'),
                'collection': ma.URLFor('book_list')
            })


    In order to integrate with db.sqlalchemy, this extension must by initialized *after*
    `~sqlalchemy.SQLAlchemy`. ::

            db = SQLAlchemy(app)
            ma = Marshmallow(app)

    This gives you access to `ma.ModelSchema`, which generates a marshmallow
    `~marshmallow.Schema` based on the passed in model. ::

        class AuthorSchema(ma.ModelSchema):
            class Meta:
                model = Author

    :param app: The application object.
    """

    def __init__(self, app=None):
        self.Schema = Schema
        self.ModelSchema = sqla.ModelSchema
        self.HyperlinkRelated = sqla.HyperlinkRelated
        _attach_fields(self)
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """
        Initializes the application with the extension.

        :param app: The application object.
        """
        sqlalchemy_ext = app.get_extension('sqlalchemy')

        db = sqlalchemy_ext.db
        self.ModelSchema.OPTIONS_CLASS.session = db.session
        app.extensions[EXTENSION_NAME] = self
        logger.debug('Marshmallow ext installed.')
