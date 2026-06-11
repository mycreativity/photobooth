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

### Regels

- Hernoem altijd het bestaande bestand — maak nooit een nieuw bestand aan en verwijder het oude
- Houd bestandsnaam-emoji en `Status:` veld altijd synchroon
- Alle commits gaan op de feature branch — nooit op main
- Implementeer alleen wat in de acceptance criteria staat
