from anthill.framework.core.management.templates import TemplateCommand
from importlib import import_module
import os


class StartProject(TemplateCommand):
    help = description = (
        "Creates an Anthill project directory structure for the given project "
        "name in the current directory or optionally in the given directory."
    )

    def __init__(self, root_templates_mod=None):
        super().__init__()
        self.root_templates_mod = root_templates_mod

    def run(self, **options):
        try:
            options['template'] = os.path.join(
                import_module(self.root_templates_mod).__path__[0], 'project_template')
        except (ImportError, AttributeError):
            pass

        project_name = options.pop('name')
        target = options.pop('directory')
        super().run('project', project_name, target, **options)
