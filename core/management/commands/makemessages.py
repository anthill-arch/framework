from anthill.framework.core.management import Command


class MakeMessages(Command):
    help = description = (
        "Runs over the entire project and "
        "pulls out all strings marked for translation. It creates (or updates) a message "
        "file in locale (for applications) directory.\n\nYou must run this command with one of either the "
        "--locale, --exclude, or --all options."
    )

    def run(self):
        pass
