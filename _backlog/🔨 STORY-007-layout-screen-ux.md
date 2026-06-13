# [STORY-007] Layout screen UX verbetering

> **Status:** 🔨 In Progress
> **Priority:** 🟠 High
> **Component:** booth (Kivy UI)
> **Estimate:** M

---

## User Story

**Als** event-gast die voor het eerst een photobooth gebruikt,
**wil ik** op het layout-keuze scherm direct begrijpen wat ik ga meemaken en wat ik krijg,
**zodat** ik snel en zeker een keuze maak zonder te aarzelen of per ongeluk vast te zitten.

---

## Context & Motivatie

Elicitation-sessie op de live LayoutScreen (screenshot 2026-06-11) bracht vijf concrete UX-gaps boven water:

1. **Geen eindresultaat-preview** — de iconen tonen een schematische compositie, niet hoe de echte print eruit ziet (inclusief branding bar, schaal, achtergrond).
2. **Geen sessieduur-hint** — gasten zien niet dat "Collage (3)" drie flits-momenten betekent en "Enkele foto" er één. Dat verschil stuurt de keuze sterk.
3. **Geen terugknop** — wie per ongeluk een layout kiest zit vast tot de sessie afgerond of handmatig gereset is.
4. **Geen filter-hint** — gasten die weten dat photobooths filters hebben zoeken die hier al; zonder hint denken ze dat het er niet inzit.
5. **Fotogrid verwijderen** — de grid-layout (6 foto's, label zei "(4)") voegt complexiteit toe zonder meerwaarde voor events. Alleen Enkele foto en Collage (3×) bewaren.

---

## Acceptance Criteria

- [ ] AC1: De Fotogrid-optie is verwijderd uit `LayoutScreen`; alleen "Enkele foto" en "Collage (3)" worden getoond.
- [ ] AC2: Elke layout-kaart toont als subtekst onder de naam het aantal foto-momenten via i18n, bijv. `layout.single_hint` = "1 foto" en `layout.strip_hint` = "3 foto's".
- [ ] AC3: Elke layout-kaart toont een print-preview gegenereerd vanuit de slot-percentages in `card_layout.json`, inclusief een donkere branding-balk onderaan op de juiste verhouding.
- [ ] AC4: Een statische subtekst of chip onderaan elke kaart toont "Daarna kies je een filter →" (altijd zichtbaar — filters zijn niet event-afhankelijk).
- [ ] AC5: Een terugknop is altijd zichtbaar (linksonder), navigeert terug naar het idle/start-scherm en stopt de camera preview correct via `on_leave`.
- [ ] AC6: `LAYOUT_GRID`, `_draw_grid_icon`, de grid-entry in `LAYOUT_PHOTO_COUNT` en de grid-slots in `print_layouts.py` zijn verwijderd; geen resterende referenties in screens, print service, agent of API.

---

## Technische Notities

| Aspect | Detail |
|--------|--------|
| Bestanden | `apps/booth/src/photobooth/ui/screens.py` — `LayoutScreen` (r. 1309), `_draw_grid_icon` (r. 807), `LAYOUT_GRID` constante |
| Bestanden | `apps/booth/src/photobooth/services/print_layouts.py` — grid slot-definitie (r. 85-96) |
| Print preview | Canvas-drawing per layout op basis van slot `x/y/w/h`-percentages uit `card_layout.json`; branding-balk als gekleurd rechthoek onderaan op `branding.heightPercent`-hoogte |
| Terugknop | `navigate_to(SCREEN_IDLE)`; camera preview stoppen via `on_leave` of `preview_layer.stop_camera_preview()` |
| Sessieduur-hint | Subtekst in `TouchCard` via `t("layout.single_hint")` / `t("layout.strip_hint")`; keys toevoegen aan `seed_translations.py` |
| Filter-hint | Statische i18n-tekst onder de kaarten, bijv. `t("layout.filter_hint")`; geen logica |
| Fotogrid | Nooit actief ingezet — verwijdering zonder migratie of event-communicatie |

---

## Out of Scope

- Herontwerp van de `FilterScreen`
- Dynamische preview op basis van het gekozen event-thema of achtergrondafbeelding
- Toevoegen van nieuwe layouts

---

## Open Vragen

Alle vragen beantwoord tijdens refinement (2026-06-11).

---

## Conversatie Log

- 2026-06-11: Gevonden via elicitation-sessie (`/elicitation`) op live screenshot van de Pi (192.168.0.109). Methodes: User Lens + Completeness Check.
- 2026-06-11: Bug gesignaleerd: `Fotogrid (4)` label klopte niet met 6 slots in config → besluit: layout volledig verwijderen.
- 2026-06-11: Refinement beslissingen:
  - Terugknop: altijd zichtbaar, linksonder.
  - Print-preview: rendert vanuit `card_layout.json` slot-percentages (niet hardcoded Canvas).
  - Fotogrid: nooit actief ingezet, geen migratie nodig.
  - Filter-hint: altijd zichtbaar — filters zijn niet event-afhankelijk, `FilterScreen._all_filters` is hardcoded.
  - Sessieduur-hint: subtekst onder kaartnaam via i18n.
