# Certiflow — Project Rules

> Rules are also stored in `.agents/rules/` for Antigravity compatibility.

---

## Rule: API Proxy Architecture

All API communication MUST be proxied through Next.js. The browser never talks to the API directly.

1. **No direct API URLs in client code** — never use `NEXT_PUBLIC_API_URL` or hardcode the API domain.
2. **Use rewrites or route handlers** — proxy `/api/:path*` to the internal API via `next.config.ts` rewrites, or a route handler when the URL is runtime-only.
3. **No tokens in the browser** — JWTs and API keys must never be exposed client-side.

```tsx
// ✅ Client component — relative URL, proxied by Next.js
<img src="/api/public/photos/abc123" />

// ✅ Server component — direct internal call is fine
const res = await fetch(`${process.env.API_URL}/api/sessions/${token}`);

// ❌ Never expose API domain to browser
<img src={`${process.env.NEXT_PUBLIC_API_URL}/api/photos/abc`} />
fetch("https://api.example.com", { headers: { Authorization: `Bearer ${token}` } });
```

---

## Rule: i18n — All Text via Translation System

All user-facing text MUST go through the i18n system. No hardcoded strings in components, API responses, or templates.

**Frontend (Next.js):**
- Always use `t("key")` — import `useTranslation` from `@/lib/i18n`
- Dynamic values: `t("common.welcome", { name: "Jasper" })`
- No inline strings, even short labels like "Save" or "Cancel"
- Add both `nl` and `en` translations for every new key in `apps/backend/scripts/seed_translations.py`
- Module-level constants with labels (e.g. `ROLE_LABELS`, `ACTION_LABELS`, `STATUS_MAP`) must be defined **inside** the component body so `t()` is in scope
- After adding new translations, re-seed the database: `docker compose exec backend python scripts/seed_translations.py`

**Client components:** use `const { t } = useTranslation();` — never raw strings in JSX.

**Server components:** use `await getTranslations(locale)` — never raw strings in JSX.

**Key convention:** `{namespace}.{section}.{identifier}`

| Namespace | Use |
|-----------|-----|
| `common` | Shared UI elements (buttons, labels, statuses, pagination, roles) |
| `nav` | Navigation items and section headers |
| `auth` | Login, OTP, session-related |
| `logbook` | Logbook actions and labels |
| `dashboard` | Dashboard titles and stats |
| `installations` | Installation management |
| `cylinders` | Cylinder management |
| `users` | User management |
| `admin` | Admin tool specific text |
| `compliance` | Compliance flags and reports |
| `sessions` | Session management |
| `reports` | Reporting pages |
| `email` | Email templates |

**Checklist before committing a component:**
1. Zero raw Dutch/English strings in JSX — every visible label goes through `t()`
2. Both `nl` and `en` values added to `seed_translations.py` for every new key
3. Seed script re-run so the keys exist in the database

**Backend:** API error messages may still be hardcoded in Dutch for now (backend i18n is out of scope).

Relevant files: `apps/web/src/lib/i18n.tsx`, `apps/backend/api/translations.py`, `apps/backend/scripts/seed_translations.py`

---

## Rule: No Spontaneous Implementation

Never start implementing outside an active user story.

- A question is not an implementation request — answer it and stop.
- Use `/create-userstory` to create a story, or reference an existing one.
- Implementation only happens on an active story, on a feature branch — never on `main`.
- This covers: installing packages, modifying files, git commits, docker builds, server config.

---

## Backlog & User Story Workflow

User stories live in `_backlog/`. Status is tracked by both the emoji prefix in the filename and the `Status:` field inside the file — keep them in sync.

| Prefix | Status | Meaning |
|--------|--------|---------|
| 🆕 | Draft | New, not yet refined |
| 📋 | Refined | Ready for implementation |
| 🔨 | In Progress | Currently being built |
| ✅ | Done | Implemented |

**Custom slash commands:**

| Command | Purpose |
|---------|---------|
| `/create-userstory` | Create a new user story |
| `/refine-userstory` | Discuss and refine a story |
| `/start-userstory` | Begin implementation |
| `/done-userstory` | Mark a story complete |
| `/grill-me` | Stress-test a plan or design |
| `/optimize` | Audit and improve the agent setup |
