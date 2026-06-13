---
description: Begin met het implementeren van een user story
---

User stories worden beheerd in `_backlog/`. Volg dit proces:

1. Lees de specifieke story (vraag de gebruiker welke als dit niet duidelijk is)
2. Verifieer dat alle open vragen beantwoord zijn; stop en bespreek als dat niet zo is
3. Hernoem het bestand naar `🔨 STORY-XXX-naam.md`
4. Update het `Status:` veld naar `🔨 In Progress`
5. **Stel een implementatieplan op** en wacht op expliciete goedkeuring van de gebruiker vóór je verder gaat. Het plan bevat:
   - Overzicht van aanpak en architectuurkeuzes
   - Lijst van te wijzigen/aan te maken bestanden
   - Volgorde van implementatie
   - Risico's en aandachtspunten
6. Maak een feature branch aan: `git checkout -b story/XXX-korte-naam` — **nooit op main**
7. Houd een takenlijst bij met de acceptance criteria en taken uit de story; markeer taken als voltooid zodra ze klaar zijn
8. Begin met bouwen en houd de takenlijst continu bij

1. Lees de specifieke story uit `_backlog/`
2. Verifieer dat alle open vragen beantwoord zijn
3. Hernoem het user story bestand met de `run_command` tool (`mv` commando) naar: `🔨 STORY-XXX-naam.md`
4. Update het `Status:` veld in het bestand naar `🔨 In Progress`
5. Schakel over naar Planning Mode: Maak een `implementation_plan.md` artifact aan (gebruik `write_to_file` met `IsArtifact: true`, `ArtifactType: 'implementation_plan'` en `RequestFeedback: true`).
6. Wacht op goedkeuring van de gebruiker op het plan.
7. Na goedkeuring: maak een feature branch aan met `git checkout -b story/XXX-korte-naam`. Alle commits gaan op deze branch — **nooit op main** (zie `.agents/rules/git-workflow.md`).
8. Maak een `task.md` artifact aan met de acceptance criteria en taken uit de story.
9. Begin met bouwen en werk de `task.md` continu bij (markeer met `[/]` en `[x]`).

- Hernoem altijd het bestaande bestand — maak nooit een nieuw bestand aan en verwijder het oude
- Houd bestandsnaam-emoji en `Status:` veld altijd synchroon
- Alle commits gaan op de feature branch — nooit op main
- Implementeer alleen wat in de acceptance criteria staat
