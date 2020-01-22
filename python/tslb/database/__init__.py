from contextlib import contextmanager
import threading
import sqlalchemy
import sqlalchemy.orm
from tslb import settings

thlocal = threading.local()

# Read the db config
if 'Database' not in settings:
    raise Exception('No \'Database\' section in the tslb settings file.')

ds = settings['Database']

if 'host' not in ds or 'db_name' not in ds or 'user' not in ds or 'password' not in ds:
    raise Exception('host, db_name, user or password on specified in the tslb settings file.')

db_host = ds['host']
db_name = ds['db_name']
db_user = ds['user']
db_password = ds['password']

del ds


class conn(object):
    """
    A singleton thread local DB connection wrapper
    """
    def get_session():
        if getattr(thlocal, 'db_sessionmaker', None) is None:
            url = 'postgresql://%s:%s@%s/%s' % (db_user, db_password, db_host, db_name)
            engine = sqlalchemy.create_engine(url)
            thlocal.db_sessionmaker = sqlalchemy.orm.sessionmaker(bind=engine)

        return thlocal.db_sessionmaker()

def get_session():
    return conn.get_session()

@contextmanager
def session_scope():
    s = get_session()
    try:
        yield s
        s.commit()
    except:
        s.rollback()
        raise
    finally:
        s.close()
