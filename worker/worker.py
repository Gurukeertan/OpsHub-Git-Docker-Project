"""
opshub-worker
-------------
A third container in the stack: a lightweight background-worker style
service. It exposes /health (JSON, for opshub-monitor to poll over
opshub-net) AND its own live HTML dashboard on / -- so it looks and
feels consistent with opshub and opshub-monitor rather than being a
bare JSON endpoint.
"""

import json
import random
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STARTED_AT = time.time()


def build_health_payload():
    uptime = round(time.time() - STARTED_AT, 1)
    return {
        "status": "ok",
        "service": "opshub-worker",
        "uptime_seconds": uptime,
        "queue_depth": random.randint(0, 12),
        "jobs_processed": int(uptime * 1.7),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>opshub-worker | Background Worker</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  :root{
    --bg:#060c17; --card:#0d1a2c; --card2:#0a1524;
    --border:#1c3350; --border-soft:#152740;
    --text:#eef3fb; --muted:#8ea2bb;
    --teal:#5eead4; --blue:#38bdf8; --green:#34d399; --violet:#a78bfa;
  }
  body{
    font-family:'Inter',system-ui,-apple-system,Segoe UI,sans-serif;
    color:var(--text); min-height:100vh;
    background:
      radial-gradient(1100px 600px at 12% -10%, rgba(167,139,250,.10), transparent 60%),
      radial-gradient(900px 500px at 100% 0%, rgba(56,189,248,.10), transparent 55%),
      var(--bg);
    background-attachment:fixed;
  }
  .wrap{max-width:760px;margin:auto;padding:32px 28px 20px}
  header{display:flex;justify-content:space-between;align-items:center;padding:6px 0 8px;flex-wrap:wrap;gap:14px}
  .brand{display:flex;gap:13px;align-items:center;font-weight:800;font-size:23px;letter-spacing:-.5px}
  .logo{
    width:42px;height:42px;border-radius:13px;
    background:linear-gradient(135deg,var(--violet),var(--blue));
    display:grid;place-items:center;color:#06111c;font-weight:900;font-size:18px;
    box-shadow:0 6px 22px rgba(167,139,250,.35);
  }
  .brand small{display:block;color:var(--muted);font-weight:500;font-size:11.5px;margin-top:1px}
  .badge{
    display:flex;align-items:center;gap:7px;padding:9px 14px;border:1px solid var(--border);
    border-radius:999px;color:var(--teal);background:rgba(10,29,44,.7);font-size:12.5px;font-weight:600;
  }
  .pulse{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 10px var(--green);animation:pulse 1.8s ease-in-out infinite}
  @keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.45;transform:scale(.75)}}

  .card{
    background:linear-gradient(160deg,var(--card),var(--card2));
    border:1px solid var(--border-soft); border-radius:22px;
    padding:26px; margin-top:24px; position:relative; overflow:hidden;
    box-shadow:0 20px 44px -18px rgba(0,0,0,.55);
  }
  .card::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;
    background:linear-gradient(90deg,var(--violet),var(--blue));opacity:.85}
  .health{display:flex;align-items:center;gap:10px;font-weight:700;font-size:19px}
  .dot{width:12px;height:12px;border-radius:50%;background:var(--green);box-shadow:0 0 14px var(--green)}
  .muted{color:var(--muted);font-size:12.5px;margin-top:6px}

  .stats{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:22px}
  .stat{background:rgba(6,12,24,.55);border:1px solid var(--border-soft);border-radius:14px;padding:16px}
  .stat b{display:block;font-family:'JetBrains Mono',monospace;font-size:22px;margin-bottom:4px;color:var(--teal)}
  .stat span{color:#7d92aa;font-size:11px;text-transform:uppercase;letter-spacing:.3px}

  footer{text-align:center;color:#5c7290;font-size:12px;padding:34px 0 12px}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="brand">
        <div class="logo">W</div>
        <div>
          opshub-worker
          <small>Background job processor</small>
        </div>
      </div>
      <div class="badge"><span class="pulse"></span> Live</div>
    </header>

    <div class="card">
      <div class="health"><span class="dot"></span> <span id="statusText">Loading…</span></div>
      <div class="muted">Self-reported status, refreshed every 3s. Also polled by opshub-monitor over opshub-net.</div>
      <div class="stats">
        <div class="stat"><b id="uptime">-</b><span>Uptime (s)</span></div>
        <div class="stat"><b id="queue">-</b><span>Queue depth</span></div>
        <div class="stat"><b id="jobs">-</b><span>Jobs processed</span></div>
        <div class="stat"><b id="checked">-</b><span>Last self-check</span></div>
      </div>
    </div>

    <footer>opshub-worker • watched by opshub-monitor over opshub-net</footer>
  </div>

<script>
async function refresh() {
  try {
    const res = await fetch('/health', {cache: 'no-store'});
    const data = await res.json();
    document.getElementById('statusText').textContent = 'Worker is healthy';
    document.getElementById('uptime').textContent = data.uptime_seconds;
    document.getElementById('queue').textContent = data.queue_depth;
    document.getElementById('jobs').textContent = data.jobs_processed;
    document.getElementById('checked').textContent = data.checked_at.slice(11,19);
  } catch (e) {
    document.getElementById('statusText').textContent = 'Unable to reach worker';
  }
}
refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload, code=200):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body_str, code=200):
        body = body_str.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._send_html(DASHBOARD_HTML)
        elif self.path == "/health":
            self._send_json(build_health_payload())
        else:
            self._send_json({"error": "not found"}, code=404)

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 7070), Handler)
    print("opshub-worker listening on :7070 (dashboard on /, health on /health)", flush=True)
    server.serve_forever()
