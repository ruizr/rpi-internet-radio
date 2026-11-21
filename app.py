import os
import json
import time
import threading
import subprocess
import urllib.request
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MP3_DIR = os.path.join(BASE_DIR, "mp3")
os.makedirs(MP3_DIR, exist_ok=True)

STATIONS = [
    {"name": "El Conquistador", "url": "https://stream10.usastreams.com/9314/stream"},
    {"name": "T13 Radio", "url": "http://icecast.teletrece.cl/t13radio.mp3"},
    {"name": "Radio ADN", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/ADN.mp3"},
    {"name": "Radio Bio-Bio", "url": "https://unlimited4-us.dps.live/biobiosantiago/mp3/icecast.audio"},
    {"name": "Radio Concierto", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/CONCIERTO.mp3"},
    {"name": "Radio Futuro", "url": "https://playerservices.streamtheworld.com/api/livestream-redirect/FUTURO.mp3"},
    {"name": "Radio FM tiempo", "url": "https://mdstrm.com/audio/639b7943e0a27908a55dbf9e/icecast.audio"},
]

WMO_ICONS = {
    0: "☀️ Despejado", 1: "🌤️ Algo nublado", 2: "⛅ Nublado parcial", 3: "☁️ Nublado",
    45: "🌫️ Niebla", 48: "🌫️ Niebla", 51: "🌦️ Llovizna", 53: "🌦️ Llovizna",
    61: "🌧️ Lluvia leve", 63: "🌧️ Lluvia", 65: "🌧️ Lluvia fuerte",
    80: "🌦️ Chubascos", 81: "🌧️ Chubascos", 95: "⛈️ Tormenta"
}

weather_cache = {"data": None, "ts": 0}
current_index = 0
active_tab = "radio"
last_activity = time.time()
SCREENSAVER_TIMEOUT = 300

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

def get_local_tracks():
    exts = (".mp3", ".m4a", ".flac")
    tracks = []
    for root, _, files in os.walk(MP3_DIR):
        for f in sorted(files):
            if f.lower().endswith(exts):
                rel = os.path.relpath(os.path.join(root, f), MP3_DIR)
                tracks.append(rel.replace("\\", "/"))
    return sorted(tracks)

HTML = r"""<!DOCTYPE html>
<html lang="es" translate="no" class="notranslate">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RPi Radio & Music</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }
  body.night { filter: brightness(0.25); }
  body { background: #111827; color: #f9fafb; display: flex; flex-direction: column; height: 100vh; padding: 8px; gap: 8px; }
  .header { background: #1f2937; border-radius: 10px; padding: 6px 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #374151; gap: 6px; }
  .info { min-width: 0; flex: 1; }
  .status { font-size: 10px; color: #34d399; font-weight: bold; text-transform: uppercase; }
  .now-playing { font-size: 15px; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tabs { display: flex; gap: 4px; }
  .tab-btn { background: #374151; color: #d1d5db; border: 1px solid #4b5563; border-radius: 8px; padding: 6px 10px; font-size: 13px; font-weight: bold; cursor: pointer; }
  .tab-btn.active { background: #059669; color: #ffffff; border-color: #10b981; }
  .clock { font-size: 22px; font-weight: bold; color: #facc15; letter-spacing: 1px; font-variant-numeric: tabular-nums; }
  .btn-play { background: #2563eb; color: white; border: none; border-radius: 8px; padding: 7px 12px; font-size: 13px; font-weight: bold; cursor: pointer; min-width: 72px; }
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
  .music-view { display: none; flex: 1; flex-direction: column; gap: 8px; min-height: 0; }
  .music-controls { display: flex; gap: 8px; }
  .m-btn { flex: 1; background: #1f2937; color: #f9fafb; border: 2px solid #374151; border-radius: 10px; padding: 8px; font-size: 13px; font-weight: bold; cursor: pointer; }
  .m-btn.active { background: #7c3aed; border-color: #a78bfa; }
  .track-list { flex: 1; overflow-y: auto; display: block; }
  .track-item { display: block; width: 100%; height: 44px; line-height: 22px; margin-bottom: 6px; background: #1f2937; color: #e5e7eb; border: 1px solid #374151; border-radius: 8px; padding: 10px 12px; font-size: 15px; font-weight: bold; text-align: left; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .track-item.active { background: #065f46; border-color: #10b981; color: #ffffff; }
  #screensaver { display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: #000000; color: #9ca3af; z-index: 9999; flex-direction: column; justify-content: center; align-items: center; }
  #screensaver.active { display: flex; }
  #ss-clock { font-size: 72px; font-weight: bold; letter-spacing: 2px; font-variant-numeric: tabular-nums; line-height: 1; }
  #ss-station { font-size: 18px; margin-top: 8px; color: #6b7280; max-width: 90vw; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
</head>
<body>
  <div class="header">
    <div class="info">
      <div class="status" id="state">DETENIDO</div>
      <div class="now-playing" id="title">Selecciona una radio</div>
    </div>
    <div class="tabs">
      <button class="tab-btn active" id="tab-radio" onclick="switchTab('radio')">📻</button>
      <button class="tab-btn" id="tab-music" onclick="switchTab('music')">🎵</button>
    </div>
    <div class="clock" id="clock">--:--</div>
    <button class="btn-play" id="toggleBtn" onclick="togglePlay()">PLAY</button>
  </div>

  <div class="main" id="view-radio">
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

  <div class="music-view" id="view-music">
    <div class="music-controls">
      <button class="m-btn" onclick="musicCmd('prev')">⏮ Ant</button>
      <button class="m-btn" onclick="musicCmd('next')">⏭ Sig</button>
      <button class="m-btn" id="btn-random" onclick="musicCmd('random')">🔀 Aleat</button>
      <button class="m-btn" onclick="rescanTracks()">🔄</button>
    </div>
    <div class="track-list" id="track-list"></div>
  </div>

  <div id="screensaver" onclick="wakeUp()">
    <div id="ss-clock">--:--</div>
    <div id="ss-station"></div>
  </div>

<script>
  let currentTab = 'radio';

  async function switchTab(tab) {
    const res = await fetch('/tab/' + tab, { method: 'POST' });
    updateUI(await res.json());
  }
  async function playStation(idx) {
    const res = await fetch('/play/' + idx, { method: 'POST' });
    updateUI(await res.json());
  }
  async function playTrack(track) {
    const res = await fetch('/music/play', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ track })
    });
    updateUI(await res.json());
  }
  async function musicCmd(cmd) {
    const res = await fetch('/music/' + cmd, { method: 'POST' });
    updateUI(await res.json());
  }
  async function rescanTracks() {
    await fetch('/music/rescan', { method: 'POST' });
    loadTracks();
  }
  async function togglePlay() {
    const res = await fetch('/toggle', { method: 'POST' });
    updateUI(await res.json());
  }
  async function loadTracks() {
    try {
      const res = await fetch('/music/tracks?t=' + Date.now());
      const data = await res.json();
      const list = document.getElementById('track-list');
      list.innerHTML = '';
      if (data.tracks.length === 0) {
        list.innerHTML = '<div class="track-item">Sin archivos en radio-web/mp3</div>';
        return;
      }
      data.tracks.forEach(t => {
        const btn = document.createElement('button');
        btn.className = 'track-item';
        btn.dataset.track = t;
        btn.innerText = t.replace(/\.[^/.]+$/, "");
        btn.onclick = () => playTrack(t);
        list.appendChild(btn);
      });
    } catch (e) {}
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
  async function wakeUp() {
    document.getElementById('screensaver').classList.remove('active');
    const res = await fetch('/wake', { method: 'POST' });
    updateUI(await res.json());
  }
  function updateUI(data) {
    document.getElementById('state').innerText = data.playing ? 'EN VIVO' : 'EN PAUSA';
    document.getElementById('title').innerText = data.station || 'Sin reproducción';
    const btn = document.getElementById('toggleBtn');
    btn.innerText = data.playing ? 'PAUSE' : 'PLAY';
    btn.classList.toggle('paused', !data.playing);

    if (data.tab && data.tab !== currentTab) {
      currentTab = data.tab;
      document.getElementById('view-radio').style.display = currentTab === 'radio' ? 'flex' : 'none';
      document.getElementById('view-music').style.display = currentTab === 'music' ? 'flex' : 'none';
      document.getElementById('tab-radio').classList.toggle('active', currentTab === 'radio');
      document.getElementById('tab-music').classList.toggle('active', currentTab === 'music');
      if (currentTab === 'music') loadTracks();
    }

    document.querySelectorAll('.station').forEach((el, i) => {
      el.classList.toggle('active', data.mode === 'radio' && i === data.index);
    });
    document.querySelectorAll('.track-item').forEach(el => {
      el.classList.toggle('active', data.mode === 'music' && el.dataset.track === data.current_file);
    });
    document.getElementById('btn-random').classList.toggle('active', !!data.random);

    const ss = document.getElementById('screensaver');
    ss.classList.toggle('active', !!data.screensaver);
    document.getElementById('ss-clock').innerText = document.getElementById('clock').innerText;
    document.getElementById('ss-station').innerText = data.station || '';
  }
  function updateClock() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
    document.getElementById('clock').innerText = timeStr;
    document.getElementById('ss-clock').innerText = timeStr;
    const mins = now.getHours() * 60 + now.getMinutes();
    const isNight = mins >= 23 * 60 || mins < 7 * 60 + 30;
    document.body.classList.toggle('night', isNight);
  }
  setInterval(updateClock, 1000);
  updateClock();
  loadTracks();
  setInterval(refresh, 2000);
  refresh();
  setInterval(refreshWeather, 600000);
  refreshWeather();
</script>
</body>
</html>"""

def get_status():
    try:
        out = subprocess.check_output(["mpc", "-f", "%file%\n%title%", "status"], text=True)
    except Exception:
        out = ""
    lines = out.splitlines()
    playing = "[playing]" in out
    random_on = "random: on" in out
    current_file = lines[0] if lines and not lines[0].startswith("volume:") else ""
    title_tag = lines[1] if len(lines) > 1 and not lines[1].startswith("[") else ""

    if current_file.startswith("http"):
        mode = "radio"
        idx = current_index
        for i, s in enumerate(STATIONS):
            if s["url"] in current_file:
                idx = i
                break
        station = STATIONS[idx]["name"] if 0 <= idx < len(STATIONS) else ""
    elif current_file:
        mode = "music"
        idx = -1
        station = title_tag if title_tag else os.path.splitext(os.path.basename(current_file))[0]
    else:
        mode = "radio"
        idx = current_index
        station = STATIONS[idx]["name"] if 0 <= idx < len(STATIONS) else ""

    is_screensaver = (time.time() - last_activity) > SCREENSAVER_TIMEOUT
    return {
        "playing": playing,
        "station": station,
        "index": idx,
        "mode": mode,
        "current_file": current_file,
        "random": random_on,
        "tab": active_tab,
        "screensaver": is_screensaver,
    }

@app.route("/")
def index():
    return render_template_string(HTML, stations=STATIONS)

@app.route("/status")
def status():
    return jsonify(get_status())

@app.route("/weather")
def weather():
    return jsonify(get_weather())

@app.route("/tab/<tab_name>", methods=["POST"])
def set_tab(tab_name):
    global active_tab, last_activity
    last_activity = time.time()
    if tab_name in ("radio", "music"):
        active_tab = tab_name
    return jsonify(get_status())

@app.route("/play/<int:idx>", methods=["POST"])
def play(idx):
    global current_index, last_activity
    last_activity = time.time()
    if 0 <= idx < len(STATIONS):
        current_index = idx
        subprocess.run(["mpc", "clear"], check=False)
        subprocess.run(["mpc", "repeat", "off"], check=False)
        subprocess.run(["mpc", "random", "off"], check=False)
        subprocess.run(["mpc", "add", STATIONS[idx]["url"]], check=False)
        subprocess.run(["mpc", "play"], check=False)
    return jsonify(get_status())

@app.route("/music/tracks")
def music_tracks():
    return jsonify({"tracks": get_local_tracks()})

@app.route("/music/rescan", methods=["POST"])
def music_rescan():
    global last_activity
    last_activity = time.time()
    subprocess.run(["mpc", "update", "--wait"], check=False)
    return jsonify(get_status())

@app.route("/music/play", methods=["POST"])
def music_play():
    global last_activity
    last_activity = time.time()
    data = request.get_json(silent=True) or {}
    target = data.get("track", "")
    tracks = get_local_tracks()
    if target in tracks:
        subprocess.run(["mpc", "update", "--wait"], check=False)
        subprocess.run(["mpc", "clear"], check=False)
        for t in tracks:
            subprocess.run(["mpc", "add", t], check=False)
        subprocess.run(["mpc", "repeat", "on"], check=False)
        pos = tracks.index(target) + 1
        subprocess.run(["mpc", "play", str(pos)], check=False)
    return jsonify(get_status())

@app.route("/music/<cmd>", methods=["POST"])
def music_cmd(cmd):
    global last_activity
    last_activity = time.time()
    if cmd == "next":
        subprocess.run(["mpc", "next"], check=False)
    elif cmd == "prev":
        subprocess.run(["mpc", "prev"], check=False)
    elif cmd == "random":
        subprocess.run(["mpc", "random"], check=False)
    return jsonify(get_status())

@app.route("/toggle", methods=["POST"])
def toggle():
    global last_activity
    last_activity = time.time()
    subprocess.run(["mpc", "toggle"], check=False)
    return jsonify(get_status())

@app.route("/wake", methods=["POST"])
def wake():
    global last_activity
    last_activity = time.time()
    return jsonify(get_status())

def auto_play():
    time.sleep(3)
    play(0)

threading.Thread(target=auto_play, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
