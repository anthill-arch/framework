# Originated from https://github.com/cuducos/alchemydumps.git
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from anthill.framework.core.management import Manager
from .autoclean import BackupAutoClean
from .backup import Backup
from .confirm import Confirm
from .database import AlchemyDumpsDatabase
import os


DatabaseDumpsCommand = Manager(usage='Backup and restore full SQL database.')


@DatabaseDumpsCommand.command
def create():
    """Create a backup based on SQLAlchemy mapped classes."""

    alchemy = AlchemyDumpsDatabase()
    data = alchemy.dumps()
    back = Backup()

    for class_name in data.keys():
        file_name = back.generate_filename(class_name)
        try:
            file_name = back.create_file(file_name, data[class_name])
        except:
            print('Error creating {} at {}'.format(
                file_name, back.storage.path(file_name)))
        else:
            rows = len(alchemy.loads(data[class_name]))
            print('{} rows from {} saved as {}'.format(
                rows, class_name, back.storage.path(file_name)))


@DatabaseDumpsCommand.command
def history():
    """List existing backups."""

    back = Backup()

    # if no files
    if not back.files:
        print('No backups found.')
        return

    # create output
    groups = [
        {'id': ts, 'files': back.by_timestamp(ts)}
        for ts in back.get_timestamps()
    ]

    for g in groups:
        if g['files']:
            date_formated = back.parse_timestamp(g['id'])
            print('\nID: {} (from {})'.format(g['id'], date_formated))
            for file_name in g['files']:
                print('    {}'.format(back.storage.path(file_name)))


@DatabaseDumpsCommand.option('-d', '--date', dest='date_id', default=False,
                             help='The date part of a file from the AlchemyDumps folder.')
def restore(date_id):
    """Restore a backup based on the date part of the backup files."""

    alchemy = AlchemyDumpsDatabase()
    back = Backup()

    # loop through mapped classes
    for mapped_class in alchemy.get_mapped_classes():
        class_name = mapped_class.__name__
        name = back.get_name(class_name, date_id)
        if back.storage.exists(name):
            # read file content
            content = back.read_file(name)
            fails = list()

            # restore to the db
            db = alchemy.db()
            for row in alchemy.loads(content):
                try:
                    db.session.merge(row)
                    db.session.commit()
                except (IntegrityError, InvalidRequestError):
                    db.session.rollback()
                    fails.append(row)

            # print summary
            status = 'partially' if len(fails) else 'totally'
            print('{} {} restored.'.format(name, status))
            for f in fails:
                print('    Restore of {} failed.'.format(f))
        else:
            msg = 'No file found for {} ({} does not exist).'
            print(msg.format(class_name, back.storage.path(name)))


@DatabaseDumpsCommand.option('-d', '--date', dest='date_id', default=False,
                             help='The date part of a file from the AlchemyDumps folder.')
@DatabaseDumpsCommand.option('-y', '--assume-yes', dest='assume_yes', action='store_true',
                             default=False, help='Assume `yes` for all prompts.')
def remove(date_id, assume_yes=False):
    """Remove a series of backup files based on the date part of the files."""

    back = Backup()

    # check if date/id is valid
    if back.valid(date_id):
        # list files to be deleted
        delete_list = tuple(back.by_timestamp(date_id))
        print('Do you want to delete the following files?')
        for name in delete_list:
            print('    {}'.format(back.storage.path(name)))

        # delete
        con = Confirm(assume_yes)
        if con.ask():
            for name in delete_list:
                back.delete_file(name)
                print('    {} deleted.'.format(name))
    else:
        print('Invalid id. Use "history" to list existing downloads.')


@DatabaseDumpsCommand.option('-y', '--assume-yes', dest='assume_yes', action='store_true',
                             default=False, help='Assume `yes` for all prompts.')
def autoclean(assume_yes=False):
    """
    Remove a series of backup files based on the following rules:
    * Keeps all the backups from the last 7 days
    * Keeps the most recent backup from each week of the last month
    * Keeps the most recent backup from each month of the last year
    * Keeps the most recent backup from each year of the remaining years
    """

    back = Backup()

    # check if there are backups
    if not back.files:
        print('No backups found.')
        return

    # get black and white list
    cleaning = BackupAutoClean(back.get_timestamps())
    white_list = cleaning.white_list
    black_list = cleaning.black_list

    if not black_list:
        print('No backup to be deleted.')
        return

    # print the list of files to be kept
    print('\n{} backups will be kept:'.format(len(white_list)))
    for date_id in white_list:
        date_formated = back.parse_timestamp(date_id)
        print('\n    ID: {} (from {})'.format(date_id, date_formated))
        for f in back.by_timestamp(date_id):
            print('    {}'.format(back.storage.path(f)))

    # print the list of files to be deleted
    delete_list = list()
    print('\n{} backups will be deleted:'.format(len(black_list)))
    for date_id in black_list:
        date_formated = back.parse_timestamp(date_id)
        print('\n    ID: {} (from {})'.format(date_id, date_formated))
        for f in back.by_timestamp(date_id):
            print('    {}'.format(back.storage.path(f)))
            delete_list.append(f)

    # delete
    con = Confirm(assume_yes)
    if con.ask():
        for name in delete_list:
            back.delete_file(name)
            print('    {} deleted.'.format(name))
