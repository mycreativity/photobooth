# [STORY-006] Admin Event Detail — Mobile UX Verbetering

> **Status:** 🔨 In Progress
> **Priority:** 🟠 High
> **Component:** frontend
> **Estimate:** M

---

## User Story

**Als** admin die events beheert op mijn telefoon,
**wil ik** dat de event detail pagina goed bruikbaar is op mobile en desktop,
**zodat** ik snel instellingen kan wijzigen, de fotokaart kan configureren, en QR-codes kan delen zonder dat content wordt afgesneden.

---

## Context & Motivatie

De huidige event detail pagina (`/events/[uid]`) heeft meerdere mobile UX problemen die het dagelijks beheer hinderen. De pagina bevat 3 tabs (Algemeen, Fotokaart, QR & Delen) die elk layout-issues hebben op viewports < 430px.

### Geïdentificeerde problemen (uit screenshots)

**Tab: Fotokaart**
- Achtergrond-thumbnails zijn onherkenbaar klein op mobile (~ 24px)
- "Achtergrond afbeelding" en "Preview" staan naast elkaar — te krap
- De fotokaart preview is afgesneden rechtsonder
- Markdown help-tekst onder "Tekst" veld is nauwelijks leesbaar
- Layout toggle (Portret/Collage) staat verloren in de ruimte

**Tab: QR & Delen**
- QR code en info staan horizontaal naast elkaar → tekst wordt afgesneden ("Publieke gale...", "https://b...", "Open galu...")
- Moet op mobile verticaal stacken: QR boven, info eronder
- "Kopieer" knoppen vallen buiten het scherm

**Tab: Algemeen**
- Datum-inputs gebruiken browser-native format → UX is acceptabel maar kan netter
- Verwijderen/Opslaan knoppen staan direct onder de header — verwarrend op mobile
- Toggle "Event is actief" is OK

**Visuele inconsistenties (cross-tab)**
- **Achtergrondkleur verschilt per tab**: Fotokaart tab heeft een cyaan/teal-getinte achtergrond over de hele pagina, terwijl Algemeen en QR tabs een correcte witte achtergrond tonen. Vermoedelijk lekt de fotokaart preview-achtergrond uit, of er zit een overgebleven CSS-klasse die de body kleurt.
- **Mobile header ontbreekt op Fotokaart tab**: Screenshots 2+3 tonen correct de hamburger + LOOMO logo header, maar screenshot 1 (Fotokaart) toont alleen een back-arrow + titel zonder de standaard AppShell mobile header. Mogelijk rendering-issue of scroll-positie die de sticky header verdringt.
- **Tab labels inconsistent**: "QR & Delen" wramt over 2 regels op mobile (screenshot 2), terwijl "Fotokaart" en "Algemeen" op één regel passen. De tab breedte is niet gelijkmatig verdeeld.
- **Actieknoppen**: "Verwijderen" (rood, ghost) en "Opslaan" (teal, filled) staan op alle tabs identiek gepositioneerd — dat is goed. Maar de positie direct onder de page header voelt misplaatst; ze horen bij het formulier, niet bij de navigatie.
- **Preview card kleur**: De fotokaart preview gebruikt een hardcoded cyaan/teal kleur (`#4dd9c0`-achtig) als placeholder, wat visueel domineert en de hele tab "blauw" doet aanvoelen. Moet een neutrale placeholder zijn (light gray) met alleen de daadwerkelijke preview-content.


---

## Acceptance Criteria

- [ ] AC1: Fotokaart tab — achtergrond thumbnails zijn minimaal 48px met duidelijke selectie-indicator
- [ ] AC2: Fotokaart tab — op mobile (< 640px) stackt de layout verticaal: preview boven, instellingen eronder
- [ ] AC3: Fotokaart tab — fotokaart preview past volledig in viewport zonder horizontale scroll
- [ ] AC4: QR & Delen tab — op mobile stackt QR + info verticaal: QR code boven, links/knoppen eronder
- [ ] AC5: QR & Delen tab — alle tekst en knoppen zijn volledig zichtbaar zonder afkapping
- [ ] AC6: Tabs — icon + kort label (⚙️ Info, 🎨 Kaart, 📱 QR) passen op één regel op 375px
- [ ] AC7: Actieknoppen — sticky footer op mobile (Opslaan primair, Verwijderen in overflow menu), header-only op desktop
- [ ] AC12: De 898-regel page.tsx is gesplitst in `GeneralTab.tsx`, `PhotoCardTab.tsx`, `SharingTab.tsx` + een dunne parent shell
- [ ] AC8: Desktop layout blijft minimaal even goed als nu — geen regressie
- [ ] AC9: Achtergrondkleur is consistent wit/lichtgrijs op alle tabs — geen teal bleed-through
- [ ] AC10: Mobile header (hamburger + LOOMO logo) is zichtbaar op alle tabs, inclusief Fotokaart
- [ ] AC11: Fotokaart preview placeholder gebruikt een neutrale kleur (grijs), niet teal

---

## Technische Notities

| Aspect | Detail |
|--------|--------|
| Bestanden | `apps/admin/src/app/events/[uid]/page.tsx` (898 regels) |
| Dependencies | Geen nieuwe — puur CSS/layout refactor |
| Database changes | Geen |
| API changes | Geen |

### Aanpak

1. **Split page.tsx** → `GeneralTab.tsx`, `PhotoCardTab.tsx`, `SharingTab.tsx` + parent shell met tabs/state
2. **Tabs**: Lucide icons (Settings, Palette, QrCode) + korte labels (Info, Kaart, QR)
3. **Sticky footer (mobile)**: `fixed bottom-0` met Opslaan als primaire CTA, Verwijderen in overflow (⋯) menu
4. **Responsive stacking**: `flex-col` op mobile, `flex-row` op desktop voor Fotokaart en QR tabs
5. **Teal bleed fix**: verwijder achtergrondkleur-overrides op Fotokaart tab, gebruik neutrale gray placeholder
6. **Mobile header fix**: verifieer AppShell rendering op alle tabs

---

## Out of Scope

- Nieuwe features toevoegen aan de event detail pagina
- Wijzigingen aan andere pagina's (dashboard, events lijst, booth detail)
- API wijzigingen
- Fotokaart render-logica aanpassen

---

## Open Vragen

_Alle vragen beantwoord in refinement sessie._

---

## Conversatie Log

- 2026-05-23: Story aangemaakt op basis van mobile screenshots. Drie tabs geanalyseerd, problemen + visuele inconsistenties gedocumenteerd.
- 2026-05-23: Refinement sessie — beslissingen:
  - Actieknoppen: sticky footer op mobile, header op desktop
  - Tabs: icon (Lucide) + kort label (Info, Kaart, QR)
  - Page splitsen: ja, drie tab-componenten + parent shell
