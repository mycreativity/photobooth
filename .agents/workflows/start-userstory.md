---
description: Begin met het implementeren van een user story
---

User stories worden beheerd in `_backlog/`. Volg altijd dit proces wanneer je als Antigravity agent werkt.

### Instructies voor het Antigravity Planning Mode proces

1. Lees de specifieke story uit `_backlog/`
2. Verifieer dat alle open vragen beantwoord zijn
3. Hernoem het user story bestand met de `run_command` tool (`mv` commando) naar: `🔨 STORY-XXX-naam.md`
4. Update het `Status:` veld in het bestand naar `🔨 In Progress`
5. Schakel over naar Planning Mode: Maak een `implementation_plan.md` artifact aan (gebruik `write_to_file` met `IsArtifact: true`, `ArtifactType: 'implementation_plan'` en `RequestFeedback: true`).
6. Wacht op goedkeuring van de gebruiker op het plan.
7. Na goedkeuring: maak een feature branch aan met `git checkout -b story/XXX-korte-naam`. Alle commits gaan op deze branch — **nooit op main** (zie `.agents/rules/git-workflow.md`).
8. Maak een `task.md` artifact aan met de acceptance criteria en taken uit de story.
9. Begin met bouwen en werk de `task.md` continu bij (markeer met `[/]` en `[x]`).

### Regels voor Antigravity

- **Altijd** bestanden hernoemen met de `run_command` tool (`mv` commando).
- Gebruik de Antigravity artifacts (`implementation_plan.md` en `task.md`) strikt zoals hierboven omschreven.
