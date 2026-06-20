# Arsenal IA Immigration97

## Audit rapide

Immigration97 possede deja plusieurs briques IA utiles:

- `ai_engine`: generation de contenus pedagogiques CO, CE, EE, EO et service LLM avec mode mock.
- `preparation_tests`: coach de progression TEF/TCF base sur regles.
- `job_agent`: agent candidature, score ATS gratuit, CV adapte, lettre, email et mots-cles manquants.
- `outreach`: prospection employeurs, verification d'opportunites et detection anti-arnaque.
- `permanent_residence`: diagnostic residence permanente et assistant RP.
- `resources`: guides, checklists et documents telechargeables.

Le probleme principal n'etait pas l'absence d'agents, mais l'absence d'un point central pour choisir le bon agent selon l'objectif utilisateur.

## Architecture cible

L'orchestrateur Immigration97 est la couche centrale qui:

1. comprend l'objectif utilisateur;
2. lit le contexte disponible: profil, categorie, niveau, publication;
3. choisit l'agent principal;
4. recommande les agents secondaires;
5. retourne une feuille de route courte avec liens directs.

Version actuelle:

- fichier: `ai_engine/orchestrator.py`
- mode: gratuit, base sur regles et mots-cles;
- interface: `/arsenal-ia/`, bloc "Agent Orchestrateur";
- aucun appel API payant.

## Agents connectes

- Agent Visa Etudes
- Agent Pays & Programmes
- Agent Candidature Internationale
- Agent ATS CV + Lettre
- Agent Profil Talent
- Agent Residence Permanente
- Agents Tests de Langue
- Agent Ressources & Guides
- Agent Consultation Humaine

## Prochaines evolutions

- enregistrer les demandes d'orchestration en base pour analyser les besoins reels;
- ouvrir une version utilisateur dans "Mon espace";
- connecter les offres recommandees, documents candidat et guides PDF au plan d'action;
- ajouter un mode premium avec LLM quand le budget API sera disponible;
- ajouter un journal de decisions pour expliquer pourquoi un agent a ete choisi.

