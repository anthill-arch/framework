from anthill.framework.core.management import Command, Option
import code
import os


class Shell(Command):
    """
    Runs a Python shell inside application context.

    :param banner: banner appearing at top of shell when started
    :param make_context: a callable returning a dict of variables
                         used in the shell namespace. By default
                         returns a dict consisting of just the app.
    :param use_ptipython: use PtIPython shell if available, ignore if not.
                          The PtIPython shell can be turned off in command
                          line by passing the **--no-ptipython** flag.
    :param use_ptpython: use PtPython shell if available, ignore if not.
                         The PtPython shell can be turned off in command
                         line by passing the **--no-ptpython** flag.
    :param use_bpython: use BPython shell if available, ignore if not.
                        The BPython shell can be turned off in command
                        line by passing the **--no-bpython** flag.
    :param use_ipython: use IPython shell if available, ignore if not.
                        The IPython shell can be turned off in command
                        line by passing the **--no-ipython** flag.
    """

    banner = ''

    help = description = 'Runs a Python shell inside application context.'

    def __init__(self, banner=None, make_context=None, use_ipython=True,
                 use_bpython=True, use_ptipython=True, use_ptpython=True):
        super().__init__()

        self.banner = banner or self.banner
        self.use_ipython = use_ipython
        self.use_bpython = use_bpython
        self.use_ptipython = use_ptipython
        self.use_ptpython = use_ptpython

        from anthill.framework.apps import app

        if make_context is None:
            make_context = lambda: dict(app=app)

        self.make_context = make_context

        if not self.banner:
            self.banner = 'Application %s_v%s' % (app.label, app.version)

    def get_options(self):
        return (
            Option('--no-ipython', action="store_true", dest='no_ipython', default=(not self.use_ipython),
                   help="Do not use the IPython shell"),
            Option('--no-bpython', action="store_true", dest='no_bpython', default=(not self.use_bpython),
                   help="Do not use the BPython shell"),
            Option('--no-ptipython', action="store_true", dest='no_ptipython', default=(not self.use_ptipython),
                   help="Do not use the PtIPython shell"),
            Option('--no-ptpython', action="store_true", dest='no_ptpython', default=(not self.use_ptpython),
                   help="Do not use the PtPython shell"),
        )

    def get_context(self):
        """
        Returns a dict of context variables added to the shell namespace.
        """
        return self.make_context()

    def run(self, no_ipython, no_bpython, no_ptipython, no_ptpython):
        """
        Runs the shell.
        If no_ptipython is False or use_ptipython is True, then a PtIPython shell is run (if installed).
        If no_ptpython is False or use_ptpython is True, then a PtPython shell is run (if installed).
        If no_bpython is False or use_bpython is True, then a BPython shell is run (if installed).
        If no_ipython is False or use_python is True then a IPython shell is run (if installed).
        """

        context = self.get_context()

        if not no_ptipython:
            # Try PtIPython
            try:
                from ptpython.ipython import embed
                history_filename = os.path.expanduser('~/.ptpython_history')
                embed(banner1=self.banner, user_ns=context, history_filename=history_filename)
                return
            except ImportError:
                pass

        if not no_ptpython:
            # Try PtPython
            try:
                from ptpython.repl import embed
                history_filename = os.path.expanduser('~/.ptpython_history')
                embed(globals=context, history_filename=history_filename)
                return
            except ImportError:
                pass

        if not no_bpython:
            # Try BPython
            try:
                from bpython import embed
                embed(banner=self.banner, locals_=context)
                return
            except ImportError:
                pass

        if not no_ipython:
            # Try IPython
            try:
                from IPython import embed
                embed(banner1=self.banner, user_ns=context)
                return
            except ImportError:
                pass

        # Use basic python shell
        code.interact(self.banner, local=context)
