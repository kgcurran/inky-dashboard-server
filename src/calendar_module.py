from ics import Calendar, Event
import requests
from datetime import datetime, timedelta, timezone, time
from dateutil.rrule import rrulestr
from zoneinfo import ZoneInfo
import os
import calendar_settings
from flask import current_app
utc_tz = ZoneInfo("UTC")


class CalendarEvent:
    # def __init__(self, color, start_day, start_time, end_day, end_time, text):
    def __init__(self, color, start_day, start_time, end_day, end_time, duration_minutes, text):
        self.color = color
        self.start_day = start_day
        self.start_time = start_time
        self.end_day = end_day
        self.end_time = end_time
        self.duration_minutes = duration_minutes
        self.text = text

def get_events_between(cal: Calendar, color: int, start_date: datetime, end_date: datetime, zone: ZoneInfo):
    '''Returns all events that occur between a specific start and end date as a list of CalendarEvent objects'''
    event_data = []
    variable_to_log = 42
    current_app.logger.debug(f"Variable value: {variable_to_log}")

    def get_day_time(date: datetime):
        date = date.astimezone(zone)
        return ((date - start_date.astimezone(zone)).days, date.hour * 100 + date.minute)

    def get_duration_minutes(start: datetime, end: datetime):
        # def get_duration_minutes(start_string, end_string):
        # start = datetime.fromisoformat(start_string)
        # end = datetime.fromisoformat(end_string)
        return round((end - start).total_seconds() // 60)

    for event in cal.events:
        rrule_found = False

        for extra in event.extra:
            if extra.name == "RRULE":
                current_app.logger.debug(f"event name: {event.name}")
                current_app.logger.debug(f"extra value: {extra.value}")
                current_app.logger.debug(f"event begin time: {event.begin.datetime}")
                # current_app.logger.debug(f"event: {dir(event)}")
                current_app.logger.debug(f"start_date: {start_date}")
                current_app.logger.debug(f"end_date: {end_date}")
                current_app.logger.debug(f"end_date_utc: {end_date.astimezone(utc_tz)}")
                # current_app.logger.debug(f"end_date stuff: {dir(end_date)}")
                # if the event is recurring, add every occurrence that lands between the start and end date
                # app.logger.debug("The value of my_variable is: %s", end_date)
                rrule = extra.value
                current_app.logger.debug(f"rrule: {rrule}")
                rule = rrulestr(rrule, dtstart=event.begin.datetime)
                current_app.logger.debug(f"rule: {rule}")

                current_app.logger.debug(f"rule stuff: {dir(rule)}")
                if rule._until and rule._until.tzinfo is not None:
                    current_app.logger.debug(f"rule until: {rule._until}")
                    current_app.logger.debug(f"rule until tzinfo: {rule._until.tzinfo}")
                    rule._until = rule._until.astimezone(timezone.utc)
                    current_app.logger.debug(f"rule until 2: {rule._until}")


                for occurrence_start in rule.between(start_date.astimezone(timezone.utc), end_date.astimezone(timezone.utc),inc=True):
                    occurrence_end = occurrence_start + (event.end.datetime - event.begin.datetime)
                    # event_data.append((color, *get_day_time(occurrence_start), *get_day_time(occurrence_end), event.name))
                    event_data.append((color, *get_day_time(occurrence_start), *get_day_time(occurrence_end), get_duration_minutes(occurrence_start, occurrence_end), event.name))
                rrule_found = True
                break

        if not rrule_found and event.begin <= end_date and start_date <= event.end:
            event_data.append((color, *get_day_time(event.begin), *get_day_time(event.end), get_duration_minutes(event.begin, event.end), event.name))
            # event_data.append((color, *get_day_time(event.begin), *get_day_time(event.end), event.name))

    return list(map(lambda edata: CalendarEvent(*edata), event_data))

def get_events_within_days_of_date(cal: Calendar, color: int, start_date: datetime, days: int):
    zone = calendar_settings.timezone
    start_of_today = datetime.combine(start_date, time.min, tzinfo=zone)

    return get_events_between(cal, color, start_of_today, start_of_today + timedelta(days=days), zone)

def get_all_events(start_date: datetime, days: int = 2):
    all_events = []

    for cal_data in calendar_settings.calendars:
        try:
            response = requests.get(cal_data[0], timeout=(5, 10))
            response.raise_for_status()
        except requests.RequestException as exc:
            current_app.logger.warning("Failed to fetch calendar %s: %s", cal_data[0], exc)
            continue
        cal = Calendar(response.text)
        all_events.extend(get_events_within_days_of_date(cal, cal_data[1], start_date, days))

    return all_events

def get_date_strings(start_date: datetime, days: int = 2):
    zone = calendar_settings.timezone
    current = datetime.combine(start_date, time.min, tzinfo=zone)

    strings = []

    for _ in range(days):
        strings.append(current.strftime("%A, %b %-d"))
        current += timedelta(days=1)

    return strings