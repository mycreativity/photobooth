# [STORY-003] Migratie SQLite → PostgreSQL

> **Status:** 🆕 Draft
> **Priority:** 🟠 High
> **Component:** backend
> **Estimate:** M

---

## User Story

**Als** ontwikkelaar,
**wil ik** de API overzetten van SQLite naar de bestaande PostgreSQL 16 server,
**zodat** de database schaalbaarder is, concurrent access ondersteunt, en er één centraal databaseplatform is.

---

## Context & Motivatie

De API (`apps/api`) gebruikt momenteel SQLite via `aiosqlite` als async driver. De database staat als bestand in een bind mount (`./data/photobooth.db`). De gebruiker heeft al een PostgreSQL 16 server draaien en wil die hergebruiken.

### Huidige setup

| Aspect       | Waarde                                                                          |
| ------------ | ------------------------------------------------------------------------------- |
| Engine       | SQLite                                                                          |
| Driver       | `aiosqlite`                                                                     |
| DATABASE_URL | `sqlite+aiosqlite:////data/photobooth.db`                                       |
| Modellen     | 7 tabellen (users, otp_codes, refresh_tokens, events, booths, sessions, photos) |
| ORM          | SQLAlchemy 2.0+ (async)                                                         |
| Auto-create  | `Base.metadata.create_all()` in `app.py` lifespan                               |

### Beperkingen van SQLite

- Geen concurrent writes (enkel write lock)
- Geen native enum/array types
- Geen connection pooling
- Moeilijker te backuppen bij actief gebruik

### Doel

```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/photobooth
```

---

## Acceptance Criteria

- [ ] AC1: `aiosqlite` dependency vervangen door `asyncpg`
- [ ] AC2: `DATABASE_URL` in docker-compose, .env, .env.example bijgewerkt naar PostgreSQL
- [ ] AC3: `config.py` default `database_url` bijgewerkt
- [ ] AC4: Modellen gecontroleerd op SQLite-specifieke constructies
- [ ] AC5: Bestaande data gemigreerd van SQLite naar PostgreSQL (indien nodig)
- [ ] AC6: App start correct met PostgreSQL backend
- [ ] AC7: CRUD operaties werken (events, photos, booths, auth)

---

## Technische Notities

| Aspect           | Detail                                                                                                                                |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Bestanden        | `apps/api/pyproject.toml`, `apps/api/src/api/config.py`, `apps/api/src/api/database.py`, `docker-compose.yml`, `.env`, `.env.example` |
| Dependencies     | `aiosqlite` → `asyncpg`                                                                                                               |
| Database changes | Nieuw PostgreSQL schema (auto-created door SQLAlchemy)                                                                                |
| API changes      | Geen                                                                                                                                  |

### Wat moet wijzigen

1. **`pyproject.toml`**: `aiosqlite` verwijderen, `asyncpg` toevoegen
2. **`config.py`**: Default `database_url` → PostgreSQL connection string
3. **`database.py`**: Mogelijk pool settings toevoegen (`pool_size`, `max_overflow`)
4. **`docker-compose.yml`**: `DATABASE_URL` env var updaten
5. **`.env` / `.env.example`**: PostgreSQL credentials
6. **Modellen**: Check op `func.now()` (werkt in PG), `String` PKs (werkt), geen SQLite-specifics gevonden

### Bestaande PG16 server

De gebruiker heeft al een PostgreSQL 16 server draaien. Details nodig:
- Host / poort
- Database naam (nieuw aanmaken: `photobooth`?)
- Credentials

---

## Out of Scope

- Alembic migraties opzetten (kan als aparte story)
- Backup strategie
- Connection pooling via PgBouncer
- Migratie van bestaande productiedata (nog geen productiedata)

---

## Open Vragen

- [ ] Wat is het adres van de PG16 server? (host, port)
- [ ] Welke database naam? Voorstel: `photobooth`
- [ ] Welke credentials gebruiken? Bestaande user of nieuwe aanmaken?
- [ ] Is er bestaande data in SQLite die gemigreerd moet worden, of is het een verse start?

---

## Conversatie Log

_Notities uit de refinement sessie._

- 2026-05-19: Story aangemaakt als follow-up van STORY-001 (app restructure). Gebruiker gaf aan een bestaande PG16 server te hebben.
