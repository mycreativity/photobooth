# [STORY-001] App Restructure & Naming Review

> **Status:** ✅ Done
> **Priority:** 🟡 Medium
> **Component:** infra
> **Estimate:** M

---

## User Story

**Als** ontwikkelaar,
**wil ik** de 4 apps hernoemen en verplaatsen naar een `apps/` parent folder,
**zodat** de monorepo-structuur overzichtelijker is en de app-namen beter beschrijven wat ze doen.

---

## Context & Motivatie

Het project heeft momenteel 4 apps los in de root:

| Huidige folder | Type | Tech | Beschrijving |
|---|---|---|---|
| `admin/` | Frontend | Next.js | Admin dashboard voor booth-beheer |
| `booth/` | Desktop app | Python/Kivy | Photobooth software op RPI4 |
| `public/` | Frontend | Next.js | Foto-viewer per event code (QR/URL) |
| `server/` | Backend | Python/FastAPI | API voor booth, admin en public |
| `shared/` | Library | Python | Gedeeld WebSocket protocol |

### Definitieve naming

| Huidig | Nieuw | Reden |
|--------|-------|-------|
| `admin/` | **`apps/admin/`** | Naam behouden, alleen verplaatst |
| `server/` | **`apps/api/`** | "api" beschrijft de rol duidelijker |
| `booth/` | **`apps/booth/`** | Naam behouden, alleen verplaatst |
| `public/` | **`apps/viewer/`** | "viewer" beschrijft de functie, geen conflict met Next.js |
| `shared/` | **`packages/shared/`** | Library, geen app — eigen plek |

### Doel-structuur

```
photobooth/
├── apps/
│   ├── admin/        → Beheer dashboard (Next.js)
│   ├── api/          → FastAPI backend (was: server)
│   ├── booth/        → RPI4 photobooth client (Python/Kivy)
│   └── viewer/       → Publieke foto viewer (was: public, Next.js)
├── packages/
│   └── shared/       → Gedeeld WS protocol + constants + card layout
├── data/             → Bind mount: SQLite DB + uploaded photos
├── docker-compose.yml
└── ...
```

### `packages/shared/` inhoud (4 bestanden)

Huidige inhoud is compact en coherent — geen verdere substructuur nodig:

| Bestand | Inhoud |
|---------|--------|
| `protocol.py` | WebSocket message/command enums (`BoothMessage`, `ServerCommand`, `BoothStatus`, `Role`) |
| `constants.py` | Token lifetimes, heartbeat config, domeinnamen, card layout loader |
| `card_layout.json` | Print layout configuratie (canvas, branding, foto-slots) |
| `__init__.py` | Lege module init |

→ Flat structuur is prima. Pas subfolders overwegen als er meer packages bijkomen (bv. `packages/ui/` voor gedeelde React components).

---

## Acceptance Criteria

- [ ] AC1: Alle 4 apps verplaatst naar `apps/` folder via `git mv`
- [ ] AC2: `public/` hernoemd naar `apps/viewer/`, `server/` naar `apps/api/`
- [ ] AC3: `shared/` verplaatst naar `packages/shared/`
- [ ] AC4: `docker-compose.yml` bijgewerkt:
  - Build paden (`./apps/admin`, `./apps/api`, `./apps/viewer`)
  - Volume mounts (bind mounts i.p.v. named volumes)
  - Service namen (`server` → `api`, `public` → `viewer`)
  - Container namen (`pb-server` → `pb-api`, `pb-public` → `pb-viewer`)
- [ ] AC5: Traefik subdomeinen bijgewerkt:
  - `api.mycreativity.nl` → `photobooth-api.mycreativity.nl`
  - `admin.mycreativity.nl` → `photobooth-admin.mycreativity.nl`
  - `booth.mycreativity.nl` → `photobooth.mycreativity.nl`
- [ ] AC6: `packages/shared/constants.py` domeinnamen bijgewerkt
- [ ] AC7: Environment variabelen: `SERVER_URL` → `API_URL` (in docker-compose, .env, .env.example)
- [ ] AC8: Docker named volume `server-data` → bind mount `./data:/data`
- [ ] AC9: Ansible deploy scripts bijgewerkt:
  - `local_repo` pad aangepast
  - Extra sync task voor `packages/shared/` → `/opt/photobooth/shared/`
- [ ] AC10: Hardcoded paden in `print_layouts.py` bijgewerkt voor nieuwe structuur
- [ ] AC11: `README.md` bijgewerkt met nieuwe structuur en subdomeinen
- [ ] AC12: Alle apps starten correct na restructure (`docker compose up --build`)

---

## Technische Notities

| Aspect | Detail |
|--------|--------|
| Bestanden | `docker-compose.yml`, `README.md`, `.env`, `.env.example`, `booth/ansible/`, `shared/constants.py`, `booth/src/.../print_layouts.py` |
| Dependencies | Docker bind mounts, Traefik labels, Ansible synchronize |
| Database changes | Geen (PostgreSQL migratie → STORY-002) |
| API changes | Geen |

### Beslissingen uit refinement

| Beslissing | Keuze | Reden |
|------------|-------|-------|
| Ansible deploy strategie | Twee aparte sync tasks (booth + shared) | Schoon, expliciet, minimale data naar Pi |
| Subdomeinen | `photobooth-api`, `photobooth-admin`, `photobooth` | Specifiek voor photobooth op gedeeld domein |
| Container namen | `pb-api`, `pb-admin`, `pb-viewer` | Consistent met app-naamgeving |
| Docker volumes | Bind mounts (`./data:/data`) | Direct zichtbaar op host, makkelijk te backuppen |
| ENV variabelen | `SERVER_URL` → `API_URL` | Consistent met "api" naamgeving |
| PostgreSQL migratie | Aparte story (STORY-002) | Andere scope, ander risicoprofiel |

### Impact-analyse

- **docker-compose.yml**: Build paden, volumes, service/container namen, Traefik labels, env vars
- **shared/constants.py**: Drie domein-constanten updaten
- **print_layouts.py**: Hardcoded fallback paden naar shared/ updaten
- **Ansible deploy.yml**: `local_repo` pad + extra sync task voor packages/shared
- **.env / .env.example**: `SERVER_URL` → `API_URL`
- **README.md**: Tabel, voorbeelden, subdomeinen bijwerken
- **Interne imports**: Geen impact (alles is relatief binnen elke app)
- **CI/CD**: N.v.t. (geen CI pipelines)

---

## Out of Scope

- Monorepo tooling toevoegen (turborepo, nx, etc.)
- Package manager migratie (pnpm workspaces etc.)
- App code refactoring — alleen verplaatsen en hernoemen
- Database migratie SQLite → PostgreSQL (→ STORY-002)

---

## Open Vragen

- [x] ~~**Naming `public` →** `viewer`~~ ✅
- [x] ~~**Naming `server` →** `api`~~ ✅
- [x] ~~**Naming `admin` →** behouden~~ ✅
- [x] ~~**Naming `booth` →** behouden~~ ✅
- [x] ~~**`shared/` positie →** `packages/shared/` (flat, geen substructuur nodig)~~ ✅
- [x] ~~**Ansible strategie →** twee aparte sync tasks~~ ✅
- [x] ~~**Subdomeinen →** `photobooth-api`, `photobooth-admin`, `photobooth`~~ ✅
- [x] ~~**Container namen →** `pb-api`, `pb-admin`, `pb-viewer`~~ ✅
- [x] ~~**Docker volumes →** bind mounts~~ ✅
- [x] ~~**ENV vars →** `SERVER_URL` → `API_URL`~~ ✅
- [x] ~~**PostgreSQL →** aparte STORY-002~~ ✅

---

## Conversatie Log

_Notities uit de refinement sessie._

- 2026-05-16: Story aangemaakt. Naming review en restructure naar `apps/` folder.
- 2026-05-16: Naming beslissingen afgerond: `public` → `viewer`, `server` → `api`, rest behouden. `shared` → `packages/shared/` flat.
- 2026-05-16: Refinement sessie — beslissingen genomen over Ansible (twee sync tasks), subdomeinen (photobooth-prefixed), container namen (pb-api/pb-viewer), bind mounts i.p.v. named volumes, `SERVER_URL` → `API_URL`. PostgreSQL migratie als aparte STORY-002.
- 2026-05-19: Grill-me sessie — extra beslissingen: Python package `server` → `api` (42 imports), package naam `api` (simpel), viewer package.json name, root containers OK.
- 2026-05-19: Implementatie afgerond. Alle 8 fasen uitgevoerd. Docker build + start geverifieerd (pb-api :8000, pb-admin :3000, pb-viewer :3001). Data hersteld uit oude named volume naar bind mount. Orphan containers opgeruimd. STORY-002 (PostgreSQL) aangemaakt als follow-up.
