from anthill.framework.core.management import Command, Option


class ApplicationChooser(Command):
    help = description = 'Choose application for administration.'
    option_list = (
        Option('name', help='Name of the application.'),
    )

    def run(self, *args, **kwargs):
        pass
