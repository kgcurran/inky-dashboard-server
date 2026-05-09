from flask import Flask, jsonify, render_template, request, send_file
from calendar_module import get_all_events, get_date_strings
from todoist_module import get_todo_items
from datetime import datetime
from io import BytesIO
import hashlib
import json
import os
import dashboard_image
from cbor2 import dumps
import calendar_settings

calendar_days = 2
min_time = 700
max_time = 2000
time_range = list(range(min_time, max_time + 1, 100))

def _to_minutes(hhmm):
    return (hhmm // 100) * 60 + (hhmm % 100)


def assign_event_lanes(events):
    """Place events into lanes so overlapping events sit side-by-side within a day column.

    Mutates each event dict in `events`, setting `lane` (0-indexed column inside the cluster)
    and `lanes` (total columns in the cluster). Non-overlapping events get lane=0, lanes=1.
    """
    by_day = {}
    for ev in events:
        by_day.setdefault(ev["sd"], []).append(ev)

    for day_events in by_day.values():
        day_events.sort(key=lambda e: (_to_minutes(e["st"]), _to_minutes(e["et"])))

        cluster = []
        cluster_end = -1

        def flush(cluster):
            lane_ends = []
            for ev in cluster:
                start = _to_minutes(ev["st"])
                placed = False
                for i, end in enumerate(lane_ends):
                    if end <= start:
                        ev["lane"] = i
                        lane_ends[i] = _to_minutes(ev["et"])
                        placed = True
                        break
                if not placed:
                    ev["lane"] = len(lane_ends)
                    lane_ends.append(_to_minutes(ev["et"]))
            total = len(lane_ends)
            for ev in cluster:
                ev["lanes"] = total

        for ev in day_events:
            start = _to_minutes(ev["st"])
            end = _to_minutes(ev["et"])
            if cluster and start < cluster_end:
                cluster.append(ev)
                cluster_end = max(cluster_end, end)
            else:
                if cluster:
                    flush(cluster)
                cluster = [ev]
                cluster_end = end
        if cluster:
            flush(cluster)


def build_dashboard_data():
    now = datetime.now(calendar_settings.timezone)

    header_payload = {
        "d": now.strftime("%d"),
        "w": now.strftime("%A"),
        "s": now.strftime("%B %Y"),
    }

    events = get_all_events(now, calendar_days)
    event_payload = []
    for event in events:
        event_payload.append({
            "co": event.color,
            "dm": event.duration_minutes,
            "sd": event.start_day,
            "st": event.start_time,
            "ed": event.end_day,
            "et": event.end_time,
            "txt": event.text,
            "ad": event.all_day,
            "lane": 0,
            "lanes": 1,
        })
    assign_event_lanes([ev for ev in event_payload if not ev["ad"]])

    allday_counts = [0] * calendar_days
    for ev in event_payload:
        if ev["ad"]:
            for day_index in range(max(ev["sd"], 0), min(ev["ed"], calendar_days)):
                allday_counts[day_index] += 1
    max_allday = max(allday_counts) if allday_counts else 0

    calendar_payload = {
        "dh": get_date_strings(now, calendar_days),
        "ev": event_payload,
        "max_allday": max_allday,
    }

    tasks_payload = [
        {"txt": task.text, "sub": task.subtext}
        for task in get_todo_items(now)
    ]

    return header_payload, tasks_payload, calendar_payload


app = Flask(__name__)

@app.route("/")
def cbor_endpoint():
    header_payload, tasks_payload, calendar_payload = build_dashboard_data()
    cbor_events = [
        {
            "co": ev["co"],
            "sd": ev["sd"],
            "st": ev["st"],
            "ed": ev["ed"],
            "et": ev["et"],
            "txt": ev["txt"],
        }
        for ev in calendar_payload["ev"]
    ]
    payload = {
        "hd": header_payload,
        "cal": {"dh": calendar_payload["dh"], "ev": cbor_events},
        "tsk": tasks_payload,
    }
    return dumps(payload)


@app.route("/home")
@app.route("/dashboard.html")
def dashboard_html():
    header_payload, tasks_payload, calendar_payload = build_dashboard_data()
    return render_template(
        'dashboard.html',
        time_range=time_range,
        header=header_payload,
        tasks=tasks_payload,
        calendar=calendar_payload,
    )


def _compute_version(header, tasks, calendar, palette):
    blob = json.dumps(
        {"h": header, "t": tasks, "c": calendar, "p": palette or ""},
        sort_keys=True,
        default=str,
    )
    return hashlib.md5(blob.encode("utf-8")).hexdigest()


@app.route("/dashboard.png")
def dashboard_png():
    palette = request.args.get("palette")
    header_payload, tasks_payload, calendar_payload = build_dashboard_data()
    version = _compute_version(header_payload, tasks_payload, calendar_payload, palette)
    etag = f'"{version}"'

    if request.if_none_match.contains(version):
        return ("", 304, {"ETag": etag, "Cache-Control": "no-cache"})

    img = dashboard_image.render(header_payload, tasks_payload, calendar_payload, time_range)
    if palette == "inky":
        img = dashboard_image.quantize_to_inky(img)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    response = send_file(
        buf,
        mimetype="image/png",
        as_attachment=False,
        download_name="dashboard.png",
        max_age=0,
    )
    response.set_etag(version)
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/dashboard.version")
def dashboard_version():
    palette = request.args.get("palette")
    header_payload, tasks_payload, calendar_payload = build_dashboard_data()
    version = _compute_version(header_payload, tasks_payload, calendar_payload, palette)
    response = jsonify({"version": version})
    response.set_etag(version)
    response.headers["Cache-Control"] = "no-cache"
    return response


if __name__=='__main__':
   app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
