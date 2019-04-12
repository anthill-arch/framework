from anthill.framework.utils.duration import duration_iso_string
from anthill.framework.utils.functional import Promise
from anthill.framework.utils.timezone import is_aware
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import state
from tornado import escape
import datetime
import decimal
import json
import uuid


class AnthillJSONEncoder(json.JSONEncoder):
    """
    JSONEncoder subclass that knows how to encode date/time, decimal types, and
    UUIDs.
    """
    def default(self, o):
        # See "Date Time String Format" in the ECMA-262 specification.
        if isinstance(o, datetime.datetime):
            r = o.isoformat()
            if o.microsecond:
                r = r[:23] + r[26:]
            if r.endswith('+00:00'):
                r = r[:-6] + 'Z'
            return r
        elif isinstance(o, datetime.date):
            return o.isoformat()
        elif isinstance(o, datetime.time):
            if is_aware(o):
                raise ValueError("JSON can't represent timezone-aware times.")
            r = o.isoformat()
            if o.microsecond:
                r = r[:12]
            return r
        elif isinstance(o, datetime.timedelta):
            return duration_iso_string(o)
        elif isinstance(o, (decimal.Decimal, uuid.UUID, Promise)):
            return str(o)
        else:
            return super().default(o)


class AlchemyJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        def dump_sqlalchemy_obj(sqlalchemy_obj):
            fields = {}
            for field in [x for x in dir(sqlalchemy_obj)
                          if not x.startswith('_')  # sqlalch builtin attr
                             and not x.startswith('rel_')  # for my attr, which are references to other tbls
                             and x != 'metadata']:
                data = sqlalchemy_obj.__getattribute__(field)
                try:
                    # this will fail on non-encodable values, like other classes
                    # also deals with every type which has an `isoformat` attr, like
                    # datetime.datetime
                    if hasattr(data, 'isoformat'):
                        fields[field] = data.isoformat()
                    # # no need of this if we are not taking `rel_*` attrs
                    # elif isinstance(data.__class__, DeclarativeMeta): # an SQLAlchemy class
                    # fields[field] = dump_sqlalchemy_obj(data)
                    else:
                        fields[field] = dump_sqlalchemy_obj(data) if isinstance(data.__class__,
                                                                                DeclarativeMeta) else data
                except TypeError:
                    fields[field] = None
            # a json-encodable dict
            return fields

        if isinstance(obj, state.InstanceState):
            return None
        if isinstance(obj.__class__, DeclarativeMeta):  # an SQLAlchemy class
            return dump_sqlalchemy_obj(obj)
        if isinstance(obj, bytes):
            return escape.to_unicode(obj)
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)
