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

1. Verifieer dat alle acceptance criteria zijn afgevinkt in je `task.md`
2. Hernoem het user story bestand met de `run_command` tool (`mv` commando) naar: `✅ STORY-XXX-naam.md`
3. Update het `Status:` veld in het bestand naar `✅ Done`
4. Log de afronding in de "Conversatie Log" van de story
5. Maak een `walkthrough.md` artifact aan (gebruik `write_to_file` of `replace_file_content` met `IsArtifact: true` en `ArtifactType: 'walkthrough'`) om je gemaakte werk en testresultaten te presenteren aan de gebruiker.
6. Push de feature branch: `git push origin story/XXX-naam`. Meld de branch naam aan de gebruiker zodat zij de PR kunnen aanmaken. **Nooit** direct naar `main` pushen (zie `.agents/rules/git-workflow.md`).

- Hernoem altijd het bestaande bestand — maak nooit een nieuw bestand aan en verwijder het oude
- Houd bestandsnaam-emoji en `Status:` veld altijd synchroon
- Bevestig dat alle taken afgevinkt zijn vóór je afrondt
