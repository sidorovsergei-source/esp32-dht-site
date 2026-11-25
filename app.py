from datetime import datetime, timezone
from hmac import compare_digest
import os

from flask import Flask, Response, render_template_string, request

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024
password = os.environ["SITE_PASSWORD"].encode()
token = f'Bearer {os.environ["INGEST_TOKEN"]}'.encode()
if len(password) < 16 or len(token) < 31:
    raise RuntimeError("Set SITE_PASSWORD (16+ bytes) and INGEST_TOKEN (24+ bytes)")

latest = None

PAGE = """<!doctype html>
<html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="15">
<title>Датчик воздуха</title>
<style>
body{margin:0;background:#edf4fa;color:#183049;font:18px system-ui;padding:24px}
main{margin:auto;max-width:480px;background:white;border-radius:16px;padding:24px}
h1{font-size:26px;margin-top:0} strong{font-size:28px}
</style>
<main><h1>Датчик воздуха</h1>
{% if reading %}
<p>Температура<br><strong>{{ reading[0] }} °C</strong></p>
<p>Влажность<br><strong>{{ reading[1] }} %</strong></p>
<p>Последнее измерение: {{ reading[2].strftime('%H:%M:%S %d.%m.%Y') }} UTC.</p>
{% if stale %}<p>Больше двух минут без новых показаний.</p>{% endif %}
{% else %}<p>Ждём первую отправку от ESP32.</p>{% endif %}
</main></html>"""


@app.after_request
def disable_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def dashboard():
    auth = request.authorization
    if (auth is None or auth.type != "basic" or auth.username != "sensor"
            or not compare_digest((auth.password or "").encode(), password)):
        return Response("Введи логин sensor и пароль от сайта.", status=401,
                        headers={"WWW-Authenticate": 'Basic realm="DHT", charset="UTF-8"'})
    reading = latest
    stale = reading is not None and (
        datetime.now(timezone.utc) - reading[2]).total_seconds() > 120
    return render_template_string(PAGE, reading=reading, stale=stale)


@app.post("/api/readings")
def ingest():
    global latest
    if not compare_digest(request.headers.get("Authorization", "").encode(), token):
        return "", 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return "", 400
    temperature = data.get("temperature")
    humidity = data.get("humidity")
    if (type(temperature) not in (int, float) or not -40 <= temperature <= 85
            or type(humidity) not in (int, float) or not 0 <= humidity <= 100):
        return "", 400
    latest = (temperature, humidity, datetime.now(timezone.utc))
    return "", 204
