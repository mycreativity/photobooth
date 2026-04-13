# Photobooth Platform

Touchscreen photobooth met DSLR camera, LED-verlichting, en een online admin portaal.

## Apps

| App | Directory | Tech | Beschrijving |
|---|---|---|---|
| **Booth** | `booth/` | Python / Kivy | Photobooth app op Raspberry Pi |
| **Server** | `server/` | Python / FastAPI | REST API + WebSocket hub |
| **Admin** | `admin/` | Next.js | Beheer dashboard |
| **Shared** | `shared/` | Python | Gedeeld WS protocol |

## Quick start (dev)

```bash
# Server + Admin via Docker
cp .env.example .env   # vul SMTP credentials in
docker compose up --build

# Of los draaien:
cd server && pip install -e . && python -m server
cd admin && npm install && npm run dev
```

## Subdomeinen

- `api.mycreativity.nl` — API server
- `admin.mycreativity.nl` — Admin dashboard
- `booth.mycreativity.nl` — Publieke gasten app

## Booth deployment

```bash
cd booth/ansible
ansible-playbook -i inventory.ini deploy.yml
```
