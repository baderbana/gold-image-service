import io
import os
import math
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATE_FILES = {
    "SAR": "template_SAR.png.jpeg",
    "EGP": "template_EGP.png.jpeg",
    "AED": "template_AED.png.jpeg",
    "KWD": "template_KWD.png.jpeg",
}

CURRENCY = {
    "SAR": {"name": "الريال السعودي"},
    "EGP": {"name": "الجنيه المصري"},
    "AED": {"name": "الدرهم الإماراتي"},
    "KWD": {"name": "الدينار الكويتي"},
}

KARATS = ["24", "22", "21", "18", "14", "9"]

REFERENCE_W = 865
REFERENCE_H = 1536

# إحداثيات مستقلة لكل قالب.
# كل مستطيل يحدد مكان الرقم فقط داخل خانة السعر.
LAYOUTS = {
    "SAR": {
        "prices": [
            (545, 473, 720, 543),
            (545, 589, 720, 659),
            (545, 706, 720, 777),
            (545, 824, 720, 895),
            (545, 942, 720, 1022),
            (545, 1060, 720, 1133),
        ],
        "date": (410, 390, 528, 420),
        "time": (608, 389, 727, 425),
    },

    "EGP": {
        "prices": [
            (530, 498, 735, 584),
            (530, 615, 735, 700),
            (530, 733, 735, 819),
            (530, 872, 735, 958),
            (530, 990, 735, 1095),
            (530, 1116, 735, 1222),
        ],
        "date": (420, 410, 530, 445),
        "time": (615, 408, 735, 465),
    },

    "AED": {
        "prices": [
            (497, 523, 710, 606),
            (497, 644, 710, 727),
            (497, 765, 710, 847),
            (497, 884, 710, 967),
            (497, 1004, 710, 1087),
            (497, 1120, 710, 1205),
        ],
        "date": (455, 445, 575, 480),
        "time": (650, 443, 780, 485),
    },

    "KWD": {
        "prices": [
            (500, 534, 730, 621),
            (500, 650, 730, 737),
            (500, 770, 730, 858),
            (500, 890, 730, 977),
            (500, 1010, 730, 1098),
            (500, 1127, 730, 1215),
        ],
        "date": (440, 455, 580, 495),
        "time": (625, 448, 785, 500),
    },
}


def font(size, bold=False):
    path = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    return ImageFont.truetype(path, size)


def scale_box(coords, width, height):
    sx = width / REFERENCE_W
    sy = height / REFERENCE_H

    return (
        int(coords[0] * sx),
        int(coords[1] * sy),
        int(coords[2] * sx),
        int(coords[3] * sy),
    )


def fit_text(draw, text, max_width, start_size, bold=True):
    size = start_size

    while size > 12:
        fnt = font(size, bold)
        bbox = draw.textbbox((0, 0), text, font=fnt)

        if bbox[2] - bbox[0] <= max_width:
            return fnt

        size -= 1

    return font(12, bold)


def draw_centered(draw, text, coords, fill, start_size, bold=True):
    x1, y1, x2, y2 = coords

    fnt = fit_text(
        draw,
        text,
        x2 - x1 - 12,
        start_size,
        bold,
    )

    bbox = draw.textbbox((0, 0), text, font=fnt)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = x1 + ((x2 - x1) - text_width) // 2
    y = y1 + ((y2 - y1) - text_height) // 2 - bbox[1]

    draw.text((x, y), text, font=fnt, fill=fill)


@app.get("/health")
def health():
    missing = [
        name
        for name in TEMPLATE_FILES.values()
        if not os.path.isfile(os.path.join(BASE_DIR, name))
    ]

    return jsonify({
        "ok": not missing,
        "service": "gold-image-service",
        "missingTemplates": missing,
    }), (200 if not missing else 500)


@app.post("/render")
def render():
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("currencyCode", "SAR")).upper()

    if code not in CURRENCY:
        return jsonify({"error": "Unsupported currencyCode"}), 400

    template_path = os.path.join(BASE_DIR, TEMPLATE_FILES[code])

    if not os.path.isfile(template_path):
        return jsonify({
            "error": "Template file not found",
            "expectedFile": TEMPLATE_FILES[code],
        }), 500

    prices = payload.get("prices")

    if not isinstance(prices, dict):
        return jsonify({
            "error": "prices must be an object keyed by karat"
        }), 400

    try:
        img = Image.open(template_path).convert("RGB")
    except Exception as exc:
        return jsonify({
            "error": "Could not open template",
            "details": str(exc),
        }), 500

    width, height = img.size
    draw = ImageDraw.Draw(img)
    layout = LAYOUTS[code]

    price_color = (255, 244, 215)
    date_color = (255, 244, 215)

    # كتابة الأسعار داخل خاناتها فقط.
    for karat, coords in zip(KARATS, layout["prices"]):
        raw_price = prices.get(karat)

        try:
            number = float(raw_price)

            if not math.isfinite(number):
                raise ValueError("Invalid price")

            price_text = f"{number:,.2f}"

        except (TypeError, ValueError):
            price_text = "N/A"

        draw_centered(
            draw,
            price_text,
            scale_box(coords, width, height),
            price_color,
            max(22, int(width * 0.039)),
            bold=True,
        )

    # التاريخ والوقت: مساحات مستقلة لكل قالب.
    date_box = scale_box(layout["date"], width, height)
    time_box = scale_box(layout["time"], width, height)

    # تنظيف مساحة القيمة فقط، وليس عنوان التاريخ أو الوقت.
    background_color = img.getpixel((
        max(0, date_box[0]),
        max(0, date_box[1]),
    ))
    draw.rectangle(date_box, fill=background_color)

    background_color = img.getpixel((
        max(0, time_box[0]),
        max(0, time_box[1]),
    ))
    draw.rectangle(time_box, fill=background_color)

    now = datetime.now(ZoneInfo("Asia/Riyadh"))

    date_text = now.strftime("%Y/%m/%d")
    time_text = now.strftime("%I:%M %p")
    time_text = time_text.replace("AM", "ص").replace("PM", "م")

    draw_centered(
        draw,
        date_text,
        date_box,
        date_color,
        max(15, int(width * 0.020)),
        bold=True,
    )

    draw_centered(
        draw,
        time_text,
        time_box,
        date_color,
        max(15, int(width * 0.020)),
        bold=True,
    )

    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True)
    output.seek(0)

    return send_file(
        output,
        mimetype="image/png",
        download_name=f"gold-{code.lower()}.png",
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
    )
