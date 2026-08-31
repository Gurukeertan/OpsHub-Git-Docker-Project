# OpsHub — Docker Infrastructure Monitoring Platform

OpsHub is a containerized infrastructure monitoring project built with **Docker and Docker Compose**. The project demonstrates a multi-container architecture consisting of a web dashboard, background worker, and monitoring service.

The project was developed in multiple versions, with **Version 2.0.0** introducing the Docker Compose-based multi-service architecture.

---

## Architecture

```text
                         ┌──────────────────────┐
                         │      User / Browser   │
                         └──────────┬───────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  │                 │                 │
                  ▼                 ▼                 ▼
            Port 8080          Port 7071          Port 9090
                  │                 │                 │
        ┌─────────▼────────┐ ┌─────▼────────────┐ ┌──▼─────────────────┐
        │     OpsHub       │ │  OpsHub Worker   │ │  OpsHub Monitor    │
        │                  │ │                  │ │                    │
        │ Nginx Web Server │ │ Background Jobs  │ │ Monitoring Service  │
        │                  │ │                  │ │                    │
        │ Dashboard        │ │ Dashboard: /     │ │ Health Monitoring  │
        └──────────────────┘ │ Health: /health  │ └─────────┬──────────┘
                              └─────────┬────────┘           │
                                        │                    │
                                        └────────┬───────────┘
                                                 │
                                      ┌──────────▼──────────┐
                                      │    opshub-net       │
                                      │  Docker Network     │
                                      └─────────────────────┘
```

### Components

| Service          | Description                                   | Container Port | Host Port |
| ---------------- | --------------------------------------------- | -------------: | --------: |
| `opshub`         | Nginx-based web dashboard                     |             80 |      8080 |
| `opshub-worker`  | Background job processor and worker dashboard |           7070 |      7071 |
| `opshub-monitor` | Monitors worker health and Docker services    |           9090 |      9090 |

> **Note:** The worker uses container port `7070`. The host port is mapped to `7071` because port `7070` was already being used by another Windows application.

---

## Features

* Multi-container Docker architecture
* Docker Compose orchestration
* Nginx-based web dashboard
* Background worker service
* Worker health endpoint
* Worker runtime statistics
* Queue depth monitoring
* Jobs processed tracking
* Monitoring service
* Container-to-container communication
* Dedicated Docker network
* Health/status monitoring
* Separate Dockerfiles for services
* Version-controlled development using Git
* GitHub releases and version tagging

---

## Project Structure

```text
OpsHub-Git-Docker-Project/
│
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── index.html
├── COMMANDS.md
│
├── monitor/
│   ├── Dockerfile
│   └── monitor.py
│
├── worker/
│   ├── Dockerfile
│   └── worker.py
│
└── README.md
```

---

## Technology Stack

* **Docker**
* **Docker Compose**
* **Nginx**
* **Python 3.12**
* **HTML**
* **CSS**
* **JavaScript**
* **Git**
* **GitHub**

---

## Docker Services

### 1. OpsHub

The main web interface is served using Nginx.

**Container port:**

```text
80
```

**Host port:**

```text
8080
```

Open:

```text
http://localhost:8080
```

---

### 2. OpsHub Worker

The worker is responsible for simulating background job processing and exposing runtime information.

It provides:

```text
/
```

for the worker dashboard and:

```text
/health
```

for health information.

Example health response:

```json
{
  "status": "ok",
  "service": "opshub-worker",
  "uptime_seconds": 299.9,
  "queue_depth": 4,
  "jobs_processed": 509
}
```

The worker runs on:

```text
Container: 7070
Host: 7071
```

Open:

```text
http://localhost:7071
```

Health endpoint:

```text
http://localhost:7071/health
```

---

### 3. OpsHub Monitor

The monitoring service observes the worker and provides monitoring information.

The monitor communicates with services through the Docker network:

```text
opshub-net
```

The monitoring service is exposed on:

```text
http://localhost:9090
```

---

## Docker Network

The services communicate through a dedicated Docker network created by Docker Compose.

```text
                 opshub-net
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
     opshub       worker       monitor
```

This allows containers to communicate using Docker service names instead of relying on host IP addresses.

---

## Getting Started

### Prerequisites

Install:

* Docker
* Docker Compose

Verify Docker:

```bash
docker --version
```

Verify Docker Compose:

```bash
docker compose version
```

---

## Clone the Repository

```bash
git clone https://github.com/Gurukeertan/OpsHub-Git-Docker-Project.git
```

Enter the project:

```bash
cd OpsHub-Git-Docker-Project
```

---

## Start the Application

Build and start all services:

```bash
docker compose up -d --build
```

Check running services:

```bash
docker compose ps
```

Expected services:

```text
opshub
opshub-monitor
opshub-worker
```

---

## Access the Services

### OpsHub Dashboard

```text
http://localhost:8080
```

### Worker Dashboard

```text
http://localhost:7071
```

### Worker Health

```text
http://localhost:7071/health
```

### Monitoring Dashboard

```text
http://localhost:9090
```

---

## Useful Docker Commands

### View running containers

```bash
docker compose ps
```

### View all containers

```bash
docker ps -a
```

### View logs

```bash
docker compose logs
```

### Worker logs

```bash
docker compose logs opshub-worker
```

### Monitor logs

```bash
docker compose logs opshub-monitor
```

### Follow logs in real time

```bash
docker compose logs -f
```

### Stop services

```bash
docker compose stop
```

### Start existing services

```bash
docker compose start
```

### Stop and remove containers

```bash
docker compose down
```

### Rebuild services

```bash
docker compose build --no-cache
```

### Rebuild and start

```bash
docker compose up -d --build
```

---

## Health Verification

Test the worker from the host:

```bash
curl http://localhost:7071/
```

Test the worker health endpoint:

```bash
curl http://localhost:7071/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "opshub-worker"
}
```

---

## Version History

### Version 1.0

The initial version introduced the OpsHub dashboard and live Docker monitoring functionality.

### Version 2.0.0

Version 2 introduced a multi-container Docker Compose architecture.

Major improvements:

* Added `opshub-worker`
* Added worker dashboard
* Added worker health endpoint
* Added background job simulation
* Added `opshub-monitor`
* Added Docker network communication
* Added separate Dockerfiles for worker and monitor
* Added Docker Compose orchestration
* Added project command documentation

---

## Git Workflow

The project uses Git for version control.

The repository maintains the original Version 1 history while introducing Version 2 as a new development stage.

Current release:

```text
v2.0.0
```

The version progression is:

```text
Version 1
   │
   ▼
Docker Monitoring
   │
   ▼
Version 2
   │
   ├── Docker Compose
   ├── Worker
   ├── Monitor
   └── Docker Networking
   │
   ▼
v2.0.0 Release
```

---

## Project Objectives

The main objectives of OpsHub are to demonstrate practical understanding of:

1. Containerization using Docker
2. Multi-container application architecture
3. Docker Compose
4. Docker networking
5. Service isolation
6. Background processing
7. Health monitoring
8. Container monitoring
9. Git version control
10. GitHub release management

---

## Troubleshooting

### Port 7070 is unavailable

The worker listens on port `7070` inside the container, but the host port is mapped to `7071`.

Check:

```bash
docker compose ps
```

Expected mapping:

```text
0.0.0.0:7071->7070/tcp
```

Access the worker using:

```text
http://localhost:7071
```

### Containers have stopped

Check:

```bash
docker compose ps -a
```

View logs:

```bash
docker compose logs --tail=100
```

Restart:

```bash
docker compose up -d
```

### Rebuild after code changes

```bash
docker compose up -d --build
```

---

## Author

**Guru Keertan R**

GitHub:

```text
https://github.com/Gurukeertan
```

Project:

```text
https://github.com/Gurukeertan/OpsHub-Git-Docker-Project
```

---

## License

This project is intended for educational and portfolio purposes.
