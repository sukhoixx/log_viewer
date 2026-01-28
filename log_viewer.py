import threading
import asyncio
import telnetlib3
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

# ------------------ Globals ------------------
log_buffer = []
log_lock = threading.Lock()
MAX_LOGS = 1000000

telnet_thread = None
telnet_stop_event = threading.Event()
telnet_writer = None

connected_host = None
connected_port = None

# ------------------ Telnet Reader ------------------
async def telnet_reader_async(host, port):
    global telnet_writer
    backoff = 5

    while not telnet_stop_event.is_set():
        try:
            reader, writer = await telnetlib3.open_connection(host, port)
            telnet_writer = writer

            with log_lock:
                log_buffer.append(f"[INFO] Connected to {host}:{port}")

            while not telnet_stop_event.is_set():
                line = await reader.readline()
                if not line:
                    raise ConnectionError("connection closed")

                with log_lock:
                    log_buffer.append(line.rstrip())
                    if len(log_buffer) > MAX_LOGS:
                        del log_buffer[:-MAX_LOGS]

        except Exception as e:
            if not telnet_stop_event.is_set():
                with log_lock:
                    log_buffer.append(f"[ERROR] {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    if telnet_writer:
        telnet_writer.close()
        telnet_writer = None


def start_telnet_loop(host, port):
    asyncio.run(telnet_reader_async(host, port))


# ------------------ API ------------------
@app.route("/logs")
def get_logs():
    with log_lock:
        return jsonify(log_buffer)


@app.route("/clear_logs", methods=["POST"])
def clear_logs():
    with log_lock:
        log_buffer.clear()
    return jsonify({"status": "cleared"})


@app.route("/connect", methods=["POST"])
def connect():
    global telnet_thread, connected_host, connected_port

    if telnet_thread and telnet_thread.is_alive():
        return jsonify({"error": "Already connected"}), 400

    data = request.json
    telnet_stop_event.clear()

    connected_host = data["host"]
    connected_port = int(data["port"])

    telnet_thread = threading.Thread(
        target=start_telnet_loop,
        args=(connected_host, connected_port),
        daemon=True,
    )
    telnet_thread.start()

    return jsonify({"status": "connected"})


@app.route("/disconnect", methods=["POST"])
def disconnect():
    global telnet_thread, connected_host, connected_port

    telnet_stop_event.set()

    if telnet_thread:
        telnet_thread.join(timeout=3)
        telnet_thread = None

    telnet_stop_event.clear()

    with log_lock:
        log_buffer.append("[INFO] Disconnected")

    connected_host = None
    connected_port = None

    return jsonify({"status": "disconnected"})


@app.route("/status")
def status():
    alive = telnet_thread is not None and telnet_thread.is_alive()
    return jsonify({
        "connected": alive,
        "host": connected_host,
        "port": connected_port
    })


@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


# ------------------ HTML ------------------
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Telnet Log Viewer</title>
<style>
body { font-family: monospace; background:#111; color:#eee; }
table { width:100%; border-collapse:collapse; }
th, td { border:1px solid #444; padding:4px 8px; }
th { background:#222; position:sticky; top:0; }
#log-container { height:80vh; overflow-y:auto; margin-top:10px; }
input[type="text"] { width:500px; }
.filter-row { margin-top:5px; }
button { margin-left:5px; }
</style>
</head>
<body>

<h3>
IP:<input id="host" value="">
Port:<input id="port" value="8885" style="width:80px">
<button id="connectBtn">Connect</button>
</h3>

<div id="filters-container">
    <button onclick="addFilter()">+ Add Filter</button>
    <button onclick="saveFilters()">Save Filters</button>
    <button onclick="loadFilters()">Load Filters</button>
</div>

<div style="margin-top:8px;">
    <button onclick="clearLogs()">Clear Logs</button>
    <label>
        <input type="checkbox" id="matchesOnly">
        Show matches only
    </label>
</div>

<div id="log-container">
<table>
<thead><tr><th>Log Entry</th></tr></thead>
<tbody id="log-body"></tbody>
</table>
</div>

<script>
let filters = [];
let lastLength = 0;
let connected = false;

// ------------------ Check status on load ------------------
async function checkStatus() {
    const res = await fetch("/status");
    const s = await res.json();
    connected = s.connected;
    document.getElementById("connectBtn").textContent = connected ? "Disconnect" : "Connect";
    if (connected) {
        document.getElementById("host").value = s.host;
        document.getElementById("port").value = s.port;
    }
}
checkStatus();

// ------------------ Connection ------------------
document.getElementById("connectBtn").onclick = async () => {
    if (!connected) {
        const res = await fetch("/connect", {
            method:"POST",
            headers:{ "Content-Type":"application/json" },
            body: JSON.stringify({
                host: document.getElementById("host").value,
                port: document.getElementById("port").value
            })
        });
        if (res.ok) {
            connected = true;
            document.getElementById("connectBtn").textContent = "Disconnect";
        }
    } else {
        await fetch("/disconnect", { method:"POST" });
        connected = false;
        document.getElementById("connectBtn").textContent = "Connect";
    }
};

// ------------------ Logs ------------------
function clearLogs() {
    fetch("/clear_logs", { method:"POST" });
    document.getElementById("log-body").innerHTML = "";
    lastLength = 0;
}

// ------------------ Filters ------------------
function addFilter(regex="", color="#ff0000", active=false) {
    const row = document.createElement("div");
    row.className = "filter-row";

    const del = document.createElement("button");
    del.textContent = "X";

    const input = document.createElement("input");
    input.value = regex;
    input.style.width = "600px";

    const colorInput = document.createElement("input");
    colorInput.type = "color";
    colorInput.value = color;

    const btn = document.createElement("button");

    const f = { row, input, colorInput, regex:null, active:false };

    function activate() {
        try { f.regex = new RegExp(input.value, "i"); }
        catch { alert("Invalid regex"); return; }
        f.active = true;
        btn.textContent = "Deactivate";
    }

    function deactivate() {
        f.active = false;
        btn.textContent = "Activate";
    }

    btn.onclick = () => {
        f.active ? deactivate() : activate();
        applyFilters();
    };

    del.onclick = () => {
        filters = filters.filter(x => x !== f);
        row.remove();
        applyFilters();
    };

    row.append(del, input, colorInput, btn);
    document.getElementById("filters-container").appendChild(row);
    filters.push(f);

    if (active) activate();
    else deactivate();
}

function applyFilters() {
    const rows = document.getElementById("log-body").children;
    for (let r of rows) {
        r.style.background = "";
        let matched = false;

        for (let i = filters.length - 1; i >= 0; i--) {
            const f = filters[i];
            if (f.active && f.regex && f.regex.test(r.textContent)) {
                r.style.background = f.colorInput.value;
                matched = true;
                break;
            }
        }

        r.style.display =
            document.getElementById("matchesOnly").checked && !matched
            ? "none" : "";
    }
}

// ------------------ Fetch Logs ------------------
async function fetchLogs() {
    const res = await fetch("/logs");
    const logs = await res.json();

    const tbody = document.getElementById("log-body");
    const cont = document.getElementById("log-container");
    const atBottom = cont.scrollHeight - cont.scrollTop - cont.clientHeight < 5;

    for (let i = lastLength; i < logs.length; i++) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.textContent = logs[i];
        tr.appendChild(td);
        tbody.appendChild(tr);
    }

    lastLength = logs.length;
    applyFilters();
    if (atBottom) cont.scrollTop = cont.scrollHeight;
}

// ------------------ Save / Load Filters ------------------
function saveFilters() {
    const data = filters.map(f => ({
        regex: f.input.value,
        color: f.colorInput.value,
        active: f.active
    }));
    const blob = new Blob([JSON.stringify(data, null, 2)], {type:"application/json"});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "filters.json";
    a.click();
}

function loadFilters() {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.onchange = () => {
        const r = new FileReader();
        r.onload = () => {
            filters = [];
            document.querySelectorAll(".filter-row").forEach(e => e.remove());
            JSON.parse(r.result).forEach(f => {
                addFilter(f.regex, f.color, f.active);
            });
            applyFilters();
        };
        r.readAsText(inp.files[0]);
    };
    inp.click();
}

setInterval(fetchLogs, 1000);
</script>
</body>
</html>
"""

import time
import threading
import webbrowser

def run_flask():
    app.run(host="127.0.0.1", port=4999, debug=False, use_reloader=False)

def open_browser():
    webbrowser.open("http://127.0.0.1:4999")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Timer(1.0, open_browser).start()

    while True:
        time.sleep(1)
