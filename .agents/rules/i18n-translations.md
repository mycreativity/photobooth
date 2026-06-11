# Rule: i18n — Alle teksten via het vertaalsysteem

## Nooit hardcoded teksten in code

Alle user-facing teksten MOETEN via het vertaalsysteem (i18n) gaan. Geen hardcoded strings in componenten, API responses, of templates.

### Frontend (Next.js)

1. **Gebruik altijd `t("key")`** — Importeer `useTranslation` uit `@/lib/i18n` en gebruik `t()` voor alle zichtbare teksten.
2. **Dynamische waarden** via `{variable}` placeholders: `t("common.welcome", { name: "Jasper" })`.
3. **Markdown-teksten** met `react-markdown`: `<ReactMarkdown>{t("help.intro")}</ReactMarkdown>`.
4. **Geen inline strings** — Zelfs korte labels zoals "Opslaan" of "Annuleren" komen uit het vertaalsysteem.

```tsx
// ✅ Correct
const { t } = useTranslation();
<button>{t("common.buttons.save")}</button>

// ❌ Fout
<button>Opslaan</button>
```

### Backend (FastAPI)

1. **API error messages** mogen voorlopig nog hardcoded in het Nederlands zijn (backend i18n is out of scope voor nu).
2. **E-mail templates** en andere user-facing content moeten wél via het vertaalsysteem als dat haalbaar is.

### Key conventie

Gebruik dotted namespace keys: `{namespace}.{section}.{identifier}`

| Namespace | Gebruik |
|-----------|---------|
| `common` | Gedeelde UI-elementen (buttons, labels, statussen) |
| `nav` | Navigatie-items |
| `auth` | Login, OTP, sessie-gerelateerd |
| `logbook` | Logboek acties en labels |
| `dashboard` | Dashboard titels en statistieken |
| `installations` | Installatiebeheer |
| `cylinders` | Cilinderbeheer |
| `users` | Gebruikersbeheer |
| `admin` | Admin-tool specifieke teksten |
| `compliance` | Compliance flags en rapportages |
| `email` | E-mail templates |

### Nieuwe teksten toevoegen

Bij het schrijven van nieuwe code met user-facing teksten:

1. **Definieer de key** volgens de conventie hierboven
2. **Voeg de vertaling toe** aan de database via de Admin UI of het seed script (`apps/backend/scripts/seed_translations.py`)
3. **Gebruik `t("key")`** in de component
4. **Voeg BEIDE talen toe** — Nederlands (nl) én Engels (en)

### Relevante bestanden

- Frontend i18n provider: `apps/web/src/lib/i18n.tsx`
- Translations API: `apps/backend/api/translations.py`
- Admin CRUD: `apps/backend/api/admin_translations.py`
- Translation model: `apps/backend/models/models.py` → `Translation`
- Seed script: `apps/backend/scripts/seed_translations.py`
- Config: `DEFAULT_LOCALE=nl`, `SUPPORTED_LOCALES=nl,en` in `.env`
