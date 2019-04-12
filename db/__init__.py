from sqlalchemy.ext.declarative import declarative_base
from anthill.framework.apps.builder import app
from anthill.framework.core.exceptions import ImproperlyConfigured
from anthill.framework.db.marshmallow import Marshmallow
from anthill.framework.db.sqlalchemy import (
    SQLAlchemy, DefaultMeta, Model as DefaultModel, BaseQuery)
from anthill.framework.db.sqlalchemy.activerecord import ActiveRecordMixin
from anthill.framework.db.management import Migrate
from anthill.framework.utils.translation import translate_lazy as _

__all__ = ['db', 'ma']


class Model(ActiveRecordMixin, DefaultModel):
    # def save(self, force_insert=False):
    #     if force_insert:
    #         self.session.add(self)
    #     self.session.flush()
    #     return self

    def dump(self):
        """Marshmallow default schema data dump."""
        model_schema = getattr(self, '__marshmallow__')
        return model_schema.dump(self)

    @classmethod
    def dump_many(cls, objects):
        model_schema = getattr(cls, '__marshmallow__')
        return model_schema(many=True).dump(objects)

    @classmethod
    def filter_by(cls, **kwargs):
        return cls.query.filter_by(**kwargs)

    @classmethod
    def get_or_create(cls, defaults=None, **kwargs):
        obj = cls.query.filter_by(**kwargs).first()
        if obj:
            return obj, False
        else:
            params = dict((k, v) for k, v in kwargs.iteritems())
            params.update(defaults or {})
            obj = cls(**params)
            return obj, True

    @classmethod
    def update_or_create(cls, defaults=None, **kwargs):
        obj = cls.query.filter_by(**kwargs).first()
        if obj:
            for key, value in defaults.iteritems():
                setattr(obj, key, value)
            created = False
        else:
            params = dict((k, v) for k, v in kwargs.iteritems())
            params.update(defaults or {})
            obj = cls(**params)
            created = True
        return obj, created


Base = declarative_base(cls=Model, metaclass=DefaultMeta, name='Model')

db = SQLAlchemy(app, query_class=BaseQuery, model_class=Base)
migrate = Migrate(app, db)
ma = Marshmallow(app)
