# Immigration97 Codex Budget Rules

Ce projet doit etre travaille en mode economie stricte de credits OpenAI.

## Regles obligatoires

- Ne jamais lancer d'appel reel a OpenAI sans validation explicite de l'utilisateur.
- Avant toute commande pouvant consommer l'API OpenAI, afficher la commande, le modele probable, le nombre d'appels estime, puis attendre validation.
- Utiliser `LLM_MOCK_MODE=1` par defaut pour les generations IA pendant le developpement.
- Ne pas lancer les commandes `generate_*`, `seed_*`, `import_*`, `outreach` ou les coachs IA si elles peuvent appeler OpenAI, sauf accord explicite.
- Eviter les analyses globales du repo. Lire seulement les fichiers necessaires a la demande.
- Ne pas afficher de gros outputs, gros diffs ou contenus complets de fichiers. Resumer et citer les fichiers utiles.
- Ne pas utiliser de recherche web sauf demande explicite ou obligation de verification.
- Preferer les tests sans API: `py_compile`, `manage.py check`, tests unitaires mockes, dry-run avec `LLM_MOCK_MODE=1`.
- Pour les generations reelles, proposer un micro-lot: 1 niveau, 1 skill, 1 ou 2 lecons, max 2 exercices, puis attendre validation.

## Commandes safe typiques

```powershell
$env:LLM_MOCK_MODE="1"
.\immigration97_env\Scripts\python.exe manage.py check
```

```powershell
$env:LLM_MOCK_MODE="1"
.\immigration97_env\Scripts\python.exe manage.py generate_german_content --level A1 --skill GRAMMATIK --lessons 1 --exercises 2 --continue-on-error
```

## Reponse attendue de Codex

Repondre court. Si une action risque de couter des credits, demander confirmation avant d'agir.
