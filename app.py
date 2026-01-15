import threading
import asyncio
import telnetlib3
import json
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

TELNET_HOST = "10.4.30.168"
TELNET_PORT = 8885

log_buffer = []
log_lock = threading.Lock()
MAX_LOGS = 100000


async def telnet_reader_async():
    backoff = 5
    while True:
        try:
            reader, writer = await telnetlib3.open_connection(
                TELNET_HOST, TELNET_PORT
            )
            print("Telnet connected.")

            while True:
                line = await reader.readline()
                if not line:
                    raise ConnectionError("telnet connection closed")

                with log_lock:
                    log_buffer.append(line.rstrip())
                    if len(log_buffer) > MAX_LOGS:
                        del log_buffer[:-MAX_LOGS]

        except Exception as e:
            with log_lock:
                log_buffer.append(f"[ERROR] {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


def start_telnet_loop():
    asyncio.run(telnet_reader_async())


@app.route("/logs")
def get_logs():
    start = int(request.args.get("start", 0))
    with log_lock:
        return jsonify({
            "logs": log_buffer[start:],
            "next": len(log_buffer)
        })


@app.route("/clear_logs", methods=["POST"])
def clear_logs():
    with log_lock:
        log_buffer.clear()
    return "", 204


@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Telnet Log Viewer</title>
    <style>
        body { font-family: monospace; background: #111; color: #eee; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #444; padding: 4px 8px; }
        th { background: #222; position: sticky; top: 0; }
        #log-container { height: 85vh; overflow-y: auto; }

        .filter-row button {
            margin-left: 6px;
        }
        .delete-btn {
            color: #ff6666;
            font-weight: bold;
        }
    </style>
</head>
<body>

<h2>Telnet Logs</h2>

<div>
    <button onclick="saveFilters()">Save Filters</button>
    <button onclick="loadFilters()">Load Filters</button>
</div>

<div id="filters-container" style="margin:10px 0;">
    <button onclick="addFilterRow()">+ Add Filter</button>
</div>

<div style="margin-bottom:10px;">
    <button onclick="clearLogs()">Clear Logs</button>
    <label>
        <input type="checkbox" id="showMatchesOnly">
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
let lastIndex = 0;

function addFilterRow(regex="", color="#ff0000", active=false) {
    const container = document.getElementById("filters-container");

    const row = document.createElement("div");
    row.className = "filter-row";
    row.style.marginTop = "5px";

    const deleteBtn = document.createElement("button");
    deleteBtn.textContent = "✕";
    deleteBtn.className = "delete-btn";

    const regexInput = document.createElement("input");
    regexInput.placeholder = "Regex";
    regexInput.value = regex;
    regexInput.style.width = "600px";

    const colorInput = document.createElement("input");
    colorInput.type = "color";
    colorInput.value = color;

    const toggleBtn = document.createElement("button");
    toggleBtn.textContent = active ? "Deactivate" : "Activate";

    const filter = {
        regexInput,
        colorInput,
        active,
        regexObj: active && regex ? new RegExp(regex, "i") : null,
        row
    };

    deleteBtn.onclick = () => {
        filter.active = false;
        filters = filters.filter(f => f !== filter);
        row.remove();
        applyFilters();
    };

    toggleBtn.onclick = () => {
        if (!filter.active) {
            try {
                filter.regexObj = new RegExp(regexInput.value, "i");
            } catch {
                alert("Invalid regex");
                return;
            }
            filter.active = true;
            toggleBtn.textContent = "Deactivate";
        } else {
            filter.active = false;
            filter.regexObj = null;
            toggleBtn.textContent = "Activate";
        }
        applyFilters();
    };

    row.append(deleteBtn, regexInput, colorInput, toggleBtn);
    container.appendChild(row);
    filters.push(filter);
}

function applyFilters() {
    const showOnly = document.getElementById("showMatchesOnly").checked;
    document.querySelectorAll("#log-body tr").forEach(row => {
        row.style.background = "";
        row.style.display = "";
        let matched = false;

        // Newest filters take precedence
        for (let i = filters.length - 1; i >= 0; i--) {
            const f = filters[i];
            if (f.active && f.regexObj && f.regexObj.test(row.textContent)) {
                row.style.background = f.colorInput.value;
                matched = true;
                break;
            }
        }
        if (showOnly && !matched) row.style.display = "none";
    });
}

async function fetchLogs() {
    const res = await fetch(`/logs?start=${lastIndex}`);
    const data = await res.json();

    const tbody = document.getElementById("log-body");
    const container = document.getElementById("log-container");

    const atBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight < 5;

    for (const line of data.logs) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.textContent = line;
        tr.appendChild(td);
        tbody.appendChild(tr);
    }

    lastIndex = data.next;
    applyFilters();

    if (atBottom) container.scrollTop = container.scrollHeight;
}

async function clearLogs() {
    await fetch("/clear_logs", { method: "POST" });
    document.getElementById("log-body").innerHTML = "";
    lastIndex = 0;
}

function saveFilters() {
    const data = filters.map(f => ({
        regex: f.regexInput.value,
        color: f.colorInput.value,
        active: f.active
    }));
    const blob = new Blob([JSON.stringify(data, null, 2)]);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "filters.json";
    a.click();
}

function loadFilters() {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "application/json";
    input.onchange = () => {
        const reader = new FileReader();
        reader.onload = () => {
            document.getElementById("filters-container").innerHTML =
                '<button onclick="addFilterRow()">+ Add Filter</button>';
            filters = [];
            JSON.parse(reader.result).forEach(f =>
                addFilterRow(f.regex, f.color, f.active)
            );
            applyFilters();
        };
        reader.readAsText(input.files[0]);
    };
    input.click();
}

setInterval(fetchLogs, 1000);
</script>

</body>
</html>
"""

if __name__ == "__main__":
    threading.Thread(target=start_telnet_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=4999, debug=False)
