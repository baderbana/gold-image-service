import io
import os
import math
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

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


def arabic(text):
    return get_display(arabic_reshaper.reshape(str(text)), base_dir="R")


def font(size, bold=False):
    path = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    return ImageFont.truetype(path, size)


def draw_center(draw, center_x, y, text, fnt, fill, direction=None):
    rendered = arabic(text) if direction != "ltr" else str(text)
    box = draw.textbbox((0, 0), rendered, font=fnt)
    x = int(center_x - (box[2] - box[0]) / 2)
    draw.text((x, y), rendered, font=fnt, fill=fill)


def draw_fitted_center(draw, center_x, y, text, max_width, start_size, fill, bold=False, direction=None):
    size = start_size
    while size > 12:
        fnt = font(size, bold)
        rendered = arabic(text) if direction != "ltr" else str(text)
        box = draw.textbbox((0, 0), rendered, font=fnt)
        if box[2] - box[0] <= max_width:
            x = int(center_x - (box[2] - box[0]) / 2)
            draw.text((x, y), rendered, font=fnt, fill=fill)
            return
        size -= 1
    draw_center(draw, center_x, y, text, font(12, bold), fill, direction)


@app.get("/health")
def health():
    missing = [
        name for name in TEMPLATE_FILES.values()
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
        return jsonify({"error": "prices must be an object keyed by karat"}), 400

    try:
        img = Image.open(template_path).convert("RGB")
    except Exception as exc:
        return jsonify({"error": "Could not open template", "details": str(exc)}), 500

    W, H = img.size
    draw = ImageDraw.Draw(img)

    # ألوان متوافقة مع القالب الذهبي. نغطي فقط الخانات الديناميكية.
    gold = (255, 221, 130)
    cream = (255, 247, 225)
    dark = (13, 17, 17)

    # مراكز الخانات النسبية لقالب السعودية المرفوع (الصورة 864x1536).
    # يدعم اختلاف أبعاد القوالب باستخدام نسب مئوية من أبعاد الصورة.
    def xy(x, y):
        return (int(W * x / 864), int(H * y / 1536))

    # امسح النص التجريبي داخل مساحة التاريخ والوقت فقط، مع إبقاء عناوين القالب.
    # القالب يحتوي عناوين "التاريخ" و"وقت التحديث" أعلى القيم.
    date_box = (xy(365, 365), xy(535, 420))
    time_box = (xy(590, 365), xy(735, 435))
    draw.rectangle((date_box[0][0], date_box[0][1], date_box[1][0], date_box[1][1]), fill=dark)
    draw.rectangle((time_box[0][0], time_box[0][1], time_box[1][0], time_box[1][1]), fill=dark)

    now = datetime.now(ZoneInfo("Asia/Riyadh"))
    date_text = now.strftime("%Y/%m/%d")
    time_text = now.strftime("%I:%M %p").replace("AM", "ص").replace("PM", "م")

    draw_fitted_center(
        draw, W * 0.515, H * 0.255,
        date_text, W * 0.17, max(16, int(W * 0.019)),
        cream, bold=True, direction="ltr",
    )
    draw_fitted_center(
        draw, W * 0.765, H * 0.255,
        time_text, W * 0.15, max(16, int(W * 0.019)),
        cream, bold=True,
    )

    # خانات الأسعار داخل المستطيلات الفارغة في القالب.
    # كل مستطيل: اكتب الرقم فقط، واترك العملة وعبارة "سعر الجرام" الثابتتين.
    price_centers = [
        (0.725, 0.339),
        (0.725, 0.416),
        (0.725, 0.493),
        (0.725, 0.570),
        (0.725, 0.647),
        (0.725, 0.724),
    ]
    for karat, (cx, cy) in zip(KARATS, price_centers):
        raw = prices.get(karat)
        try:
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError("Invalid price")
            text = f"{value:,.2f}"
        except (TypeError, ValueError):
            text = "N/A"

        # تغطية داخل مربع السعر فقط ثم رسم الرقم في المنتصف.
        center_x = int(W * cx)
        center_y = int(H * cy)
        box_w = int(W * 0.22)
        box_h = int(H * 0.045)
        draw.rounded_rectangle(
            (
                center_x - box_w // 2,
                center_y - box_h // 2,
                center_x + box_w // 2,
                center_y + box_h // 2,
            ),
            radius=max(8, int(W * 0.012)),
            fill=(61, 48, 28),
            outline=(204, 157, 58),
            width=max(2, int(W * 0.002)),
        )
        draw_fitted_center(
            draw, center_x, center_y - int(H * 0.014),
            text, box_w - 10, max(18, int(W * 0.036)),
            cream, bold=True, direction="ltr",
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
