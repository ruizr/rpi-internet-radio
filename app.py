import json
import time
import threading
import subprocess
import urllib.request
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

STATIONS = [
    {"name": "El Conquistador", "url": "https://stream10.usastreams.com/9314/stream"},
    {"name": "T13 Radio", "url": "http://icecast.teletrece.cl/t13radio.mp3"},
    {"name": "Radio ADN", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/ADN.mp3"},
    {"name": "Radio Bio-Bio", "url": "https://unlimited4-us.dps.live/biobiosantiago/mp3/icecast.audio"},
    {"name": "Radio Concierto", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/CONCIERTO.mp3"},
    {"name": "Radio Futuro", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/FUTURO.mp3"},
	{"name": "El Conquistador", "url": "https://stream10.usastreams.com/9314/stream"},
]

WMO_ICONS = {
    0: "☀️ Despejado", 1: "🌤️ Algo nublado", 2: "⛅ Nublado parcial", 3: "☁️ Nublado",
    45: "🌫️ Niebla", 48: "🌫️ Niebla", 51: "🌦️ Llovizna", 53: "🌦️ Llovizna",
    61: "🌧️ Lluvia leve", 63: "🌧️ Lluvia", 65: "🌧️ Lluvia fuerte",
    80: "🌦️ Chubascos", 81: "🌧️ Chubascos", 95: "⛈️ Tormenta"
}

weather_cache = {"data": None, "ts": 0}

def get_weather():
    now = time.time()
    if weather_cache["data"] and (now - weather_cache["ts"] < 1800):
        return weather_cache["data"]
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        "latitude=-33.59&longitude=-70.70"
        "&current=temperature_2m,weather_code"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min"
        "&timezone=America%2FSantiago&forecast_days=2"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            raw = json.loads(resp.read().decode())
        cur_temp = round(raw["current"]["temperature_2m"])
        cur_desc = WMO_ICONS.get(raw["current"]["weather_code"], "🌤️ Variable")
        today_max = round(raw["daily"]["temperature_2m_max"][0])
        today_min = round(raw["daily"]["temperature_2m_min"][0])

        tom_desc = WMO_ICONS.get(raw["daily"]["weather_code"][1], "🌤️ Variable")
        tom_max = round(raw["daily"]["temperature_2m_max"][1])
        tom_min = round(raw["daily"]["temperature_2m_min"][1])

        data = {
            "today": {"temp": f"{cur_temp}°", "desc": cur_desc, "range": f"{today_min}° / {today_max}°"},
            "tomorrow": {"desc": tom_desc, "range": f"{tom_min}° / {tom_max}°"},
        }
        weather_cache["data"] = data
        weather_cache["ts"] = now
        return data
    except Exception:
        return weather_cache["data"] or {
            "today": {"temp": "--°", "desc": "Sin datos", "range": "-- / --"},
            "tomorrow": {"desc": "Sin datos", "range": "-- / --"},
        }

HTML = """<!DOCTYPE html>
<html lang="es" translate="no" class="notranslate">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RPi Radio</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }
  body.night { filter: brightness(0.25); }
  body { background: #111827; color: #f9fafb; display: flex; flex-direction: column; height: 100vh; padding: 8px; gap: 8px; }
  .header { background: #1f2937; border-radius: 10px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #374151; gap: 8px; }
  .info { min-width: 0; flex: 1; }
  .status { font-size: 11px; color: #34d399; font-weight: bold; text-transform: uppercase; }
  .now-playing { font-size: 16px; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .clock { font-size: 26px; font-weight: bold; color: #facc15; letter-spacing: 1px; font-variant-numeric: tabular-nums; }
  .btn-play { background: #2563eb; color: white; border: none; border-radius: 8px; padding: 8px 14px; font-size: 14px; font-weight: bold; cursor: pointer; min-width: 78px; }
  .btn-play.paused { background: #dc2626; }
  .main { display: flex; flex: 1; gap: 8px; min-height: 0; }
  .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; flex: 1; overflow-y: auto; }
  .station { background: #1f2937; color: #e5e7eb; border: 2px solid #374151; border-radius: 10px; font-size: 14px; font-weight: bold; cursor: pointer; padding: 6px; text-align: center; }
  .station.active { background: #065f46; border-color: #10b981; color: #ffffff; }
  .weather-col { width: 138px; display: flex; flex-direction: column; gap: 8px; }
  .w-card { flex: 1; background: #1f2937; border: 1px solid #374151; border-radius: 10px; padding: 8px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; }
  .w-label { font-size: 11px; font-weight: bold; color: #93c5fd; text-transform: uppercase; margin-bottom: 2px; }
  .w-temp { font-size: 18px; font-weight: bold; color: #f9fafb; line-height: 1.1; }
  .w-desc { font-size: 14px; font-weight: bold; color: #d1d5db; margin-top: 3px; line-height: 1.15; }
  .w-range { font-size: 18px; font-weight: bold; color: #fbbf24; margin-top: 4px; }
</style>
</head>
<body>
  <div class="header">
    <div class="info">
      <div class="status" id="state">DETENIDO</div>
      <div class="now-playing" id="title">Selecciona una radio</div>
    </div>
    <div class="clock" id="clock">--:--</div>
    <button class="btn-play" id="toggleBtn" onclick="togglePlay()">PLAY</button>
  </div>
  <div class="main">
    <div class="grid">
      {% for s in stations %}
      <button class="station" id="st-{{ loop.index0 }}" onclick="playStation({{ loop.index0 }})">{{ s.name }}</button>
      {% endfor %}
    </div>
    <div class="weather-col">
      <div class="w-card">
        <div class="w-label">Hoy</div>
        <div class="w-temp" id="w-today-temp">--°</div>
        <div class="w-desc" id="w-today-desc">Cargando...</div>
        <div class="w-range" id="w-today-range">-- / --</div>
      </div>
      <div class="w-card">
        <div class="w-label">Mañana</div>
        <div class="w-desc" id="w-tom-desc">Cargando...</div>
        <div class="w-range" id="w-tom-range">-- / --</div>
      </div>
    </div>
  </div>
<script>
  async function playStation(idx) {
    const res = await fetch('/play/' + idx, { method: 'POST' });
    updateUI(await res.json());
  }
  async function togglePlay() {
    const res = await fetch('/toggle', { method: 'POST' });
    updateUI(await res.json());
  }
  async function refresh() {
    try {
      const res = await fetch('/status?t=' + Date.now());
      updateUI(await res.json());
    } catch (e) {}
  }
  async function refreshWeather() {
    try {
      const res = await fetch('/weather?t=' + Date.now());
      const w = await res.json();
      document.getElementById('w-today-temp').innerText = w.today.temp;
      document.getElementById('w-today-desc').innerText = w.today.desc;
      document.getElementById('w-today-range').innerText = w.today.range;
      document.getElementById('w-tom-desc').innerText = w.tomorrow.desc;
      document.getElementById('w-tom-range').innerText = w.tomorrow.range;
    } catch (e) {}
  }
  function updateUI(data) {
    document.getElementById('state').innerText = data.playing ? 'EN VIVO' : 'EN PAUSA';
    document.getElementById('title').innerText = data.station || 'Sin emisora';
    const btn = document.getElementById('toggleBtn');
    btn.innerText = data.playing ? 'PAUSE' : 'PLAY';
    btn.classList.toggle('paused', !data.playing);
    document.querySelectorAll('.station').forEach((el, i) => el.classList.toggle('active', i === data.index));
  }
  function updateClock() {
    const now = new Date();
    document.getElementById('clock').innerText = now.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
    const mins = now.getHours() * 60 + now.getMinutes();
    const isNight = mins >= 23 * 60 || mins < 7 * 60 + 30;
    document.body.classList.toggle('night', isNight);
  }
  setInterval(updateClock, 1000);
  updateClock();
  setInterval(refresh, 2000);
  refresh();
  setInterval(refreshWeather, 600000);
  refreshWeather();
</script>
</body>
</html>"""

current_index = 0

def get_status():
    try:
        out = subprocess.check_output(["mpc", "-f", "%file%", "status"], text=True)
    except Exception:
        out = ""
    playing = "[playing]" in out
    idx = current_index
    for i, s in enumerate(STATIONS):
        if s["url"] in out:
            idx = i
            break
    station = STATIONS[idx]["name"] if 0 <= idx < len(STATIONS) else ""
    return {"playing": playing, "station": station, "index": idx}

@app.route("/")
def index():
    return render_template_string(HTML, stations=STATIONS)

@app.route("/status")
def status():
    return jsonify(get_status())

@app.route("/weather")
def weather():
    return jsonify(get_weather())

@app.route("/play/<int:idx>", methods=["POST"])
def play(idx):
    global current_index
    if 0 <= idx < len(STATIONS):
        current_index = idx
        subprocess.run(["mpc", "clear"], check=False)
        subprocess.run(["mpc", "add", STATIONS[idx]["url"]], check=False)
        subprocess.run(["mpc", "play"], check=False)
    return jsonify(get_status())

@app.route("/toggle", methods=["POST"])
def toggle():
    subprocess.run(["mpc", "toggle"], check=False)
    return jsonify(get_status())

def auto_play():
    time.sleep(3)
    play(0)

threading.Thread(target=auto_play, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
