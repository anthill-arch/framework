from tornado.template import BaseLoader, Template
import os


class Loader(BaseLoader):
    """A template loader that loads from a single root directory."""

    def __init__(self, root_directory, session=None, **kwargs):
        super().__init__(**kwargs)
        self._root_directory = root_directory
        self.session = session

    def resolve_path(self, name, parent_path=None):
        if parent_path and not parent_path.startswith("<") and \
                not parent_path.startswith("/") and \
                not name.startswith("/"):
            current_path = os.path.join(self.root, parent_path)
            file_dir = os.path.dirname(os.path.abspath(current_path))
            relative_path = os.path.abspath(os.path.join(file_dir, name))
            if relative_path.startswith(self.root):
                name = relative_path[len(self.root) + 1:]
        return name

    def _create_template(self, name):
        path = os.path.join(self.root, name)
        with open(path, "rb") as f:
            template = Template(f.read(), name=name, loader=self)
            return template

    @property
    def root(self):
        if self.session is not None:
            root_directory = self.session.get('template_path', self._root_directory)
        else:
            root_directory = self._root_directory
        return os.path.abspath(root_directory)
