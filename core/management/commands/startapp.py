from anthill.framework.core.management import Option
from anthill.framework.core.management.utils import get_random_secret_key, get_random_color
from anthill.framework.core.management.templates import TemplateCommand
from importlib import import_module
import os


class StartApplication(TemplateCommand):
    help = description = (
        "Creates an Anthill app directory structure for the given app name in "
        "the current directory or optionally in the given directory."
    )

    def __init__(self, root_templates_mod=None):
        super().__init__()
        self.root_templates_mod = root_templates_mod
        self.default_host = 'localhost'

    def get_options(self):
        options = super().get_options()
        options += (
            Option('-h', '--host', default=self.default_host, help='Server hostname.'),
            Option('-p', '--port', required=True, help='Server port number.'),
        )
        return options

    def run(self, **options):
        try:
            options['template'] = os.path.join(
                import_module(self.root_templates_mod).__path__[0], 'app_template')
        except (ImportError, AttributeError):
            pass

        entity_name = options.pop('name')
        target = options.pop('directory')

        # Create a random SECRET_KEY to put it in the main settings.
        options['secret_key'] = get_random_secret_key()

        options['app_color'] = get_random_color()
        options['server_hostname'] = options.pop('host')
        options['server_port'] = options.pop('port')

        super().run('app', entity_name, target, **options)
