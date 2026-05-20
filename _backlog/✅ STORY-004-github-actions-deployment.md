# [STORY-004] CI/CD Deployment Pipeline via GitHub Actions

> **Status:** ✅ Done
> **Priority:** 🟠 High
> **Component:** infra
> **Estimate:** M

---

## User Story

**Als** ontwikkelaar,
**wil ik** automatisch deployen naar mijn Hetzner productieserver bij een push naar `main`,
**zodat** deployments reproduceerbaar, betrouwbaar en hands-off zijn.

---

## Context & Motivatie

De photobooth stack draait op een Hetzner server met Traefik als reverse proxy. Momenteel worden deployments handmatig gedaan (SSH → pull → build). De bestaande GitHub repo (`mycreativity/photobooth`) bevat nog de oude PyGame-based photobooth app (32 commits). We hergebruiken deze repo: oude code taggen als `v1.0-legacy`, daarna force push met de nieuwe monorepo.

### Huidige productie-setup

| Aspect          | Waarde                                         |
| --------------- | ---------------------------------------------- |
| Server          | Hetzner VPS                                    |
| Services        | `pb-api`, `pb-admin`, `pb-viewer`              |
| Orchestratie    | Docker Compose                                 |
| Reverse proxy   | Traefik (extern `proxy` netwerk)               |
| Subdomeinen     | `photobooth-api.mycreativity.nl`, `photobooth-admin.mycreativity.nl`, `photobooth.mycreativity.nl` |
| Server pad      | `~/docker/photobooth`                          |
| GitHub repo     | `mycreativity/photobooth` (bestaand, hergebruiken) |

### Deployment strategie

**Build on server via SSH** (Optie A):
- GitHub Actions SSH't naar de server
- `cd ~/docker/photobooth && git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d`
- Simpel, geen registry nodig, kleine stack

### Branch & PR strategie

- Alleen `main` triggert deployment
- Werken met PRs per user story (feature branches)
- Flow: feature branch → PR → merge naar `main` → auto-deploy

---

## Acceptance Criteria

- [ ] AC1: Bestaande `mycreativity/photobooth` repo: oude code getagd als `v1.0-legacy`
- [ ] AC2: Lokale repo gepusht naar `mycreativity/photobooth` (force push naar `main`)
- [ ] AC3: GitHub Actions workflow (`.github/workflows/deploy.yml`) bestaat
- [ ] AC4: Push naar `main` triggert automatische deployment naar productie
- [ ] AC5: Alle drie services (`pb-api`, `pb-admin`, `pb-viewer`) worden correct gebouwd en herstart
- [ ] AC6: Secrets (`SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`) geconfigureerd als repository secrets
- [ ] AC7: Productie Dockerfiles bestaan voor alle drie services
- [ ] AC8: `docker-compose.prod.yml` override: geen dev volume mounts, alleen `./data:/data`
- [ ] AC9: Traefik labels en netwerk configuratie werkt correct na deployment
- [ ] AC10: Deployment faalt graceful bij build errors (geen half-gedeployde staat)

---

## Technische Notities

| Aspect           | Detail                                                                                          |
| ---------------- | ----------------------------------------------------------------------------------------------- |
| Bestanden        | `.github/workflows/deploy.yml`, `docker-compose.prod.yml` (nieuw), `apps/*/Dockerfile.prod`    |
| Dependencies     | GitHub repo, SSH keypair, deploy user op server                                                  |
| Database changes | Geen                                                                                             |
| API changes      | Geen                                                                                             |

### Wat moet wijzigen / aangemaakt worden

1. **GitHub repo voorbereiden**
   - Clone `mycreativity/photobooth` → tag huidige `main` als `v1.0-legacy` → push tag
   - Lokale repo: `git remote add origin git@github.com:mycreativity/photobooth.git`
   - Force push: `git push --force origin main`

2. **Productie Dockerfiles**
   - `apps/viewer/Dockerfile.prod` — multi-stage Next.js standalone build (kopie van admin)
   - `apps/api/Dockerfile.prod` — evalueren, huidige is mogelijk voldoende (geen editable install)

3. **`docker-compose.prod.yml`** (nieuw)
   - Override dev volume mounts (verwijderen)
   - Alleen `./data:/data` als bind mount
   - Verwijst naar `Dockerfile.prod` voor admin en viewer
   - Productie env vars (URLs naar subdomeinen)

4. **`.github/workflows/deploy.yml`** (nieuw)
   - Trigger: push naar `main`
   - Stap: SSH naar server → `cd ~/docker/photobooth && git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d`

5. **GitHub Secrets** (handmatig door gebruiker)
   - `SSH_HOST` — server IP/hostname
   - `SSH_USER` — deploy username
   - `SSH_PRIVATE_KEY` — ed25519 private key (nieuw keypair genereren)

6. **Server voorbereiding** (handmatig door gebruiker)
   - Deploy user aanmaken
   - Public key toevoegen aan `~/.ssh/authorized_keys`
   - `.env` bestand plaatsen in `~/docker/photobooth/.env`
   - Eerste keer: `git clone` van de repo

### Bestaande Dockerfiles status

| Service  | Dev Dockerfile | Prod Dockerfile | Actie nodig                             |
| -------- | -------------- | --------------- | --------------------------------------- |
| API      | ✅ Bestaat      | ❌ Ontbreekt     | Aanmaken (non-editable pip install)     |
| Admin    | ✅ Bestaat      | ✅ Bestaat       | Geen — multi-stage standalone OK        |
| Viewer   | ✅ Bestaat      | ❌ Ontbreekt     | Aanmaken (kopie van admin Dockerfile.prod) |

### Env vars strategie

`.env` staat handmatig op de server in `~/docker/photobooth/.env`. Wordt **niet** aangeraakt door de deploy pipeline. Bevat:
- `JWT_SECRET`
- SMTP credentials
- Productie URLs (`API_URL`, `ADMIN_URL`, `WS_URL`)
- `ADMIN_EMAIL`

---

## Out of Scope

- PostgreSQL migratie (→ STORY-003)
- Booth (Raspberry Pi) deployment — heeft eigen Ansible flow
- Staging environment / develop branch
- Automatische tests in de pipeline (aparte story)
- Rollback strategie
- Monitoring / alerting bij failed deploys
- GitHub Secrets configuratie (handmatig door gebruiker)
- Server user aanmaken (handmatig door gebruiker)

---

## Open Vragen

Geen — alle vragen beantwoord in refinement sessie.

---

## Conversatie Log

_Notities uit de refinement sessie._

- 2026-05-19: Story aangemaakt. Gebruiker wil CI/CD via GitHub Actions naar Hetzner productieserver.
- 2026-05-19: Refinement sessie afgerond. Beslissingen:
  - Repo: `mycreativity/photobooth` hergebruiken, oude code taggen als `v1.0-legacy`
  - Deployment: Optie A (build on server via SSH), geen GHCR
  - SSH: aparte deploy user, gebruiker configureert secrets (SSH_HOST, SSH_USER, SSH_PRIVATE_KEY)
  - Server pad: `~/docker/photobooth`
  - Env vars: `.env` handmatig op server, niet door CI
  - Prod Dockerfiles: meenemen in deze story (viewer + API ontbreken)
  - Docker Compose: `docker-compose.prod.yml` override, geen dev mounts, alleen `./data:/data`
  - Branch: alleen `main` deployt, PRs per user story
- 2026-05-19: Implementatie afgerond. Alle bestanden aangemaakt en gepusht. Iteratief gedebugged:
  - Git-based deploy → SCP-based deploy (server had geen GitHub SSH access)
  - Certresolver `letsencrypt` → `myresolver` (Traefik config match)
  - Port 3000 conflict → ports verwijderd in prod (Traefik routeert intern)
  - Next.js 16 standalone binding fix → `HOSTNAME=0.0.0.0`
  - Alle drie subdomeinen live: API, Admin, Viewer
