# Rule: No Spontaneous Implementation

## Beantwoord eerst, implementeer later

Start NOOIT spontaan met implementatie buiten een actieve user story om.

### Wat valt hieronder

- Packages installeren (`brew install`, `npm install`, `pip install`)
- Code wijzigen of bestanden aanmaken
- Git commits, pushes, deploys
- Docker builds, server configuratie

### Correct gedrag

1. **Gebruiker stelt een vraag** → beantwoord de vraag. Punt.
2. **Gebruiker wil iets gebouwd** → maak een user story aan via `/create-userstory`, of verwijs naar een bestaande.
3. **Binnen een actieve story** → dan mag je bouwen, maar alleen op een feature branch.

### Waarom

De gebruiker verwacht controle over wat er wanneer verandert. Een vraag is geen opdracht. Implementatie zonder expliciet verzoek is ongewenst — zelfs als het "maar een klein dingetje" is.
