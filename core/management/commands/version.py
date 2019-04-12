from anthill.framework.core.management import Command


class Version(Command):
    help = description = 'Show app version and exit.'

    # noinspection PyMethodOverriding
    def __call__(self, app):
        print('Application %s v%s' % (app.label, app.version))

    def run(self, *args, **kwargs):
        pass
