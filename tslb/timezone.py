import pytz
from datetime import datetime
from dateutil import tz

def now():
    return datetime.utcnow().replace(tzinfo=pytz.utc)

def localtime(d):
    return d.astimezone(tz.tzlocal())
