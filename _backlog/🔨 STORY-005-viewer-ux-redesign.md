# [STORY-005] Viewer App UX/VD Redesign

> **Status:** 🔨 In Progress
> **Priority:** 🟠 High
> **Component:** frontend
> **Estimate:** XL

---

## User Story

**Als** gast op een event,
**wil ik** via een QR-code op de booth mijn eigen foto's bekijken in een premium, fullscreen viewer en deze direct delen via mijn telefoon,
**zodat** ik een naadloze, privacy-vriendelijke ervaring heb van booth tot socials.

---

## Context & Motivatie

De huidige viewer app (`apps/viewer`) is functioneel maar visueel onafgewerkt: inline styles, emoji-iconen, generieke paarse kleuren die niet bij het LOOMO merk passen, geen componenten, geen design system, geen sharing-opties, en geen privacy (alle event-foto's zijn zichtbaar voor iedereen).

### Fundamentele architectuurwijziging

De viewer verandert van **event-based** naar **session-based**:

| Aspect | Huidig | Nieuw |
|---|---|---|
| URL-structuur | `/e/{event_uid}` — alle foto's | `/s/{session_token}` — alleen eigen foto's |
| Privacy | Alle gasten zien alles | AVG-proof: alleen eigen sessie |
| QR-code | Eén per event | Uniek per sessie (op booth na foto's) |
| Inhoud | Eindeloos grid | 1-6 foto's + print layout, fullscreen swipe |

### LOOMO Brand Palette (geextraheerd uit logo)

| Token | Kleur | Gebruik |
|---|---|---|
| `--brand-black` | `#0a0a0a` | Achtergrond |
| `--brand-white` | `#f5f0eb` | Tekst (warm wit, niet klinisch) |
| `--brand-wood` | `#c8956c` | Accenten, warmte, hover states |
| `--brand-wood-light` | `#d4a97a` | Subtiele highlights |
| `--brand-teal` | `#4dd9c0` | Tech-accent, interactieve elementen, CTA's |
| `--brand-teal-glow` | `rgba(77, 217, 192, 0.15)` | Glow effecten |
| `--party-warm` | `#ff9f6a` | Feestelijke warmte, confetti |
| `--party-rose` | `#e8607a` | Hartjes, love-theme accenten |

---

## Acceptance Criteria

### Design System & Componenten
- [ ] AC1: Design system met CSS custom properties (tokens voor kleur, spacing, typografie, radii, shadows)
- [ ] AC2: Component library met herbruikbare componenten
- [ ] AC3: Storybook setup (dev-tool) met alle componenten gedocumenteerd
- [ ] AC4: Lucide React icon set (geen emoji's in UI)
- [ ] AC5: Inter font met verfijnde weight/size schaal
- [ ] AC6: Dark mode only — warm zwart theme

### Schermen & User Flow
- [ ] AC7: Landing page (`/`) — "Scan de QR-code" + subtiel LOOMO logo
- [ ] AC8: Session viewer (`/s/{token}`) — fullscreen swipeable viewer (Optie B)
  - Print layout als eerste slide, daarna individuele foto's
  - Progress indicators bovenaan
  - Swipe/pijltjes navigatie
  - Glassmorphic action panel onderaan
- [ ] AC9: Empty state — "foto's worden verwerkt" (als sessie net is aangemaakt)
- [ ] AC10: Error states — 404 (ongeldige token), expired (>30 dagen)
- [ ] AC11: Confetti animatie bij eerste keer openen van sessie

### Sharing & Download
- [ ] AC12: Native Web Share API als primaire "Deel" knop (mobiel)
- [ ] AC13: Desktop fallback: Download + Kopieer link + Email
- [ ] AC14: Twee share-varianten: "Deel strip" (print layout, default) + "Deel foto" (individueel)
- [ ] AC15: Download in originele kwaliteit (zowel print als individueel)
- [ ] AC16: OG meta tags per sessie — event naam, print layout thumbnail, beschrijving

### Privacy & Toegang
- [ ] AC17: Session-based URLs met uniek token (niet raadbaar)
- [ ] AC18: Geen event-brede gallerij voor gasten (admin-only via dashboard)
- [ ] AC19: Event expiratie: 30 dagen na event datum → "verlopen" scherm
- [ ] AC20: Consent via fysiek bordje bij booth (geen digitale consent screen)

### Branding
- [ ] AC21: Event-first branding — event naam prominent, niet LOOMO
- [ ] AC22: Subtiele "Powered by LOOMO" footer met logo
- [ ] AC23: Geen watermark op foto's

### Technisch
- [ ] AC24: Framer Motion voor slide transitions, spring-physics swipen, confetti
- [ ] AC25: Responsive mobile-first (320px - 1440px)
- [ ] AC26: Lazy loading, blur placeholders voor foto's
- [ ] AC27: Server-side OG tag rendering per sessie page

---

## Technische Notities

### Schermen overzicht

```
1. Landing (/)
   └── "Scan de QR-code bij de photobooth"
   └── Subtiel LOOMO logo + "Powered by LOOMO"

2. Session Viewer (/s/{session_token})
   ├── [Slide 1] Print layout — fullscreen, "Deel" CTA
   ├── [Slide 2] Individuele foto 1
   ├── [Slide 3] Individuele foto 2
   ├── [Slide N] ...
   ├── Progress bar bovenin
   ├── Glassmorphic action panel (Deel / Download)
   └── Footer: "Powered by LOOMO"

3. Error/Expired (/s/{invalid_token})
   └── Stijlvol "niet gevonden" of "verlopen" scherm

4. Event Gallery (/e/{uid}) — ADMIN ONLY
   └── Alle foto's van het event (alleen via admin dashboard)
```

### Database wijzigingen

| Model | Wijziging |
|---|---|
| `Session` | Nieuw veld: `token` (VARCHAR 32, unique, indexed) — voor publieke sessie URLs |
| `Event` | Bestaand: `end_date` gebruiken voor 30-dagen expiratie check |

### API wijzigingen

| Endpoint | Beschrijving |
|---|---|
| `GET /api/public/sessions/{token}` | Sessie info + event naam (public) |
| `GET /api/public/sessions/{token}/photos` | Foto's van sessie incl. print variant (public) |

### Component library

| Component | Props | Beschrijving |
|---|---|---|
| `SessionViewer` | session, photos | Fullscreen swipeable container |
| `PhotoSlide` | photo, variant, actions | Enkele slide (foto of layout) |
| `ActionPanel` | onShare, onDownload, variant | Glassmorphic bottom panel |
| `ShareSheet` | photo, session | Native share + fallbacks |
| `ProgressBar` | current, total | Slide indicators |
| `EmptyState` | type | Wachten op foto's |
| `ErrorState` | code, message | Fout weergave |
| `Button` | variant, icon, children | Design system button |
| `Footer` | — | "Powered by LOOMO" |

### Dependencies

| Package | Doel |
|---|---|
| `framer-motion` | Slide transitions, spring swipen, confetti |
| `lucide-react` | Professionele icon set |
| `@storybook/react` | Component documentatie (dev) |

---

## Out of Scope

- Admin dashboard redesign (aparte story)
- Booth app UI (aparte stack)
- Video support
- Per-event theming (V2 feature)
- PIN-beveiliging per event (V2 feature)
- Digitale consent screen (fysiek bordje is voldoende)
- Realtime WebSocket push (huidige polling is OK)
- Multi-taal (i18n)
- Analytics/tracking
- Light mode

---

## Open Vragen

Geen — alle vragen beantwoord in refinement sessie.

---

## Conversatie Log

_Notities uit de refinement sessie._

- 2026-05-20: Story aangemaakt. Gebruiker wil complete UX/VD redesign van viewer app.
- 2026-05-20: Refinement sessie afgerond. Beslissingen:
  - Branding: event-first, LOOMO subtiel in footer ("Powered by LOOMO")
  - Sharing: print layout + individuele foto's, print als default
  - Privacy: session-based viewer (AVG-proof), geen event-brede gallerij voor gasten
  - Consent: fysiek bordje bij booth, geen digitale consent screen. Verwerkersovereenkomst in huurcontract.
  - Deelkanalen: native share API (mobiel), download + kopieer link + email (desktop)
  - Layout: Optie B (fullscreen swipeable), print layout als eerste slide
  - Theme: dark mode only, één universeel warm theme
  - Per-event theming: niet nu (V2)
  - Animaties: Framer Motion (smooth transitions + confetti bij eerste view)
  - Storybook: dev-tool only
  - Expiratie: 30 dagen na event datum
  - OG tags: event naam + print layout thumbnail per sessie
