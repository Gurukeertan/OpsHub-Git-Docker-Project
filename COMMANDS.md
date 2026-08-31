# OpsHub — Git + Docker Command Guide

## 1. Project goal

Build and package a production-style internal deployment dashboard using **only Git and Docker**.

Scenario: a DevOps/platform team maintains a lightweight internal operations portal. The application is version-controlled in Git and shipped as a reproducible Docker image running behind Nginx.

## 2. Tools used

- Git — source control, version history, branching and release tags
- Docker — image creation, container runtime and reproducible packaging
- Nginx — web server inside the Docker image

No Kubernetes, Jenkins, GitHub Actions, cloud service, or application framework is required.

## 2a. Architecture: 3 containers over one Docker network

The stack now runs **three** containers, all on a dedicated Docker
bridge network (`opshub-net`):

- **opshub** — the Nginx-served dashboard (`Dockerfile`), exposing `/health` on port 80.
- **opshub-worker** — a small Python service (`worker/`) standing in for a background worker/queue-consumer, exposing `/health` on port 7070.
- **opshub-monitor** — a Python service (`monitor/`) that concurrently polls both `opshub` and `opshub-worker` over the internal Docker network (using Docker's built-in service-name DNS resolution), classifies failures (timeout, connection refused, DNS failure, bad HTTP status, slow response), and only logs/alerts on an actual state *change* rather than every poll. It serves a live HTML dashboard on port 9090.

```bash
docker compose up -d --build
docker compose ps

curl http://localhost:8080/health          # opshub
curl http://localhost:7070/health          # opshub-worker
curl http://localhost:9090/status          # opshub-monitor raw JSON

docker compose down
```

Open `http://localhost:9090` for the live dashboard — auto-refreshes
every 3s and shows both targets side by side.

### Adding a 4th (or Nth) container to be monitored

1. Add the new service to `docker-compose.yml`, on `opshub-net`.
2. Add it to `opshub-monitor`'s `MONITOR_TARGETS` env var: `name=http://service-name:port/health`.
3. `docker compose up -d --build` — no code changes required.

## 3. Create the project from scratch

```bash
mkdir opshub
cd opshub

touch index.html Dockerfile nginx.conf COMMANDS.md

git init
git branch -M main
```

Copy the project files into the directory.

## 4. Verify files

```bash
ls
cat Dockerfile
cat nginx.conf
```

## 5. First Git commit

```bash
git status
git add .
git commit -m "feat: create OpsHub deployment dashboard"
git log --oneline
```

## 6. Build the Docker image

```bash
docker build -t opshub:v1 .
docker images
```

## 7. Run the application

```bash
docker run -d --name opshub -p 8080:80 opshub:v1
docker ps
```

Open in a browser:

```text
http://localhost:8080
```

Health check:

```bash
curl http://localhost:8080/health
```

Expected:

```text
healthy
```

## 8. Inspect the running container

```bash
docker logs opshub
docker inspect opshub
docker exec -it opshub sh
```

Inside the container:

```bash
nginx -t
exit
```

## 9. Stop and remove the container

```bash
docker stop opshub
docker rm opshub
```

## 10. Simulate a production update

Edit `index.html` and change the release version, for example:

```text
v1.4.2
```

to:

```text
v1.5.0
```

Then create a Git change:

```bash
git status
git diff
git add index.html
git commit -m "release: update dashboard to v1.5.0"
```

## 11. Build a new release image

```bash
docker build -t opshub:v1.5.0 .
docker images
```

Run the new version:

```bash
docker run -d --name opshub-v150 -p 8081:80 opshub:v1.5.0
```

Test:

```bash
curl http://localhost:8081/health
```

Open:

```text
http://localhost:8081
```

## 12. Tag the Git release

```bash
git tag -a v1.5.0 -m "OpsHub release v1.5.0"
git tag
git show v1.5.0
```

## 13. Demonstrate rollback

Because Docker images are versioned, rollback does not require rebuilding.

Stop the new version:

```bash
docker stop opshub-v150
docker rm opshub-v150
```

Start the previous known-good image:

```bash
docker run -d --name opshub -p 8080:80 opshub:v1
```

Verify:

```bash
docker ps
curl http://localhost:8080/health
```

This demonstrates a basic image-based rollback strategy.

## 14. Useful Docker cleanup

List containers:

```bash
docker ps -a
```

List images:

```bash
docker images
```

Remove an image:

```bash
docker rmi opshub:v1
```

Remove stopped containers:

```bash
docker container prune
```

Remove unused images:

```bash
docker image prune
```

## 15. Git branching scenario

Create a feature branch:

```bash
git checkout -b feature/dashboard-update
```

After making changes:

```bash
git status
git diff
git add .
git commit -m "feat: improve operations dashboard"
```

Return to main:

```bash
git checkout main
```

Merge:

```bash
git merge feature/dashboard-update
```

Delete the feature branch:

```bash
git branch -d feature/dashboard-update
```

## 16. Complete verification

```bash
git status
git log --oneline --decorate --graph --all
git tag

docker images
docker ps

curl http://localhost:8080
curl http://localhost:8080/health
```

## 17. What this project demonstrates

- Git repository initialization
- Meaningful Git commits
- Feature branching and merging
- Release tagging
- Dockerfile creation
- Docker image versioning
- Container lifecycle management
- Port mapping
- Container inspection and logs
- Nginx-based production-style serving
- Health endpoint
- Versioned release deployment
- Basic rollback using a previous Docker image
- Reproducible application packaging

## 18. Portfolio/project title

**OpsHub — Production-Style Deployment Control Center Using Git & Docker**

Recommended resume description:

> Built a production-style deployment dashboard and packaged it as a versioned Docker image, using Git for source control, release tagging, feature branching, Nginx-based serving, container health verification, and image-based rollback.
