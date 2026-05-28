# Deployment Guide — TaxPilot

This guide covers three deployment topologies in increasing order of production-readiness:

1. **Local development** (single-machine, Docker Compose)
2. **Single-VPS production** (Hetzner / DigitalOcean, suitable for 1–50 firms)
3. **Managed-cloud production** (AWS Mumbai, MongoDB Atlas, suitable for 50+ firms)

---

## 1. Local development

### Prerequisites

- Python 3.11
- Node.js 20+, Yarn 1.22
- MongoDB 7 (local or Atlas free tier)

### Run

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill MONGO_URL and DB_NAME
uvicorn server:app --reload --host 0.0.0.0 --port 8001

# 2. Frontend
cd ../frontend
yarn install
yarn start              # opens http://localhost:3000
```

On first startup the backend auto-seeds demo data (1 CA firm, 3 clients, 6 mismatches, 5 TDS entries, 9 compliance items). Re-seed at any time via the "Reset demo data" button in the sidebar.

### Environment variables

`backend/.env`
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=taxpilot
CORS_ORIGINS=http://localhost:3000
```

`frontend/.env`
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

---

## 2. Single-VPS production (Hetzner CX32 + Docker Compose)

Recommended for Year-1 (≤ 50 paying firms). Cost: ~€8/month for the VPS, ~₹3,000-5,000/month total ops cost.

### 2.1 Server provisioning

```bash
# Hetzner CX32: 4 vCPU, 8 GB RAM, 80 GB SSD, Falkenstein/Helsinki (€8/mo)
# Distro: Ubuntu 24.04 LTS
# Add SSH key on creation. Disable root password login.

# After login:
adduser deploy && usermod -aG sudo deploy
ufw allow OpenSSH && ufw allow http && ufw allow https && ufw enable
apt update && apt -y upgrade
apt -y install docker.io docker-compose-v2 nginx certbot python3-certbot-nginx
```

### 2.2 `docker-compose.yml`

```yaml
services:
  mongo:
    image: mongo:7
    restart: unless-stopped
    volumes:
      - mongo-data:/data/db
    environment:
      MONGO_INITDB_ROOT_USERNAME_FILE: /run/secrets/mongo_user
      MONGO_INITDB_ROOT_PASSWORD_FILE: /run/secrets/mongo_pass
    secrets: [mongo_user, mongo_pass]
    networks: [tp-net]

  backend:
    image: ghcr.io/sahilk/taxpilot-backend:latest
    restart: unless-stopped
    depends_on: [mongo]
    environment:
      MONGO_URL: mongodb://${MONGO_USER}:${MONGO_PASS}@mongo:27017/taxpilot?authSource=admin
      DB_NAME: taxpilot
      CORS_ORIGINS: https://app.taxpilot.in
    networks: [tp-net]

  frontend:
    image: ghcr.io/sahilk/taxpilot-frontend:latest
    restart: unless-stopped
    networks: [tp-net]

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on: [backend, frontend]
    networks: [tp-net]

secrets:
  mongo_user: { file: ./secrets/mongo_user }
  mongo_pass: { file: ./secrets/mongo_pass }

volumes:
  mongo-data:

networks:
  tp-net: {}
```

### 2.3 Nginx config

```nginx
worker_processes auto;
events { worker_connections 1024; }
http {
  upstream backend  { server backend:8001;  }
  upstream frontend { server frontend:3000; }

  server {
    listen 80;
    server_name app.taxpilot.in;
    return 301 https://$server_name$request_uri;
  }

  server {
    listen 443 ssl http2;
    server_name app.taxpilot.in;

    ssl_certificate     /etc/letsencrypt/live/app.taxpilot.in/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.taxpilot.in/privkey.pem;
    ssl_protocols TLSv1.3 TLSv1.2;
    ssl_prefer_server_ciphers off;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;

    client_max_body_size 12M;

    location /api/ {
      proxy_pass http://backend;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For  $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
    }
    location / {
      proxy_pass http://frontend;
      proxy_set_header Host $host;
    }
  }
}
```

### 2.4 Initial TLS

```bash
certbot --nginx -d app.taxpilot.in --email sahil@kumarca.in --agree-tos --no-eff-email
systemctl enable --now certbot.timer    # auto-renew
```

### 2.5 Backup

Daily encrypted mongodump → Cloudflare R2 (₹100/month for 100 GB).

```bash
# /etc/cron.daily/taxpilot-backup
#!/usr/bin/env bash
TS=$(date +%Y%m%d-%H%M%S)
docker compose -f /opt/taxpilot/docker-compose.yml exec -T mongo \
  mongodump --archive --gzip \
  --username "$MONGO_USER" --password "$MONGO_PASS" --authenticationDatabase admin \
  | gpg --encrypt --recipient backup@taxpilot.in --output "/tmp/tp-$TS.archive.gpg"

rclone copy "/tmp/tp-$TS.archive.gpg" r2:tp-backups/
rm "/tmp/tp-$TS.archive.gpg"
find /tmp -name "tp-*.archive.gpg" -mtime +1 -delete
```

### 2.6 Observability

| Component        | Tool                                              |
| ---------------- | ------------------------------------------------- |
| Error tracking   | Sentry (free tier 5k events/month)                |
| Uptime monitor   | BetterStack (free tier 10 monitors)               |
| Metrics          | Prometheus + Grafana Cloud (free tier 10k series) |
| Logs             | Loki (Grafana Cloud)                              |

## 3. Managed-cloud production (Year-2)

Scale point: ≥ 100 firms or ≥ 50 GB data.

### 3.1 Topology

```
  Cloudflare (WAF + CDN + DDoS)
              │
              ▼
   AWS Application Load Balancer (ap-south-1)
              │
        ┌─────┴─────┐
        ▼           ▼
    Fargate     Fargate
   (Backend)  (Frontend)     ── auto-scaling 2 → 8 tasks
        │
        ▼
   MongoDB Atlas (M30, ap-south-1, 3-node replica set)
        │
        ▼
   S3 Mumbai (document storage)
   CloudWatch (logs + metrics)
   AWS Secrets Manager (creds)
```

Estimated monthly cost at 100 firms / 2k clients: ~₹85,000/month (Atlas M30 ~₹17k, Fargate ~₹30k, ALB ~₹3k, S3 ~₹1k, CloudWatch ~₹3k, Cloudflare Pro ~₹2k, rest = data transfer + Sentry/observability).

### 3.2 IaC

Terraform module structure:

```
infra/
├── modules/
│   ├── vpc/
│   ├── ecs/
│   ├── mongo-atlas/
│   ├── s3/
│   └── cloudfront/
├── envs/
│   ├── staging/
│   └── prod/
└── README.md
```

## 4. CI/CD

`.github/workflows/deploy.yml`:

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r backend/requirements.txt
      - run: pip install pytest && pytest backend/tests
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && yarn install --frozen-lockfile && yarn test --watchAll=false

  build-and-push:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - run: docker build -t ghcr.io/sahilk/taxpilot-backend:${{ github.sha }}  ./backend
      - run: docker build -t ghcr.io/sahilk/taxpilot-frontend:${{ github.sha }} ./frontend
      - run: docker push ghcr.io/sahilk/taxpilot-backend:${{ github.sha }}
      - run: docker push ghcr.io/sahilk/taxpilot-frontend:${{ github.sha }}

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.PROD_HOST }}
          username: deploy
          key:  ${{ secrets.PROD_SSH_KEY }}
          script: |
            cd /opt/taxpilot
            docker compose pull
            docker compose up -d
            docker image prune -f
```

## 5. Runbooks

### 5.1 Restoring a backup

```bash
ssh deploy@app.taxpilot.in
rclone copy r2:tp-backups/tp-20260115-080000.archive.gpg /tmp/
gpg --decrypt /tmp/tp-20260115-080000.archive.gpg > /tmp/restore.archive
docker compose exec -T mongo mongorestore \
  --archive --gzip --drop --nsInclude "taxpilot.*" \
  --username "$MONGO_USER" --password "$MONGO_PASS" --authenticationDatabase admin \
  < /tmp/restore.archive
```

### 5.2 Rolling back a deploy

```bash
ssh deploy@app.taxpilot.in
docker pull ghcr.io/sahilk/taxpilot-backend:<previous-sha>
docker pull ghcr.io/sahilk/taxpilot-frontend:<previous-sha>
docker compose up -d
```

### 5.3 Adding a new CA firm (admin task)

Until self-serve signup ships in Phase 1, new firms are created via:

```bash
docker compose exec backend python -c "
import asyncio
from server import db, _now
async def add():
    await db.firms.insert_one({...})
asyncio.run(add())
"
```

### 5.4 Incident response

| Severity | Definition                                        | Response time |
| -------- | ------------------------------------------------- | ------------- |
| SEV-1    | Customer data exposed / production fully down     | 15 minutes    |
| SEV-2    | Major feature broken for all users                | 1 hour        |
| SEV-3    | Single-customer issue or non-critical feature     | 4 business hours |
| SEV-4    | Cosmetic / documentation                          | Next sprint   |

Post-incident review (PIR) within 5 business days for all SEV-1 and SEV-2.

## 6. Quick reference

| Need to…                       | Command                                                    |
| ------------------------------ | ---------------------------------------------------------- |
| Restart services               | `sudo supervisorctl restart backend frontend`              |
| Tail logs                      | `tail -f /var/log/supervisor/backend.err.log`              |
| Re-seed demo data              | `curl -X POST $API/seed/reset`                             |
| Check health                   | `curl $API/health`                                         |
| Run frontend lint              | `cd frontend && yarn lint`                                 |
| Run backend lint               | `cd backend && ruff check .`                               |
| MongoDB shell                  | `docker compose exec mongo mongosh -u $MONGO_USER -p`      |
