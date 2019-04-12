from anthill.framework.core.management import Command
import os


class Clean(Command):
    """
    Remove *.pyc and *.pyo files recursively starting at current directory
    """

    def run(self):
        for dirpath, dirnames, filenames in os.walk('.'):
            for filename in filenames:
                if filename.endswith('.pyc') or filename.endswith('.pyo'):
                    full_pathname = os.path.join(dirpath, filename)
                    self.stdout.write('Removing %s' % full_pathname)
                    os.remove(full_pathname)
