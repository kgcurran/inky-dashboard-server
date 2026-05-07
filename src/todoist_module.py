import calendar_settings
from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Task
from datetime import date, datetime, time, timezone

api = TodoistAPI(calendar_settings.todoist_api_key)

class TodoItem:
    def __init__(self, text, subtext):
        self.text = text
        self.subtext = subtext

def get_subtext(current: datetime, task: Task):
    if task.due is None:
        return "No Due Date"

    raw = task.due.date
    if isinstance(raw, datetime):
        dt = raw if raw.tzinfo else raw.replace(tzinfo=calendar_settings.timezone)
    else:
        dt = datetime.combine(raw, time.min, tzinfo=calendar_settings.timezone)

    dt = dt.astimezone(calendar_settings.timezone)
    current = current.astimezone(calendar_settings.timezone)

    month_day = dt.strftime("%b %d %I:%M %p")
    day_of_week = dt.strftime("%A")

    if current > dt:
        return f"{month_day} · Overdue"
    elif (dt - current).days == 1:
        return f"{month_day} · {day_of_week} · Today"
    elif (dt - current).days == 2:
        return f"{month_day} · {day_of_week} · Tomorrow"
    else:
        return f"{month_day} · {day_of_week}"

def get_todo_items(current: datetime, limit: int = 7):
    items = []

    for page in api.get_tasks():
        for task in page:
            items.append(TodoItem(
                task.content,
                get_subtext(current, task)
            ))
            if len(items) >= limit:
                return items

    return items