"""
opshub-monitor
--------------
A small, dependency-free health-monitoring service for OpsHub and any
number of additional containers.

Design:
- Each target is polled on its OWN background thread, concurrently --
  a slow or hanging target never delays checks for the others.
- Failures are classified (timeout, connection refused, DNS failure,
  bad HTTP status, slow response) instead of a flat healthy/unhealthy,
  so /status tells you the actual problem.
- A "trigger" fires only on a STATE CHANGE (healthy -> unhealthy or
  back), not on every poll. This keeps the history meaningful instead
  of filling up with repeated "still unhealthy" entries, and is the
  hook point for wiring in real alerting (webhook, Slack, email, etc.)
  via the ALERT_WEBHOOK_URL env var.

Targets are configured via the MONITOR_TARGETS environment variable
-- adding a new container to watch is a one-line docker-compose
change, no code edits required:

    MONITOR_TARGETS=opshub=http://opshub/health,redis=http://redis:6379/health

Any target not listed defaults to just "opshub" for backwards
compatibility.
"""

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "5"))
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "3"))
SLOW_THRESHOLD_SECONDS = float(os.environ.get("SLOW_THRESHOLD_SECONDS", "1.5"))
ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "")  # optional

DEFAULT_TARGETS = "opshub=http://opshub/health"
RAW_TARGETS = os.environ.get("MONITOR_TARGETS", DEFAULT_TARGETS)


def parse_targets(raw):
    targets = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        name, url = pair.split("=", 1)
        targets[name.strip()] = url.strip()
    return targets


TARGETS = parse_targets(RAW_TARGETS)  # {name: url}

state = {
    name: {
        "target": url,
        "status": "unknown",       # healthy | unhealthy | unknown
        "issue": None,             # e.g. "timeout", "connection_refused", "dns_failure", "http_500", "slow_response"
        "response_ms": None,
        "last_checked": None,
        "last_success": None,
        "consecutive_failures": 0,
        "events": [],              # only state TRANSITIONS, not every poll (last 20)
    }
    for name, url in TARGETS.items()
}
state_lock = threading.Lock()


def classify_error(exc):
    if isinstance(exc, socket.timeout) or isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, urllib.error.HTTPError):
        return "http_%s" % exc.code
    if isinstance(exc, urllib.error.URLError):
        reason = str(exc.reason)
        if "Name or service not known" in reason or "nodename nor servname" in reason:
            return "dns_failure"
        if "Connection refused" in reason:
            return "connection_refused"
        return "connection_error"
    return "unknown_error: %s" % exc


def fire_trigger(name, new_status, issue, s):
    """Called only on a state transition. Extend this to page/alert."""
    print(
        "[TRIGGER] %s -> %s%s at %s"
        % (name, new_status, (" (%s)" % issue) if issue else "", s["last_checked"]),
        flush=True,
    )
    if ALERT_WEBHOOK_URL:
        payload = json.dumps(
            {"target": name, "status": new_status, "issue": issue, "at": s["last_checked"]}
        ).encode()
        try:
            req = urllib.request.Request(
                ALERT_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception as exc:
            print("[TRIGGER] webhook delivery failed: %s" % exc, flush=True)


def check_one(name, url):
    now = datetime.now(timezone.utc).isoformat()
    ok = False
    issue = None
    response_ms = None
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            response_ms = round((time.monotonic() - start) * 1000, 1)
            if resp.status == 200:
                ok = True
                if response_ms / 1000 > SLOW_THRESHOLD_SECONDS:
                    issue = "slow_response"
            else:
                issue = "http_%s" % resp.status
    except Exception as exc:
        response_ms = round((time.monotonic() - start) * 1000, 1)
        issue = classify_error(exc)

    with state_lock:
        s = state[name]
        previous_status = s["status"]
        s["last_checked"] = now
        s["response_ms"] = response_ms
        s["status"] = "healthy" if ok else "unhealthy"
        s["issue"] = issue  # keeps "slow_response" even when ok=True

        if ok:
            s["last_success"] = now
            s["consecutive_failures"] = 0
        else:
            s["consecutive_failures"] += 1

        # Only record + trigger on an actual state change, not every poll.
        if s["status"] != previous_status:
            s["events"].append(
                {"time": now, "from": previous_status, "to": s["status"], "issue": issue}
            )
            s["events"] = s["events"][-20:]
            fire_trigger(name, s["status"], issue, s)


def poll_target_forever(name, url):
    """Each target runs on its own thread, so a slow target never
    blocks or delays checks for any other target."""
    while True:
        check_one(name, url)
        time.sleep(POLL_INTERVAL_SECONDS)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>opshub-monitor | Live Health Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  :root{
    --bg:#060c17; --bg2:#0a1120;
    --card:#0d1a2c; --card2:#0a1524;
    --border:#1c3350; --border-soft:#152740;
    --text:#eef3fb; --muted:#8ea2bb;
    --teal:#5eead4; --blue:#38bdf8; --violet:#a78bfa;
    --green:#34d399; --red:#f87171; --amber:#fbbf24; --orange:#fb923c;
  }
  body{
    font-family:'Inter',system-ui,-apple-system,Segoe UI,sans-serif;
    color:var(--text); min-height:100vh;
    background:
      radial-gradient(1100px 600px at 12% -10%, rgba(94,234,212,.10), transparent 60%),
      radial-gradient(900px 500px at 100% 0%, rgba(56,189,248,.10), transparent 55%),
      radial-gradient(700px 500px at 50% 110%, rgba(167,139,250,.08), transparent 55%),
      var(--bg);
    background-attachment:fixed;
  }
  .wrap{max-width:1180px;margin:auto;padding:32px 28px 20px}
  header{display:flex;justify-content:space-between;align-items:center;padding:6px 0 8px;flex-wrap:wrap;gap:14px}
  .brand{display:flex;gap:13px;align-items:center;font-weight:800;font-size:23px;letter-spacing:-.5px}
  .logo{
    width:42px;height:42px;border-radius:13px;
    background:linear-gradient(135deg,var(--teal),var(--blue));
    display:grid;place-items:center;color:#06111c;font-weight:900;font-size:18px;
    box-shadow:0 6px 22px rgba(56,189,248,.35);
  }
  .brand small{display:block;color:var(--muted);font-weight:500;font-size:11.5px;letter-spacing:.3px;margin-top:1px}
  .badge{
    display:flex;align-items:center;gap:7px;padding:9px 14px;border:1px solid var(--border);
    border-radius:999px;color:var(--teal);background:rgba(10,29,44,.7);
    font-size:12.5px;font-weight:600;backdrop-filter:blur(6px);
  }
  .pulse{width:7px;height:7px;border-radius:50%;background:var(--teal);box-shadow:0 0 10px var(--teal);animation:pulse 1.8s ease-in-out infinite}
  @keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.45;transform:scale(.75)}}

  .summary{
    display:grid;grid-template-columns:repeat(4,1fr);gap:14px;
    margin:26px 0 30px;
  }
  .summary .tile{
    background:linear-gradient(160deg,var(--card),var(--card2));
    border:1px solid var(--border-soft); border-radius:16px;
    padding:16px 18px; position:relative; overflow:hidden;
  }
  .summary .tile::after{content:"";position:absolute;inset:0;border-radius:16px;padding:1px;
    background:linear-gradient(160deg,rgba(255,255,255,.06),transparent 40%);
    -webkit-mask:linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    -webkit-mask-composite: xor; mask-composite: exclude; pointer-events:none;}
  .summary .n{font-family:'JetBrains Mono',monospace;font-size:26px;font-weight:700;line-height:1}
  .summary .l{color:var(--muted);font-size:11.5px;margin-top:7px;letter-spacing:.3px;text-transform:uppercase}
  .summary .healthy .n{color:var(--green)}
  .summary .issues .n{color:var(--red)}
  .summary .avg .n{color:var(--blue)}
  .summary .total .n{background:linear-gradient(90deg,var(--teal),var(--blue));-webkit-background-clip:text;background-clip:text;color:transparent}

  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:18px}

  .card{
    background:linear-gradient(160deg,var(--card),var(--card2));
    border:1px solid var(--border-soft); border-radius:22px;
    padding:24px; position:relative; overflow:hidden;
    box-shadow:0 20px 44px -18px rgba(0,0,0,.55);
    transition:transform .22s ease, box-shadow .22s ease, border-color .22s ease;
  }
  .card:hover{transform:translateY(-3px); border-color:var(--border); box-shadow:0 26px 54px -16px rgba(0,0,0,.65)}
  .card::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;
    background:linear-gradient(90deg,var(--teal),var(--blue));opacity:.85}
  .card.bad::before{background:linear-gradient(90deg,#fb7185,var(--red))}
  .card.slow::before{background:linear-gradient(90deg,var(--amber),var(--orange))}
  .card.unknown::before{background:linear-gradient(90deg,#94a3b8,#cbd5e1)}

  .cardhead{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:4px}
  .name{font-size:17px;font-weight:700;letter-spacing:-.2px}
  .health{display:flex;align-items:center;gap:9px;font-weight:600;font-size:13.5px;color:var(--muted);margin-top:5px}
  .dot{width:10px;height:10px;border-radius:50%;background:var(--green);box-shadow:0 0 12px var(--green);flex-shrink:0}
  .dot.bad{background:var(--red);box-shadow:0 0 12px var(--red)}
  .dot.unknown{background:#94a3b8;box-shadow:0 0 12px #94a3b8}
  .dot.slow{background:var(--orange);box-shadow:0 0 12px var(--orange)}

  .muted{color:var(--muted);line-height:1.7;font-size:12.5px}
  .target-url{font-family:'JetBrains Mono',monospace;font-size:11.5px;color:#7590ac;
    background:rgba(0,0,0,.22);border:1px solid var(--border-soft);border-radius:8px;
    padding:5px 9px;margin-top:10px;display:inline-block;word-break:break-all}

  .issue{display:inline-flex;align-items:center;gap:6px;margin-top:10px;padding:5px 12px;border-radius:999px;
    background:rgba(248,113,113,.12);border:1px solid rgba(248,113,113,.35);color:#fca5a5;font-size:11.5px;font-weight:700}
  .issue.warn{background:rgba(251,146,60,.12);border-color:rgba(251,146,60,.35);color:#fdba74}

  .stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:18px}
  .stat{background:rgba(6,12,24,.55);border:1px solid var(--border-soft);border-radius:13px;padding:11px 10px;text-align:left}
  .stat b{display:block;font-family:'JetBrains Mono',monospace;font-size:14.5px;margin-bottom:3px;word-break:break-word;font-weight:600}
  .stat span{color:#7d92aa;font-size:10.5px;text-transform:uppercase;letter-spacing:.3px}

  .section-title{font-size:12px;margin:18px 0 10px;color:#93a7be;text-transform:uppercase;letter-spacing:.6px;font-weight:700}
  .history{display:flex;flex-direction:column;gap:6px;max-height:180px;overflow-y:auto;padding-right:2px}
  .history::-webkit-scrollbar{width:5px}
  .history::-webkit-scrollbar-thumb{background:#1e3552;border-radius:10px}
  .row{display:flex;justify-content:space-between;align-items:center;gap:10px;
    background:rgba(6,12,24,.5);border:1px solid var(--border-soft);border-radius:10px;
    padding:8px 12px;font-size:11.5px}
  .row .t{color:#7d92aa;font-family:'JetBrains Mono',monospace;font-size:10.5px}
  .ok{color:var(--green);font-weight:700}
  .fail{color:var(--red);font-weight:700}

  footer{text-align:center;color:#5c7290;font-size:12px;padding:34px 0 12px}
  #targets{margin-top:4px}
  .empty{padding:40px;text-align:center;color:var(--muted);font-size:13px}

  @media(max-width:820px){.summary{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="brand">
        <div class="logo">M</div>
        <div>
          opshub-monitor
          <small>Live health telemetry over opshub-net</small>
        </div>
      </div>
      <div class="badge"><span class="pulse"></span> Checking every __INTERVAL__s, concurrently</div>
    </header>

    <div class="summary" id="summary">
      <div class="tile total"><div class="n">–</div><div class="l">Targets</div></div>
      <div class="tile healthy"><div class="n">–</div><div class="l">Healthy</div></div>
      <div class="tile issues"><div class="n">–</div><div class="l">With issues</div></div>
      <div class="tile avg"><div class="n">–</div><div class="l">Avg response</div></div>
    </div>

    <div id="targets" class="grid"><div class="empty">Loading targets…</div></div>

    <footer>opshub-monitor • isolated health sidecar over Docker networking</footer>
  </div>

<script>
function targetCard(name, data) {
  let cardClass = 'card', dotClass = 'dot', statusText = 'Healthy';
  if (data.status === 'healthy' && data.issue === 'slow_response') {
    cardClass += ' slow'; dotClass += ' slow'; statusText = 'Healthy, but slow';
  } else if (data.status === 'healthy') {
    statusText = 'Healthy';
  } else if (data.status === 'unknown') {
    cardClass += ' unknown'; dotClass += ' unknown'; statusText = 'Waiting for first check…';
  } else {
    cardClass += ' bad'; dotClass += ' bad'; statusText = 'Unhealthy';
  }

  const issueBadge = (data.issue && data.status !== 'unknown')
    ? `<div class="issue ${data.status === 'healthy' ? 'warn' : ''}">⚠ ${data.issue}</div>` : '';

  const events = (data.events || []).slice().reverse();
  const historyHtml = events.length === 0
    ? '<div class="muted">No state changes yet — status has been stable.</div>'
    : events.map(e => `
        <div class="row">
          <span class="t">${e.time}</span>
          <span class="${e.to === 'healthy' ? 'ok' : 'fail'}">${e.from} → ${e.to}${e.issue ? ' (' + e.issue + ')' : ''}</span>
        </div>
      `).join('');

  return `
    <div class="${cardClass}">
      <div class="cardhead">
        <div>
          <div class="name">${name}</div>
          <div class="health"><span class="${dotClass}"></span> ${statusText}</div>
        </div>
      </div>
      ${issueBadge}
      <div><span class="target-url">${data.target || '-'}</span></div>
      <div class="stats">
        <div class="stat"><b>${data.response_ms != null ? data.response_ms + ' ms' : '-'}</b><span>Response</span></div>
        <div class="stat"><b>${data.last_checked ? data.last_checked.slice(11,19) : '-'}</b><span>Last check</span></div>
        <div class="stat"><b>${data.consecutive_failures}</b><span>Fail streak</span></div>
      </div>
      <div class="section-title">State changes</div>
      <div class="history">${historyHtml}</div>
    </div>
  `;
}

function renderSummary(data) {
  const names = Object.keys(data);
  const total = names.length;
  const healthy = names.filter(n => data[n].status === 'healthy' && data[n].issue !== 'slow_response').length;
  const issues = total - healthy;
  const times = names.map(n => data[n].response_ms).filter(v => v != null);
  const avg = times.length ? Math.round(times.reduce((a,b)=>a+b,0) / times.length) : null;

  const el = document.getElementById('summary');
  el.innerHTML = `
    <div class="tile total"><div class="n">${total}</div><div class="l">Targets</div></div>
    <div class="tile healthy"><div class="n">${healthy}</div><div class="l">Healthy</div></div>
    <div class="tile issues"><div class="n">${issues}</div><div class="l">With issues</div></div>
    <div class="tile avg"><div class="n">${avg != null ? avg + 'ms' : '-'}</div><div class="l">Avg response</div></div>
  `;
}

async function refresh() {
  const el = document.getElementById('targets');
  try {
    const res = await fetch('/status', {cache: 'no-store'});
    const data = await res.json();
    const names = Object.keys(data);
    if (names.length === 0) {
      el.innerHTML = '<div class="empty">No targets configured.</div>';
      return;
    }
    renderSummary(data);
    el.innerHTML = names.map(name => targetCard(name, data[name])).join('');
  } catch (e) {
    el.innerHTML = '<div class="empty">Unable to reach monitor API.</div>';
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
        body = json.dumps(payload, indent=2).encode()
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
            self._send_html(DASHBOARD_HTML.replace("__INTERVAL__", str(POLL_INTERVAL_SECONDS)))
        elif self.path == "/status":
            with state_lock:
                self._send_json({name: dict(s) for name, s in state.items()})
        elif self.path == "/health":
            self._send_json({"status": "healthy", "service": "opshub-monitor"})
        else:
            self._send_json({"error": "not found"}, code=404)

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    for _name, _url in TARGETS.items():
        threading.Thread(target=poll_target_forever, args=(_name, _url), daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", 9090), Handler)
    print(
        "opshub-monitor listening on :9090, watching concurrently: %s (every %ss)"
        % (list(TARGETS.keys()), POLL_INTERVAL_SECONDS),
        flush=True,
    )
    server.serve_forever()
