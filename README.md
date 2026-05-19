# Photobooth Platform

Touchscreen photobooth met DSLR camera, LED-verlichting, en een online admin portaal.

## Apps

| App | Directory | Tech | Beschrijving |
|---|---|---|---|
| **Admin** | `apps/admin/` | Next.js | Beheer dashboard |
| **API** | `apps/api/` | Python / FastAPI | REST API + WebSocket hub |
| **Booth** | `apps/booth/` | Python / Kivy | Photobooth app op Raspberry Pi |
| **Viewer** | `apps/viewer/` | Next.js | Publieke foto viewer per event |
| **Shared** | `packages/shared/` | Python | Gedeeld WS protocol + constants |

## Quick start (dev)

```bash
# Alle services via Docker
cp .env.example .env   # vul SMTP credentials in
docker compose up --build

# Of los draaien:
cd apps/api && pip install -e . && python -m api
cd apps/admin && npm install && npm run dev
```

## Subdomeinen

- `photobooth-api.mycreativity.nl` — API server
- `photobooth-admin.mycreativity.nl` — Admin dashboard
- `photobooth.mycreativity.nl` — Publieke foto viewer

## Booth deployment

```bash
cd apps/booth/ansible
ansible-playbook -i inventory.ini deploy.yml
```
