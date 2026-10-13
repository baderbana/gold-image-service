import io
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

W, H = 1080, 1350

BG = (12, 20, 18)
GOLD = (226, 187, 92)
CREAM = (247, 235, 202)
MUTED = (190, 183, 155)

CURRENCY = {
    "SAR": {"name": "الريال السعودي"},
    "EGP": {"name": "الجنيه المصري"},
    "AED": {"name": "الدرهم الإماراتي"},
    "KWD": {"name": "الدينار الكويتي"},
}


def font(size, bold=False):
    path = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )

    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def center(draw, y, text, fnt, fill):
    box = draw.textbbox(
        (0, 0),
        text,
        font=fnt,
        direction="rtl",
        language="ar",
    )

    x = (W - (box[2] - box[0])) // 2

    draw.text(
        (x, y),
        text,
        font=fnt,
        fill=fill,
        direction="rtl",
        language="ar",
    )


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "gold-image-service",
    })


@app.post("/render")
def render():
    payload = request.get_json(silent=True) or {}

    code = str(payload.get("currencyCode", "SAR")).upper()

    if code not in CURRENCY:
        return jsonify({
            "error": "Unsupported currencyCode"
        }), 400

    prices = payload.get("prices")

    if not isinstance(prices, dict):
        return jsonify({
            "error": "prices must be an object keyed by karat"
        }), 400

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # إطار التصميم
    d.rounded_rectangle(
        (26, 26, W - 26, H - 26),
        radius=30,
        outline=GOLD,
        width=3,
    )

    d.rounded_rectangle(
        (43, 43, W - 43, H - 43),
        radius=25,
        outline=(80, 73, 48),
        width=2,
    )

    # علامة مائية نصية
    d.text(
        (W // 2 - 330, H // 2 - 25),
        "ASK BADR",
        font=font(68, True),
        fill=(32, 39, 31),
    )

    d.text(
        (W // 2 - 280, H // 2 + 38),
        "GOLD PRICE",
        font=font(42, True),
        fill=(32, 39, 31),
    )

    # العنوان والعملة
    center(
        d, 70,
        "أسعار الذهب اليوم",
        font(58, True),
        GOLD,
    )

    center(
        d, 155,
        f"{CURRENCY[code]['name']} ({code})",
        font(31, True),
        CREAM,
    )

    now = datetime.now(ZoneInfo("Asia/Riyadh"))

    center(
        d, 215,
        f"{now.strftime('%Y-%m-%d  %H:%M')}  |  توقيت مكة",
        font(25),
        MUTED,
    )

    # معالم زخرفية مختلفة لكل عملة
    sy = 335

    d.line(
        (90, sy + 70, W - 90, sy + 70),
        fill=GOLD,
        width=3,
    )

    if code == "SAR":
        # مبانٍ ومعلم هندسي مستوحى من أفق الرياض
        d.rectangle(
            (245, sy - 5, 330, sy + 70),
            outline=GOLD,
            width=4,
        )

        d.rectangle(
            (750, sy - 5, 835, sy + 70),
            outline=GOLD,
            width=4,
        )

        d.polygon(
            [
                (465, sy + 70),
                (480, sy - 15),
                (505, sy - 45),
                (530, sy - 15),
                (545, sy + 70),
            ],
            outline=GOLD,
        )

        d.ellipse(
            (490, sy - 32, 520, sy - 2),
            outline=GOLD,
            width=4,
        )

    elif code == "EGP":
        # أهرامات مصر
        d.polygon(
            [(360, sy + 70), (465, sy - 30), (570, sy + 70)],
            outline=GOLD,
        )

        d.polygon(
            [(500, sy + 70), (625, sy - 55), (750, sy + 70)],
            outline=GOLD,
        )

    elif code == "AED":
        # برج طويل مستوحى من أفق دبي
        d.polygon(
            [
                (470, sy + 70),
                (500, sy - 85),
                (515, sy - 140),
                (530, sy - 85),
                (560, sy + 70),
            ],
            outline=GOLD,
        )

        for x, h in [
            (300, 70),
            (370, 95),
            (650, 80),
            (730, 60),
        ]:
            d.rectangle(
                (x, sy + 70 - h, x + 42, sy + 70),
                outline=GOLD,
                width=3,
            )

    else:
        # أبراج الكويت بشكل زخرفي
        for x, h in [
            (360, 100),
            (445, 135),
            (530, 115),
            (615, 150),
            (700, 95),
        ]:
            d.rectangle(
                (x, sy + 70 - h, x + 40, sy + 70),
                outline=GOLD,
                width=3,
            )

    center(
        d, 425,
        "سعر الجرام حسب العيار",
        font(34, True),
        CREAM,
    )

    # الأسعار المرسلة من n8n
    for i, karat in enumerate(["24", "22", "21", "18", "14", "9"]):
        y = 490 + i * 100

        d.rounded_rectangle(
            (95, y, W - 95, y + 78),
            radius=18,
            fill=(22, 31, 25),
            outline=(96, 78, 40),
            width=2,
        )

        d.text(
            (W - 145, y + 17),
            f"عيار {karat}",
            font=font(31, True),
            fill=CREAM,
            anchor="ra",
            direction="rtl",
            language="ar",
        )

        raw_price = prices.get(karat)

        try:
            price_number = float(raw_price)

            if not __import__("math").isfinite(price_number):
                raise ValueError("Invalid price")

            price = f"{price_number:.2f} {code}"

        except (TypeError, ValueError):
            price = "غير متوفر"

        d.text(
            (135, y + 17),
            price,
            font=font(30, True),
            fill=GOLD,
        )

    # التذييل
    center(
        d, 1135,
        "أسعار تقديرية للجرام ولا تشمل المصنعية أو الضرائب",
        font(22),
        MUTED,
    )

    center(
        d, 1180,
        "تتحدث الأرقام عند طلب السعر من البوت",
        font(22),
        MUTED,
    )

    center(
        d, 1240,
        "Ask Badr about the price of gold",
        font(20, True),
        GOLD,
    )

    # إخراج صورة PNG
    output = io.BytesIO()

    img.save(
        output,
        format="PNG",
        optimize=True,
    )

    output.seek(0)

    return send_file(
        output,
        mimetype="image/png",
        download_name=f"gold-{code.lower()}.png",
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )
