import json
from anthill.framework.utils.serializer import AnthillJSONEncoder
from .base import BaseSerializer


class JSONSerializer(BaseSerializer):
    def dumps(self, value):
        return json.dumps(value, cls=AnthillJSONEncoder).encode()

    def loads(self, value):
        return json.loads(value.decode())
