from anthill.framework.core.management import Command


class Server(Command):
    """
    Runs the server i.e. app.run()
    """

    help = description = 'Runs the server i.e. app.run().'

    def __call__(self, app=None, *args, **kwargs):
        app.run(**kwargs)

    def run(self, *args, **kwargs):
        pass
