import io
import os
import math

from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATES = {
    "SAR": "template_SAR.png.jpeg",
    "EGP": "template_EGP.png.jpeg",
    "AED": "template_AED.png.jpeg",
    "KWD": "template_KWD.png.jpeg",
}

KARATS = ["24", "22", "21", "18", "14", "9"]

# مراكز خانات الأسعار في قالب السعودية الأصلي
# الإحداثيات محسوبة كنسب من أبعاد الصورة
PRICE_BOXES = [
    (0.728, 0.330),
    (0.728, 0.403),
    (0.728, 0.482),
    (0.728, 0.557),
    (0.728, 0.637),
    (0.728, 0.714),
]


def get_font(size):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]

    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "gold-image-service"
    })


@app.post("/render")
def render():
    payload = request.get_json(silent=True) or {}

    code = str(payload.get("currencyCode", "SAR")).upper()
    prices = payload.get("prices")

    if code not in TEMPLATES:
        return jsonify({"error": "Unsupported currencyCode"}), 400

    if not isinstance(prices, dict):
        return jsonify({
            "error": "prices must be an object keyed by karat"
        }), 400

    template_path = os.path.join(BASE_DIR, TEMPLATES[code])

    if not os.path.isfile(template_path):
        return jsonify({
            "error": "Template file not found",
            "expected_file": TEMPLATES[code]
        }), 500

    # فتح التصميم الأصلي دون إعادة رسم أي نص ثابت
    with Image.open(template_path) as source:
        img = source.convert("RGB")

    draw = ImageDraw.Draw(img)
    width, height = img.size

    # ضبط حجم الأرقام بحسب عرض الصورة
    font_size = max(20, int(width * 0.041))
    price_font = get_font(font_size)

    for index, karat in enumerate(KARATS):
        raw_price = prices.get(karat)

        try:
            number = float(raw_price)

            if not math.isfinite(number) or number < 0:
                raise ValueError("Invalid price")

            price_text = f"{number:.2f}"

        except (TypeError, ValueError):
            price_text = "--.--"

        x_ratio, y_ratio = PRICE_BOXES[index]
        x = int(width * x_ratio)
        y = int(height * y_ratio)

        # الأرقام فقط؛ العملة موجودة مسبقًا في القالب
        draw.text(
            (x, y),
            price_text,
            font=price_font,
            fill=(255, 244, 210),
            anchor="mm",
            stroke_width=0
        )

    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True)
    output.seek(0)

    return send_file(
        output,
        mimetype="image/png",
        download_name=f"gold-{code.lower()}.png"
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000"))
    )
