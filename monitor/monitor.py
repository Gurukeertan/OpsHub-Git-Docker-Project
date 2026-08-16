import json
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

TARGET = os.getenv("TARGET_CONTAINER", "opshub")


def docker_request(path):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect("/var/run/docker.sock")

    request = (
        f"GET {path} HTTP/1.1\r\n"
        "Host: docker\r\n"
        "Connection: close\r\n\r\n"
    )

    client.sendall(request.encode())

    data = b""

    while True:
        chunk = client.recv(4096)

        if not chunk:
            break

        data += chunk

    client.close()

    # Separate HTTP headers and body
    header_end = data.find(b"\r\n\r\n")

    if header_end == -1:
        raise Exception("Invalid Docker API response")

    headers = data[:header_end].decode(errors="ignore")
    body = data[header_end + 4:]

    # Docker API may use chunked transfer encoding
    if "Transfer-Encoding: chunked" in headers:

        decoded = b""
        position = 0

        while position < len(body):

            line_end = body.find(b"\r\n", position)

            if line_end == -1:
                break

            size_line = body[position:line_end]

            try:
                size = int(size_line, 16)
            except ValueError:
                break

            position = line_end + 2

            if size == 0:
                break

            decoded += body[position:position + size]

            position += size + 2

        body = decoded

    return json.loads(body.decode())


def get_stats():

    try:

        info = docker_request(
            f"/containers/{TARGET}/json"
        )

        running = info["State"]["Running"]

        status = (
            "HEALTHY"
            if running
            else "UNHEALTHY"
        )

        return {
            "container": TARGET,
            "status": status,
            "running": running,
            "image": info["Config"]["Image"],
            "started_at": info["State"].get(
                "StartedAt",
                ""
            ),
            "restart_count": info.get(
                "RestartCount",
                0
            ),
            "timestamp": time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }

    except Exception as e:

        return {
            "container": TARGET,
            "status": "UNHEALTHY",
            "running": False,
            "image": "unknown",
            "started_at": "",
            "restart_count": 0,
            "timestamp": time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "error": str(e)
        }


HTML = """
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width,initial-scale=1">

<title>OpsHub Live Monitoring</title>

<style>

* {
    box-sizing: border-box;
}

body {

    margin: 0;

    font-family:
        Arial,
        sans-serif;

    background: #07111f;

    color: #e8eef7;
}

.container {

    max-width: 1100px;

    margin: auto;

    padding: 35px;
}

header {

    display: flex;

    justify-content:
        space-between;

    align-items:
        center;

    margin-bottom: 30px;
}

.logo {

    font-size: 25px;

    font-weight: bold;
}

.badge {

    padding: 9px 15px;

    border-radius: 20px;

    background: #10263a;

    color: #63e6c4;
}

.hero {

    margin-bottom: 25px;
}

h1 {

    font-size: 45px;

    margin: 10px 0;
}

.subtitle {

    color: #8fa3b8;
}

.status {

    padding: 25px;

    border-radius: 18px;

    background: #0d1b2b;

    border: 1px solid #1b344b;

    margin-bottom: 20px;
}

.status h2 {

    margin-top: 0;
}

.status-indicator {

    font-size: 30px;

    font-weight: bold;
}

.healthy {

    color: #34d399;
}

.unhealthy {

    color: #fb7185;
}

.grid {

    display: grid;

    grid-template-columns:
        repeat(3, 1fr);

    gap: 15px;
}

.card {

    background: #0d1b2b;

    border: 1px solid #1b344b;

    border-radius: 16px;

    padding: 22px;
}

.label {

    color: #8296aa;

    font-size: 13px;

    margin-bottom: 10px;
}

.value {

    font-size: 20px;

    font-weight: bold;

    word-break: break-word;
}

.footer {

    margin-top: 30px;

    color: #637990;

    font-size: 13px;
}

@media(max-width:700px) {

    .grid {

        grid-template-columns: 1fr;
    }

    h1 {

        font-size: 35px;
    }

}

</style>

</head>


<body>


<div class="container">


<header>

<div class="logo">

⚙ OpsHub

</div>

<div class="badge">

LIVE MONITORING

</div>

</header>


<div class="hero">

<div class="subtitle">

Docker Infrastructure Monitoring

</div>

<h1>

Deployment Control Center

</h1>

<div class="subtitle">

Real-time container status monitoring

</div>

</div>


<div class="status">

<h2>

System Status

</h2>

<div
id="status"
class="status-indicator">

Checking...

</div>

<p id="last-check">

</p>

</div>


<div class="grid">


<div class="card">

<div class="label">

CONTAINER

</div>

<div
id="container"
class="value">

-

</div>

</div>


<div class="card">

<div class="label">

IMAGE

</div>

<div
id="image"
class="value">

-

</div>

</div>


<div class="card">

<div class="label">

RUNTIME

</div>

<div
id="running"
class="value">

-

</div>

</div>


<div class="card">

<div class="label">

STARTED AT

</div>

<div
id="started"
class="value">

-

</div>

</div>


<div class="card">

<div class="label">

RESTART COUNT

</div>

<div
id="restart"
class="value">

-

</div>

</div>


<div class="card">

<div class="label">

CHECK INTERVAL

</div>

<div class="value">

2 seconds

</div>

</div>


</div>


<div class="footer">

OpsHub Monitoring
•
Git + Docker Infrastructure Lab

</div>


</div>


<script>


async function monitor() {


try {


const response =

await fetch(
    "/api/status"
);


const data =

await response.json();


const status =

document.getElementById(
    "status"
);


status.textContent =

data.status === "HEALTHY"

? "● HEALTHY"

: "● UNHEALTHY";


status.className =

"status-indicator " +

(
    data.status === "HEALTHY"

    ? "healthy"

    : "unhealthy"
);


document.getElementById(
    "container"
).textContent =

data.container;


document.getElementById(
    "image"
).textContent =

data.image;


document.getElementById(
    "running"
).textContent =

data.running

? "RUNNING"

: "STOPPED";


document.getElementById(
    "started"
).textContent =

data.started_at || "-";


document.getElementById(
    "restart"
).textContent =

data.restart_count;


document.getElementById(
    "last-check"
).textContent =

"Last check: " +
data.timestamp;


}

catch (error) {


document.getElementById(
    "status"
).textContent =

"● MONITOR ERROR";


}

}


monitor();


setInterval(
    monitor,
    2000
);


</script>


</body>

</html>
"""


class Handler(
    BaseHTTPRequestHandler
):


    def do_GET(self):


        if self.path == "/api/status":


            data = get_stats()


            body = json.dumps(
                data
            ).encode()


            self.send_response(
                200
            )


            self.send_header(
                "Content-Type",
                "application/json"
            )


            self.send_header(
                "Content-Length",
                str(len(body))
            )


            self.end_headers()


            self.wfile.write(
                body
            )


        else:


            body = HTML.encode()


            self.send_response(
                200
            )


            self.send_header(
                "Content-Type",
                "text/html"
            )


            self.send_header(
                "Content-Length",
                str(len(body))
            )


            self.end_headers()


            self.wfile.write(
                body
            )


server = HTTPServer(
    ("0.0.0.0", 8080),
    Handler
)


print(
    "OpsHub Monitor started on port 8080"
)


server.serve_forever()
