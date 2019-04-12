"""
    db.marshmallow.sqla
    ~~~~~~~~~~~~~~~~~~~~~~

    Integration with db.sqlalchemy and marshmallow-sqlalchemy.
    Provides `ModelSchema <marshmallow_sqlalchemy.ModelSchema>` classes
    that use the scoped session from SQLALchemy.
"""
from six.moves.urllib import parse
import marshmallow_sqlalchemy as msqla
from marshmallow.exceptions import ValidationError
from .schema import Schema


class DummySession(object):
    """Placeholder session object."""


class SchemaOpts(msqla.ModelSchemaOpts):
    """
    Schema options for `~marshmallow.sqla.ModelSchema`.
    Same as `marshmallow_sqlalchemy.SchemaOpts`, except that we add a
    placeholder `DummySession` if ``sqla_session`` is not defined on
    class Meta. The actual session from `sqlalchemy` gets bound
    in `~marshmallow.Marshmallow.init_app`.
    """
    session = DummySession()

    def __init__(self, meta, **kwargs):
        if not hasattr(meta, 'sqla_session'):
            meta.sqla_session = self.session
        super(SchemaOpts, self).__init__(meta, **kwargs)


class ModelSchema(msqla.ModelSchema, Schema):
    """
    ModelSchema that generates fields based on the `model`
    class Meta option, which should be a ``db.Model`` class from `~sqlalchemy`.
    Uses the scoped session from db.sqlalchemy by default.

    See `marshmallow_sqlalchemy.ModelSchema` for more details
    on the `ModelSchema` API.
    """
    OPTIONS_CLASS = SchemaOpts


# noinspection PyProtectedMember
class HyperlinkRelated(msqla.fields.Related):
    """
    Field that generates hyperlinks to indicate references between models,
    rather than primary keys.

    :param str endpoint: Endpoint name for generated hyperlink.
    :param bool external: Set to `True` if absolute URLs should be used,
                          instead of relative URLs.
    """

    def __init__(self, endpoint, external=False, **kwargs):
        super(HyperlinkRelated, self).__init__(**kwargs)
        self.endpoint = endpoint
        self.external = external

    def _serialize(self, value, attr, obj):
        from anthill.framework.utils.urls import reverse
        key = super(HyperlinkRelated, self)._serialize(value, attr, obj)
        return reverse(self.endpoint, external=self.external, *(key,))

    def _deserialize(self, value, *args, **kwargs):
        if self.external:
            parsed = parse.urlparse(value)
            value = parsed.path

        endpoint, kwargs = self.adapter.match(value)
        if endpoint != self.endpoint:
            raise ValidationError(
                (
                    'Parsed endpoint "{endpoint}" from URL "{value}"; expected "{self.endpoint}"'
                ).format(**locals())
            )
        if self.url_key not in kwargs:
            raise ValidationError(
                'URL pattern "{self.url_key}" not found in {kwargs!r}'.format(**locals())
            )

        return super(HyperlinkRelated, self)._deserialize(kwargs[self.url_key], *args, **kwargs)
