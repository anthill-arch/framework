from wtforms import FileField as _FileField
from anthill.framework.core.files import File
from wtforms.validators import DataRequired, StopValidation
from collections import Iterable


class FileField(_FileField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = None

    def process_formdata(self, valuelist):
        valuelist = (x for x in valuelist if isinstance(x, File) and x)
        data = next(valuelist, None)

        if data is not None:
            self.data = data
        else:
            self.raw_data = ()


class FileRequired(DataRequired):
    def __call__(self, form, field):
        if not (isinstance(field.data, File) and field.data):
            raise StopValidation(self.message or field.gettext(
                'This field is required.'))


file_required = FileRequired


class FileAllowed(object):
    def __init__(self, upload_set, message=None):
        self.upload_set = upload_set
        self.message = message

    def __call__(self, form, field):
        if not (isinstance(field.data, File) and field.data):
            return

        filename = field.data.name.lower()

        if isinstance(self.upload_set, Iterable):
            if any(filename.endswith('.' + x) for x in self.upload_set):
                return

            raise StopValidation(self.message or field.gettext(
                'File does not have an approved extension: {extensions}'
            ).format(extensions=', '.join(self.upload_set)))

        if not self.upload_set.file_allowed(field.data, filename):
            raise StopValidation(self.message or field.gettext(
                'File does not have an approved extension.'))


file_allowed = FileAllowed
