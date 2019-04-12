import marshmallow as ma

sentinel = object()


class Schema(ma.Schema):
    """
    Base serializer with which to define custom serializers.
    See `marshmallow.Schema` for more details about the `Schema` API.
    """

    def get_data(self, obj, many=sentinel, *args, **kwargs):
        """
        Return the serialized data.

        :param obj: Object to serialize.
        :param bool many: Whether `obj` should be serialized as an instance
            or as a collection. If unset, defaults to the value of the
            `many` attribute on this Schema.
        :param kwargs: Additional keyword arguments passed (not used yet).
        """
        if many is sentinel:
            many = self.many
        data = self.dump(obj, many=many).data
        return data
