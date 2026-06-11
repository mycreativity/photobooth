---
description: Markeer een user story als afgerond en push de branch
---

User stories worden beheerd in `_backlog/`. Volg dit proces:

1. Verifieer dat alle acceptance criteria afgevinkt zijn
2. Hernoem het bestand naar `✅ STORY-XXX-naam.md`
3. Update het `Status:` veld naar `✅ Done`
4. Log de afronding in de "Conversatie Log" sectie van de story met datum
5. Presenteer een **walkthrough** van het gemaakte werk en testresultaten:
   - Wat er gebouwd is (per acceptance criterion)
   - Welke bestanden zijn aangemaakt of gewijzigd
   - Hoe te testen (golden path + edge cases)
   - Eventuele vervolgacties of bekende beperkingen
6. Push de feature branch: `git push origin story/XXX-naam`
7. Meld de branch naam aan de gebruiker zodat zij de PR kunnen aanmaken — **nooit direct naar main pushen**

### Regels

- Hernoem altijd het bestaande bestand — maak nooit een nieuw bestand aan en verwijder het oude
- Houd bestandsnaam-emoji en `Status:` veld altijd synchroon
- Bevestig dat alle taken afgevinkt zijn vóór je afrondt
