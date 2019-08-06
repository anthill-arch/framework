from sqlalchemy.ext.serializer import dumps, loads


class BaseSerializer:
    def loads(self, *args, **kwargs):
        raise NotImplementedError

    def dumps(self, *args, **kwargs):
        raise NotImplementedError


class DefaultSerializer(BaseSerializer):
    def loads(self, *args, **kwargs):
        return loads(*args, **kwargs)

    def dumps(self, *args, **kwargs):
        return dumps(*args, **kwargs)
