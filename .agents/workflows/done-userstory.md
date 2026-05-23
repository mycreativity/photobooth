---
description: Markeer een user story als afgerond
---

User stories worden beheerd in `_backlog/`. Volg altijd dit proces wanneer je als Antigravity agent werkt.

### Instructies

1. Verifieer dat alle acceptance criteria zijn afgevinkt in je `task.md`
2. Hernoem het user story bestand met de `run_command` tool (`mv` commando) naar: `✅ STORY-XXX-naam.md`
3. Update het `Status:` veld in het bestand naar `✅ Done`
4. Log de afronding in de "Conversatie Log" van de story
5. Maak een `walkthrough.md` artifact aan (gebruik `write_to_file` of `replace_file_content` met `IsArtifact: true` en `ArtifactType: 'walkthrough'`) om je gemaakte werk en testresultaten te presenteren aan de gebruiker.
6. Push de feature branch: `git push origin story/XXX-naam`. Meld de branch naam aan de gebruiker zodat zij de PR kunnen aanmaken. **Nooit** direct naar `main` pushen (zie `.agents/rules/git-workflow.md`).

### Regels voor Antigravity

- **Altijd** bestanden hernoemen met de `run_command` tool (`mv` commando).
- **Altijd** zowel het `Status:` veld ALS het emoji-prefix in de bestandsnaam synchroon houden.
- Gebruik het Antigravity artifact `walkthrough.md` strikt zoals hierboven omschreven.
