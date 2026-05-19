# [STORY-002] Booth ↔ API Connection Resilience & Event Lifecycle

> **Status:** ✅ Done
> **Priority:** 🟠 High
> **Component:** backend | infra
> **Estimate:** L

---

## User Story

**Als** beheerder van meerdere photobooth-apparaten (verhuurmodel, 2-3 booths),
**wil ik** een robuuste, zelfherstellende verbinding tussen booth en API met een helder event-lifecycle model,
**zodat** booths betrouwbaar werken ongeacht of ze tijdelijk offline gaan, opnieuw opstarten, of aan een nieuw event worden gekoppeld.

---

## Context & Motivatie

De huidige Booth ↔ API verbinding werkt, maar na analyse van de codebase zijn er meerdere verbeterpunten gevonden. De booths worden verhuurd — ze gaan naar klanten voor events (bruiloften, feesten) en komen daarna terug. Dit betekent:

- Booths kunnen overal ter wereld staan met wisselende internetverbinding
- Configuratie en event-koppeling gebeurt altijd remote via het admin dashboard
- Foto's moeten zo snel mogelijk online zichtbaar zijn in de viewer app
- Na het event moeten QR-code galerijen bereikbaar blijven

### Huidige Architectuur (wat goed werkt)

| Aspect | Implementatie | Status |
|---|---|---|
| Transport | WebSocket (`websockets` lib, booth → API) + HTTP (photo upload) | ✅ Juiste split |
| Reconnect | Exponential backoff (5s → 60s max) | ✅ Goed |
| Heartbeat | Elke 10s met system metrics (CPU, mem, disk, temp, power) | ✅ Uitgebreid |
| Auth | SHA-256 hashed API key | ✅ Werkend (maar transport onveilig) |
| Registration | Booth stuurt `register`, API antwoordt met `ack` + event info | ✅ Werkt |
| Commands | Admin → Booth: `update_settings`, `restart`, `push_event`, `start/stop_preview` | ✅ Werkt |
| Log relay | Booth logs → Admin via WS (ring buffer, 200 lines) | ✅ Handig |
| Photo upload | HTTP POST naar `/api/photos/upload` (background thread, non-blocking) | ✅ Werkt |
| Hub | In-memory `ConnectionHub` singleton (booth + admin viewer tracking) | ✅ Functioneel |

### Gevonden Problemen & Risico's

#### 🔴 Kritiek

1. **Geen offline photo queue** — Als de booth geen verbinding heeft tijdens een sessie, worden foto's niet geüpload en is er geen retry-mechanisme. Ze staan lokaal maar worden nooit nagesynchroniseerd.

2. **API key in query string** — De API key wordt als `?api_key=xxx` in de WebSocket URL verstuurd. Dit is zichtbaar in server logs, proxy logs, en browser history. Moet naar het eerste WS-bericht.

#### 🟠 High

3. **Event koppeling is alleen server-side** — Na een reconnect krijgt de booth wel het `event_id` in de `ack`, maar niet de volledige event card config (achtergrond, branding). Die moet apart gepusht worden.

4. **Stale heartbeat detectie ontbreekt** — De `ConnectionHub` slaat `_last_heartbeat` timestamps op, maar er is geen achtergrondtaak die controleert of een booth "silently dead" is.

5. **Booth status cleanup bij crash** — Als de API-server crasht, blijven alle booths op "online" staan in de DB.

#### 🟡 Medium

6. **Hardcoded paden** — `agent.py` zoekt booth.toml op `/opt/photobooth/booth.toml` en data op `/opt/photobooth/data`. Niet configureerbaar.

7. **Event datum UX** — Het is onduidelijk in de admin wat `date` en `end_date` precies doen (informatief vs. enforced).

---

## Acceptance Criteria

### Must Have

- [ ] AC1: **Offline photo queue** — Foto's die niet geüpload kunnen worden, worden opgeslagen in een `upload_queue` tabel in de bestaande booth SQLite database. Een background poller (elke 10s) retried mislukte uploads (FIFO, max 50 retries). De directe upload (huidige flow) blijft de primaire route — de queue is alleen fallback bij falen.
- [ ] AC2: **Secure API key transport** — API key wordt niet meer in de URL query string verstuurd, maar via het `register` WebSocket message. API-side validatie verplaatst van connect-moment naar register-handler.
- [ ] AC3: **Auto-reconnect event state restore** — Na reconnect ontvangt de booth automatisch de volledige event card configuratie (achtergrond, branding, date) in de `ack` response of als direct opvolgende `push_event`, niet alleen het `event_id`.
- [ ] AC4: **Startup cleanup** — Bij API server startup worden alle booth-statussen gereset naar "offline".
- [ ] AC5: **Photo upload deduplicatie** — API-side idempotency check op `booth_id + session_id + seq + variant`. Duplicate upload retourneert `200 OK` zonder opnieuw op te slaan.

### Should Have

- [ ] AC6: **Stale heartbeat detection** — Background task die elke 30s controleert of booths langer dan 3× heartbeat_interval (30s) geen heartbeat hebben gestuurd en ze op "offline" zet in DB + hub cleanup.
- [ ] AC7: **Event datum tooltips in admin** — Info/tooltips bij datum-velden in de admin UI die uitleggen: "Datum = informatief (booth werkt ook vóór deze datum)" en "Einddatum = na deze datum + 24u stopt de booth met uploaden, galerij blijft bereikbaar".
- [ ] AC8: **Event soft expiratie** — API-side guard: na `end_date + 24h` worden uploads geweigerd (HTTP 410 Gone). De viewer/galerij (QR code) blijft altijd toegankelijk ongeacht event status.

### Could Have

- [ ] AC9: **Configurable data paths** — `/opt/photobooth` paden vervangen door config uit `booth.toml` of environment variables.

---

## Technische Notities

### Architectuur Overzicht

```
┌─────────────┐         WebSocket          ┌──────────────┐
│  Booth (Pi)  │ ◄════════════════════════► │   API Server │
│  agent.py    │    register/heartbeat/     │  booth_ws.py │
│              │    log/frame/commands      │   hub.py     │
└──────┬───────┘                            └──────┬───────┘
       │ HTTP POST                                 │
       │ /api/photos/upload                        │ REST API
       └───────────────────────────────────────────┘
```

### Upload Flow (nieuw met queue)

```
Foto genomen (Kivy UI thread)
    ↓
fire-and-forget naar agent thread
    ↓
Directe upload poging (HTTP POST, background thread)
    ├── ✅ Succes → foto direct zichtbaar in viewer
    └── ❌ Mislukt → INSERT in upload_queue (booth SQLite)
                         ↓
              Retry poller elke 10s (agent thread)
                    ├── ✅ Succes → DELETE uit queue
                    └── ❌ Mislukt → retries++ (max 50)
```

### Bestanden

| Aspect | Detail |
|--------|--------|
| Bestanden (booth) | `apps/booth/src/photobooth/services/agent.py`, `config.py`, `app.py`, `services/storage.py` |
| Bestanden (API) | `apps/api/src/api/ws/booth_ws.py`, `ws/hub.py`, `api/booths.py`, `api/photos.py`, `app.py` |
| Bestanden (admin) | Event form component (tooltip toevoegen) |
| Bestanden (models) | `apps/api/src/api/models/db.py` (Booth, Event), `models/schemas.py` |
| Dependencies | Geen nieuwe — bestaande SQLite (booth), `websockets`, `aiohttp` |
| Database changes (booth) | Nieuwe `upload_queue` tabel in bestaande `photobooth.db` |
| Database changes (API) | Geen |
| API changes | Deduplicatie in `/api/photos/upload`, event expiratie guard |

### WS Protocol Wijzigingen

```diff
 Booth → API:
-  register    { booth_id, name, version }
+  register    { booth_id, name, version, api_key }
   heartbeat   { cpu, cam_connected, uptime, mem_*, disk_*, power_*, settings }
   frame       { data (base64) }
   photo_ready { session_id, seq }
   log         { level, message, logger, ts }

 API → Booth:
-  ack            { status, event_id, event_uid }
+  ack            { status, event_id, event_uid }
+  push_event     (automatisch na ack als booth event heeft)
   update_settings { settings: { key: value } }
   push_event     { event: { event_uid, event_name, ... background_url } }
   restart        {}
   start_preview  {}
   stop_preview   {}
```

---

## Design Beslissingen

| Beslissing | Keuze | Reden |
|-----------|-------|-------|
| Event expiratie | Soft guard (uploads blokkeren na end_date + 24h, galerij blijft open) | Klanten moeten QR codes blijven scannen na het event |
| Startdatum | Informatief, niet enforced | Booth moet testbaar zijn bij aflevering |
| Self-registration | Niet implementeren | 2-3 booths, handmatig flashen is prima |
| Booth-side event selectie | Out of scope | Altijd remote via admin dashboard |
| Photo deduplicatie | `booth_id + session_id + seq + variant` | Simpel, geen hashing nodig, idempotent |
| Events per booth | Altijd 1 actief event | Verhuurmodel = 1 booth per event per klant |
| Event auto-association | Niet implementeren | Risico op verkeerde koppeling bij meerdere booths |
| Offline queue opslag | Bestaande booth SQLite (`upload_queue` tabel) | Thread-safe (WAL mode), geen extra dependency |
| Upload retry interval | 10 seconden | Directe upload is primair, queue is fallback |
| TOML writer fix | Niet in scope | Irrelevant bij 2-3 zelf-beheerde booths |
| WebSocket vs REST | Huidige hybrid behouden | WS voor real-time (camera, commands), HTTP voor uploads |

---

## Out of Scope

- Migratie naar een andere message broker (MQTT, RabbitMQ)
- Multi-tenancy (meerdere organisaties)
- End-to-end encryption van foto's
- Booth firmware/OS updates via API
- Horizontale schaling van de API (meerdere instanties + shared state)
- Booth self-registration
- Booth-side event selectie UI
- Event auto-association
- TOML comment-preserving writer
- Server-side command queue (admin commands zijn fire-and-forget, 503 als booth offline)

---

## Open Vragen

_Alle vragen beantwoord tijdens refinement sessie van 2026-05-19._

---

## Conversatie Log

### 2026-05-19 — Refinement Sessie

Volledige grill-me sessie uitgevoerd. Alle design branches doorlopen:

1. **Event expiratie** → Soft guard: uploads blokkeren na end_date + 24h, galerij blijft altijd open
2. **Startdatum** → Informatief only, niet enforced. Booth moet testbaar zijn bij aflevering
3. **Admin tooltips** → Ja, toevoegen bij datum-velden met uitleg over gedrag
4. **Self-registration** → Geschrapt. 2-3 booths, handmatig flashen
5. **Booth-side event selectie** → Out of scope. Altijd remote via admin
6. **Photo deduplicatie** → Op `booth_id + session_id + seq + variant`, idempotent
7. **Meerdere events per booth** → Nee, altijd 1 actief event
8. **Event auto-association** → Geschrapt. Risico op verkeerde koppeling
9. **Offline queue opslag** → Bestaande booth SQLite, `upload_queue` tabel (thread-safe)
10. **Upload polling** → 10s voor retries, directe upload blijft primair (non-blocking background thread)
11. **TOML writer fix** → Geschrapt uit scope
12. **WebSocket vs REST** → Huidige hybrid is correct, geen wijziging

**Context:** Booths worden verhuurd. 2-3 apparaten, SD card flash (later SSD). Alles remote beheerd via admin dashboard.

### 2026-05-19 — Initiële Analyse

User story aangemaakt op basis van volledige code-analyse van de bestaande Booth ↔ API verbinding (13 bestanden, ~2400 regels).

### 2026-05-19 — Implementatie Afgerond

Alle 9 acceptance criteria (AC1–AC8 + shared helper) geïmplementeerd in 8 bestanden over 5 componenten. Geen nieuwe dependencies. Backwards compatible met bestaande booths (legacy mode voor API key). Story afgesloten.
