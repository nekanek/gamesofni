import time
import datetime


DEBUGGING = False


def get_unix_time_of_event(event):
    # scheduled format
    return str(int(time.mktime(datetime.datetime.strptime(
        event.get('time'), '%Y-%m-%dT%H:%M:%SZ').timetuple())))


def get_unix_time_from_date(date):
    # create_game command format
    return str(int(time.mktime(datetime.datetime.strptime(date, '%d-%m-%y %H:%M').timetuple())))


def get_formatted_time(unix_time):
    return time.strftime('%H:%M %m/%d/%Y', time.gmtime(unix_time))


def get_utc_time(timestamp, offset):
    offset_seconds = int(offset) * 60 * 60
    return timestamp - offset_seconds


def get_local_time(timestamp, offset):
    offset_seconds = int(offset) * 60 * 60
    return timestamp + offset_seconds


class VcgException(Exception):
    pass
