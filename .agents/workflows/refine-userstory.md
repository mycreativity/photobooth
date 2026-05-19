---
description: Spar over een bestaande user story
---

User stories worden beheerd in `_backlog/`. Volg altijd dit proces wanneer je als Antigravity agent werkt.

### Instructies

1. Lees de specifieke story uit `_backlog/` (vraag de gebruiker welke story als dit niet duidelijk is)
2. Bespreek open vragen, acceptance criteria en technische keuzes. Pas hierbij actief de "grill-me" skill toe (zie `.agents/skills/grill-me.md`) om de gebruiker stevig te bevragen over het plan tot er een volledig en gedeeld begrip is.
3. Werk het bestand bij met de uitkomsten (gebruik bv. `replace_file_content`)
4. Log de beslissingen in de "Conversatie Log" sectie van de story met datum
5. Als de story klaar is voor implementatie, hernoem het bestand met de `run_command` tool (`mv` commando) naar `📋 STORY-XXX-naam.md` (zorg dat de extensie `.md` blijft)
6. Update het `Status:` veld in het bestand naar `📋 Refined`
7. Vraag of we kunnen starten.

### Regels voor Antigravity

- Bij sparren: stel gerichte vragen, geef opties met voor/nadelen, laat de gebruiker beslissen
- **Altijd** bestanden hernoemen met de `run_command` tool (`mv` commando) in plaats van nieuwe bestanden aan te maken en oude te verwijderen.
- **Altijd** zowel het `Status:` veld ALS het emoji-prefix in de bestandsnaam synchroon houden.
