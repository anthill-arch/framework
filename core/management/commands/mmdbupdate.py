from anthill.framework.core.management import Command, Option
import requests
import tarfile
import functools
import time
import os

products = ['City', 'Country']
link_base = 'http://geolite.maxmind.com/download/geoip/database'
link_tpl = '/'.join([link_base, 'GeoLite2-%(product)s.tar.gz'])
links = [link_tpl % {'product': product} for product in products]

CHUNK_SIZE = 1024
PROGRESS_WIDTH = 50
DB_EXT = '.mmdb'


def _progress(message, width=PROGRESS_WIDTH, logger=None):
    def decorator(func):

        @functools.wraps(func)
        def wrapper(*args_, **kwargs_):
            dots = width - len(message) - 7
            if logger is None:
                print('  \\_ %s %s' % (message, '.' * dots), end=' ')
            func(*args_, **kwargs_)
            if logger is None:
                print('OK')
            else:
                logger.info('  \\_ %s %s OK' % (message, '.' * dots))

        return wrapper
    return decorator


def _get_names(link, base):
    arc_name = link.rpartition('/')[-1]
    db_name = arc_name.partition('.')[0] + DB_EXT

    return (
        os.path.join(base, arc_name),
        os.path.join(base, db_name)
    )


def update(base, logger=None):
    ts = int(time.time())
    for link in links:
        arc_name, db_name = _get_names(link, base)

        if logger is not None:
            logger.info('* %s' % link)
        else:
            print('* %s' % link)

        @_progress('Create backup', logger=logger)
        def backup():
            if os.path.isfile(db_name):
                name_parts = list(os.path.splitext(db_name))
                name_parts.insert(-1, '.%s' % ts)
                new_name = ''.join(name_parts)
                os.rename(db_name, new_name)

        @_progress('Downloading', logger=logger)
        def download():
            resp = requests.get(link, stream=True)
            with open(arc_name, 'wb') as af:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    af.write(chunk)

        @_progress('Extracting', logger=logger)
        def extract():
            arc = tarfile.open(arc_name)
            for m in arc.getmembers():
                if m.name.endswith(DB_EXT):
                    with open(db_name, 'wb') as f:
                        f.write(arc.extractfile(m).read())
            arc.close()

        @_progress('Cleanup', logger=logger)
        def cleanup():
            os.unlink(arc_name)

        backup()
        download()
        extract()
        cleanup()


class GeoIPMMDBUpdate(Command):
    help = description = 'Creates or updates geoip2 mmdb databases.'
    option_list = (
        Option('-p', '--path', default='', help='Path where files to save'),
    )

    def run(self, path):
        update(path)
