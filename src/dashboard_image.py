"""Pillow-based renderer for the 800x480 dashboard image used by the Inky Frame.

Mirrors the HTML/CSS layout in templates/dashboard.html and static/css/styles.css.
No browser dependency — runs on a Raspberry Pi with only Pillow + system fonts.
"""

from PIL import Image, ImageDraw, ImageFont

INKY_PALETTE = [
    (0, 0, 0),        # 0 BLACK
    (255, 255, 255),  # 1 WHITE
    (0, 255, 0),      # 2 GREEN
    (0, 0, 255),      # 3 BLUE
    (255, 0, 0),      # 4 RED
    (255, 255, 0),    # 5 YELLOW
    (255, 140, 0),    # 6 ORANGE
]


def quantize_to_inky(img):
    """Reduce the image to the Inky Frame's 7-color palette with Floyd-Steinberg dither."""
    flat = []
    for r, g, b in INKY_PALETTE:
        flat.extend((r, g, b))
    flat.extend([0] * (256 * 3 - len(flat)))
    palette_img = Image.new("P", (1, 1))
    palette_img.putpalette(flat)
    rgb = img.convert("RGB") if img.mode != "RGB" else img
    return rgb.quantize(palette=palette_img, dither=Image.Dither.FLOYDSTEINBERG)

W, H = 800, 480
LEFT_W = 300
HEADER_H = 96
HOUR_PX = 32
HOUR_COL_W = 36
DAY_HEADER_H = 26
ALLDAY_ROW_H = 16
FRAME_BORDER = 2

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
ORANGE = (255, 140, 0)

HEADER_BG = BLUE
HEADER_TEXT = WHITE
META = WHITE
DARK = BLACK
SUB = BLACK
TASK_DIVIDER = BLACK
GRID = BLACK
FRAME = BLACK
HOUR_TEXT = BLACK
DAY_HEADER_TEXT = BLACK

EVENT_COLORS = {
    0: BLACK,
    1: WHITE,
    2: GREEN,
    3: BLUE,
    4: RED,
    5: YELLOW,
    6: ORANGE,
}
LIGHT_EVENT_COLORS = {1, 2, 5}

FONT_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]
FONT_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def _load(size, bold=False):
    for path in (FONT_BOLD if bold else FONT_REGULAR):
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _truncate(draw, text, font, max_w):
    if draw.textlength(text, font=font) <= max_w:
        return text
    ellipsis = "…"
    while text and draw.textlength(text + ellipsis, font=font) > max_w:
        text = text[:-1]
    return (text + ellipsis) if text else ""


def render(header, tasks, calendar, time_range):
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    f_day = _load(56, bold=True)
    f_dow = _load(20, bold=True)
    f_my = _load(13)
    f_task = _load(12, bold=True)
    f_sub = _load(10)
    f_hd = _load(11, bold=True)
    f_hour = _load(10)
    f_event = _load(12, bold=True)

    _draw_left(d, header, tasks, f_day, f_dow, f_my, f_task, f_sub)
    _draw_right(d, calendar, time_range, f_hd, f_hour, f_event)

    return img


def _draw_left(d, header, tasks, f_day, f_dow, f_my, f_task, f_sub):
    d.rectangle([(0, 0), (LEFT_W, HEADER_H)], fill=HEADER_BG)

    day_text = header["d"]
    d.text((16, 18), day_text, font=f_day, fill=WHITE)
    day_w = d.textlength(day_text, font=f_day)
    meta_x = 16 + day_w + 12
    d.text((meta_x, 26), header["w"], font=f_dow, fill=WHITE)
    d.text((meta_x, 56), header["s"], font=f_my, fill=META)

    y = HEADER_H + 4
    task_h = 42
    max_w = LEFT_W - 32
    for task in tasks:
        if y + task_h > H:
            break
        title = _truncate(d, task.get("txt", ""), f_task, max_w)
        sub = _truncate(d, task.get("sub", ""), f_sub, max_w)
        d.text((16, y + 6), title, font=f_task, fill=DARK)
        d.text((16, y + 24), sub, font=f_sub, fill=SUB)
        y_end = y + task_h
        d.line([(8, y_end), (LEFT_W - 8, y_end)], fill=TASK_DIVIDER, width=1)
        y = y_end


def _draw_right(d, calendar, time_range, f_hd, f_hour, f_event):
    _draw_calendar(
        d, calendar, time_range,
        x0=LEFT_W, y0=0, x1=W, y1=H,
        day_header_h=DAY_HEADER_H,
        hour_col_w=HOUR_COL_W,
        allday_row_h=ALLDAY_ROW_H,
        f_hd=f_hd, f_hour=f_hour, f_event=f_event,
        hour_px=HOUR_PX,
        event_top_pad=1,
    )


def _draw_calendar(d, calendar, time_range, *, x0, y0, x1, y1,
                   day_header_h, hour_col_w, allday_row_h,
                   f_hd, f_hour, f_event, hour_px=None, event_top_pad=3):
    d.rectangle(
        [(x0, y0), (x1 - 1, y1 - 1)],
        outline=FRAME,
        width=FRAME_BORDER,
    )

    days = calendar.get("dh", [])
    n_days = max(len(days), 1)

    body_x = x0 + FRAME_BORDER + hour_col_w
    body_x_end = x1 - FRAME_BORDER
    body_w = body_x_end - body_x
    day_w = body_w / n_days

    body_y = y0 + FRAME_BORDER + day_header_h
    body_y_end = y1 - FRAME_BORDER

    for i, day in enumerate(days):
        cx = body_x + day_w * (i + 0.5)
        bbox = d.textbbox((0, 0), day, font=f_hd)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        d.text(
            (cx - text_w / 2, y0 + FRAME_BORDER + (day_header_h - text_h) / 2 - 2),
            day,
            font=f_hd,
            fill=DAY_HEADER_TEXT,
        )

    d.line([(x0 + FRAME_BORDER, body_y), (body_x_end, body_y)], fill=GRID, width=1)
    d.line([(body_x, body_y), (body_x, body_y_end)], fill=GRID, width=1)
    for i in range(1, n_days):
        x_div = body_x + day_w * i
        d.line([(x_div, body_y), (x_div, body_y_end)], fill=GRID, width=1)
        d.line([(x_div, y0 + FRAME_BORDER), (x_div, body_y)], fill=GRID, width=1)

    if not time_range:
        return
    first_hour = time_range[0] // 100

    allday_counts = [0] * n_days
    for ev in calendar.get("ev", []):
        if not ev.get("ad"):
            continue
        sd = ev.get("sd", 0)
        ed = ev.get("ed", sd + 1)
        for day_index in range(max(sd, 0), min(ed, n_days)):
            allday_counts[day_index] += 1
    max_allday = max(allday_counts) if allday_counts else 0
    allday_h = max_allday * allday_row_h + (2 if max_allday else 0)

    grid_y = body_y + allday_h

    if hour_px is None:
        n_intervals = max(1, len(time_range) - 1)
        hour_px = (body_y_end - grid_y) / n_intervals

    rendered = [0] * n_days
    for ev in calendar.get("ev", []):
        if not ev.get("ad"):
            continue
        sd = ev.get("sd", 0)
        ed = ev.get("ed", sd + 1)
        for day_index in range(max(sd, 0), min(ed, n_days)):
            row = rendered[day_index]
            col_x0 = body_x + day_w * day_index
            ex0 = col_x0 + 1
            ex1 = col_x0 + day_w - 1
            ey0 = body_y + 1 + row * allday_row_h
            ey1 = ey0 + allday_row_h - 1
            color = EVENT_COLORS.get(ev.get("co", 0), (100, 100, 100))
            text_color = DARK if ev.get("co") in LIGHT_EVENT_COLORS else WHITE
            d.rectangle([(ex0, ey0), (ex1, ey1)], fill=color)
            title = _truncate(d, ev.get("txt", ""), f_event, ex1 - ex0 - 8)
            d.text((ex0 + 4, ey0 + 1), title, font=f_event, fill=text_color)
            rendered[day_index] = row + 1

    for time in time_range:
        hour = time // 100
        y_h = grid_y + (hour - first_hour) * hour_px
        if y_h > body_y_end:
            break
        d.line([(body_x, y_h), (body_x_end, y_h)], fill=GRID, width=1)
        label = str(hour % 12 or 12)
        bbox = d.textbbox((0, 0), label, font=f_hour)
        tw = bbox[2] - bbox[0]
        d.text(
            (body_x - 5 - tw, y_h + 1),
            label,
            font=f_hour,
            fill=HOUR_TEXT,
        )

    for ev in calendar.get("ev", []):
        if ev.get("ad"):
            continue
        sd = ev.get("sd", 0)
        if sd < 0 or sd >= n_days:
            continue
        sh, sm = ev["st"] // 100, ev["st"] % 100
        eh, em = ev["et"] // 100, ev["et"] % 100
        offset_min = (sh - first_hour) * 60 + sm
        duration_min = (eh - sh) * 60 + (em - sm)
        if duration_min <= 0:
            continue

        ey0 = grid_y + offset_min * hour_px / 60
        ey1 = ey0 + duration_min * hour_px / 60
        if ey1 <= grid_y or ey0 >= body_y_end:
            continue
        ey0 = max(ey0, grid_y + 1)
        ey1 = min(ey1, body_y_end - 1)

        col_x0 = body_x + day_w * sd
        lanes = max(int(ev.get("lanes", 1)), 1)
        lane = max(int(ev.get("lane", 0)), 0)
        lane_w = day_w / lanes
        ex0 = col_x0 + lane_w * lane + 1
        ex1 = col_x0 + lane_w * (lane + 1) - 1

        color = EVENT_COLORS.get(ev.get("co", 0), (100, 100, 100))
        text_color = DARK if ev.get("co") in LIGHT_EVENT_COLORS else WHITE
        d.rectangle([(ex0, ey0), (ex1, ey1)], fill=color)

        title = _truncate(d, ev.get("txt", ""), f_event, ex1 - ex0 - 8)
        d.text((ex0 + 4, ey0 + event_top_pad), title, font=f_event, fill=text_color)


W_P, H_P = 480, 800
DAY_HEADER_H_P = 36
HOUR_COL_W_P = 40
ALLDAY_ROW_H_P = 22


def render_portrait(calendar, time_range):
    img = Image.new("RGB", (W_P, H_P), WHITE)
    d = ImageDraw.Draw(img)
    f_hd = _load(14, bold=True)
    f_hour = _load(12)
    f_event = _load(18, bold=True)
    _draw_calendar(
        d, calendar, time_range,
        x0=0, y0=0, x1=W_P, y1=H_P,
        day_header_h=DAY_HEADER_H_P,
        hour_col_w=HOUR_COL_W_P,
        allday_row_h=ALLDAY_ROW_H_P,
        f_hd=f_hd, f_hour=f_hour, f_event=f_event,
        hour_px=None,
    )
    return img
