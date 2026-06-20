from __future__ import annotations

import json

from django.db import transaction
from django.template.defaultfilters import slugify

from preparation_tests.models import CourseExercise, CourseLesson


def _unique_slug(base: str) -> str:
    slug = slugify(base)[:45] or "contenu-preparation"
    candidate = slug
    i = 2
    while CourseLesson.objects.filter(slug=candidate).exists():
        candidate = f"{slug}-{i}"
        i += 1
    return candidate


def _source_text(obj) -> str:
    parts = [
        getattr(obj, "title", ""),
        getattr(obj, "subtitle", ""),
        getattr(obj, "objective", ""),
        getattr(obj, "recurring_theme", ""),
        getattr(obj, "lesson_html", ""),
        getattr(obj, "subject_html", ""),
        getattr(obj, "correction_html", ""),
    ]
    return "\n".join([p for p in parts if p])


def _fallback_payload(obj, count: int) -> dict:
    section = obj.section
    theme = getattr(obj, "recurring_theme", "") or obj.title
    level = obj.level
    lesson_html = getattr(obj, "lesson_html", "") or getattr(obj, "subject_html", "") or (
        f"<p><strong>{theme}</strong> est un thème fréquent dans les examens de français. "
        f"Au niveau {level}, l'objectif est d'identifier l'idée principale, les détails utiles "
        "et les pièges de formulation.</p>"
    )
    expression_tasks = {
        "eo": [
            (
                "Présentation personnelle structurée",
                "Prépare une réponse orale de 2 minutes avec introduction, deux arguments et conclusion.",
                f"Présente ton projet d'installation au Canada en expliquant tes motivations, ton domaine professionnel et tes premières démarches d'intégration.",
                "Structure attendue: introduction claire, deux arguments développés, exemple personnel, conclusion courte.",
            ),
            (
                "Convaincre un agent ou conseiller",
                "Réponds comme dans un entretien: sois précis, logique et convaincant.",
                "Un conseiller te demande pourquoi ton projet est réaliste. Explique ton plan, les ressources déjà préparées et les difficultés que tu anticipes.",
                "Une bonne réponse montre la cohérence du projet et utilise des connecteurs: d'abord, ensuite, cependant, c'est pourquoi.",
            ),
            (
                "Donner son opinion",
                "Donne ton avis et justifie-le avec des exemples concrets.",
                "Selon toi, quelle est la priorité pour réussir son intégration dans un nouveau pays: la langue, l'emploi ou le réseau social ?",
                "Il faut choisir une position, reconnaître une nuance possible et défendre l'idée avec au moins deux exemples.",
            ),
            (
                "Comparer deux choix",
                "Compare les avantages et limites de deux options avant de conclure.",
                "Compare l'installation dans une grande ville et dans une ville moyenne pour un nouvel immigrant.",
                "La réponse doit comparer clairement coût, emploi, services, qualité de vie et adaptation familiale.",
            ),
            (
                "Raconter une expérience",
                "Raconte une expérience passée en montrant ce que tu as appris.",
                "Raconte une situation où tu as dû t'adapter à un nouvel environnement et explique comment cela peut t'aider au Canada.",
                "Une bonne réponse utilise le passé, décrit le problème, l'action menée et la leçon retenue.",
            ),
            (
                "Réagir à une objection",
                "Réponds à une objection avec calme et arguments.",
                "Quelqu'un te dit que recommencer sa carrière dans un autre pays est trop risqué. Réponds à cette objection.",
                "La réponse doit reconnaître le risque, proposer des solutions et finir par une conclusion positive mais réaliste.",
            ),
        ],
        "ee": [
            (
                "Demande d'information",
                "Rédige un courriel formel de 160 à 200 mots.",
                "Tu veux t'inscrire à une séance d'information sur les démarches d'installation. Écris au centre d'accueil pour demander la date, les documents à apporter et les services disponibles.",
                "Correction attendue: objet clair, formule d'appel, contexte, trois demandes précises, formule de politesse.",
            ),
            (
                "Report de rendez-vous",
                "Rédige une lettre formelle avec justification et nouvelle proposition.",
                "Tu ne peux pas te présenter à un rendez-vous administratif. Écris pour t'excuser, expliquer brièvement la raison et proposer deux nouvelles disponibilités.",
                "La réponse doit rester polie, concise et contenir une demande claire de confirmation.",
            ),
            (
                "Réclamation polie",
                "Rédige un message formel en gardant un ton professionnel.",
                "Tu as reçu une information incomplète concernant ton dossier. Écris au service concerné pour signaler le problème et demander les précisions nécessaires.",
                "Une bonne copie explique les faits sans agressivité, indique ce qui manque et formule une demande précise.",
            ),
            (
                "Lettre de motivation courte",
                "Rédige un texte structuré de candidature.",
                "Tu souhaites participer à un programme local d'intégration professionnelle. Écris une lettre pour présenter ton profil, tes objectifs et ton intérêt pour le programme.",
                "La réponse doit valoriser le parcours, montrer la motivation et rester adaptée à un destinataire officiel.",
            ),
            (
                "Demande d'aide ou d'accompagnement",
                "Rédige un courriel formel et humain.",
                "Tu viens d'arriver dans une nouvelle ville et tu cherches un accompagnement pour comprendre les services essentiels. Écris à une association locale.",
                "La copie doit préciser la situation, les besoins et les disponibilités, avec une formule de remerciement.",
            ),
            (
                "Synthèse d'une situation",
                "Rédige un message clair et organisé.",
                "Un organisme te demande de résumer ta situation pour orienter ton dossier. Présente ton parcours, ton besoin principal et les prochaines étapes souhaitées.",
                "La réponse doit être organisée en paragraphes courts avec des informations utiles et vérifiables.",
            ),
        ],
    }
    comprehension_tasks = {
        "co": [
            (
                "Repérer la raison de l'appel",
                "Écoute le message et choisis l'objectif principal.",
                "Dans un message vocal d'un centre administratif, pourquoi l'agent appelle-t-il le demandeur ?",
                [
                    "Pour confirmer un rendez-vous et rappeler les documents à apporter",
                    "Pour annoncer que le dossier est définitivement refusé",
                    "Pour proposer une formation sans rapport avec l'immigration",
                    "Pour demander un paiement immédiat par téléphone",
                ],
                "A",
                "La bonne réponse identifie l'objectif global du message: confirmer une étape administrative et préciser les pièces nécessaires.",
            ),
            (
                "Identifier une date corrigée",
                "Fais attention aux corrections et aux changements d'information.",
                "L'agent mentionne d'abord mardi, puis corrige l'information. Quelle date faut-il retenir ?",
                [
                    "La date indiquée après la correction de l'agent",
                    "La première date entendue uniquement",
                    "La date de dépôt du dossier précédent",
                    "Aucune date, car le rendez-vous est annulé",
                ],
                "A",
                "Dans les annonces orales, la dernière information corrigée remplace souvent la première.",
            ),
            (
                "Comprendre une consigne",
                "Choisis l'action demandée au candidat.",
                "Quelle action le demandeur doit-il effectuer avant son rendez-vous ?",
                [
                    "Préparer les documents originaux et arriver en avance",
                    "Envoyer une réclamation au ministère",
                    "Changer immédiatement d'adresse en ligne",
                    "Refaire tous les formulaires déjà soumis",
                ],
                "A",
                "La consigne porte sur la préparation concrète du rendez-vous, pas sur une nouvelle demande complète.",
            ),
            (
                "Repérer un document demandé",
                "Distingue les documents simplement mentionnés des documents exigés.",
                "Quel document est explicitement demandé pour le rendez-vous ?",
                [
                    "Une pièce d'identité valide",
                    "Un contrat de travail signé par trois personnes",
                    "Un diplôme traduit dans toutes les langues",
                    "Une preuve de voyage touristique",
                ],
                "A",
                "La réponse correcte correspond au document exigé; les autres options sont des distracteurs administratifs.",
            ),
            (
                "Comprendre la conséquence",
                "Repère ce qui se passe si la personne ne respecte pas la consigne.",
                "Que risque le demandeur s'il arrive sans les documents requis ?",
                [
                    "Son rendez-vous peut être reporté",
                    "Son compte bancaire sera fermé",
                    "Il devra quitter le pays le jour même",
                    "Il recevra automatiquement une approbation",
                ],
                "A",
                "La conséquence logique dans ce type d'annonce est le report ou le traitement retardé du dossier.",
            ),
            (
                "Identifier le ton du message",
                "Analyse l'intention et le ton du locuteur.",
                "Quel est le ton général du message ?",
                [
                    "Informatif et professionnel",
                    "Ironique et familier",
                    "Agressif et menaçant",
                    "Publicitaire et enthousiaste",
                ],
                "A",
                "Une annonce administrative vise surtout à informer clairement et professionnellement.",
            ),
        ],
        "ce": [
            (
                "Identifier l'idée principale",
                "Lis le texte et choisis l'idée centrale.",
                "Quelle idée principale se dégage d'un article sur l'intégration professionnelle des immigrants ?",
                [
                    "L'intégration dépend à la fois des compétences, de la reconnaissance des diplômes et du réseau professionnel",
                    "Les diplômes étrangers sont toujours acceptés automatiquement",
                    "Le marché du travail ne concerne pas les nouveaux arrivants",
                    "La langue n'a aucun impact sur l'emploi",
                ],
                "A",
                "La bonne réponse résume plusieurs dimensions du texte au lieu de retenir un détail isolé.",
            ),
            (
                "Comprendre une cause",
                "Repère la relation de cause à effet.",
                "Pourquoi certains immigrants acceptent-ils d'abord un emploi inférieur à leur qualification ?",
                [
                    "Parce que la reconnaissance des diplômes et l'expérience locale peuvent prendre du temps",
                    "Parce qu'ils ne souhaitent jamais travailler dans leur domaine",
                    "Parce que les employeurs interdisent toute progression",
                    "Parce que les formations sont toujours gratuites",
                ],
                "A",
                "La cause est liée aux obstacles d'entrée sur le marché, pas à une absence de motivation.",
            ),
            (
                "Distinguer fait et opinion",
                "Choisis l'énoncé qui exprime le point de vue de l'auteur.",
                "Quel énoncé relève plutôt d'une opinion argumentée ?",
                [
                    "Les programmes d'accompagnement devraient être renforcés pour accélérer l'intégration",
                    "Un pourcentage précis de candidats a répondu à l'enquête",
                    "Le texte cite le nom d'un organisme public",
                    "La date de publication figure en haut de l'article",
                ],
                "A",
                "Une opinion propose une position ou une recommandation; les autres réponses sont des faits observables.",
            ),
            (
                "Comprendre un connecteur",
                "Analyse le rôle du connecteur dans la phrase.",
                "Dans la phrase contenant 'cependant', quelle relation logique est introduite ?",
                [
                    "Une opposition ou une nuance",
                    "Une addition sans contraste",
                    "Une conclusion définitive",
                    "Une chronologie uniquement",
                ],
                "A",
                "'Cependant' introduit une restriction, une opposition ou une nuance par rapport à l'idée précédente.",
            ),
            (
                "Faire une inférence",
                "Déduis une information qui n'est pas dite mot pour mot.",
                "Si un candidat multiplie les stages et rencontres professionnelles, que peut-on déduire ?",
                [
                    "Il cherche à construire une expérience locale et un réseau",
                    "Il refuse de travailler durablement",
                    "Il abandonne automatiquement son projet",
                    "Il évite tout contact avec les employeurs",
                ],
                "A",
                "L'inférence s'appuie sur les indices du texte: stages, rencontres et réseau professionnel.",
            ),
            (
                "Comprendre le vocabulaire",
                "Trouve le sens du mot en contexte.",
                "Dans ce contexte, que signifie 'valoriser son parcours' ?",
                [
                    "Présenter ses expériences comme des atouts utiles",
                    "Masquer toutes ses expériences passées",
                    "Refuser de parler de ses compétences",
                    "Changer complètement d'identité professionnelle",
                ],
                "A",
                "Valoriser signifie mettre en avant ce qui est pertinent et positif dans son parcours.",
            ),
        ],
    }
    questions = []
    for i in range(max(1, count)):
        if section in expression_tasks:
            title, instruction, question, explanation = expression_tasks[section][i % len(expression_tasks[section])]
            questions.append({
                "title": title,
                "instruction": instruction,
                "question": question,
                "options": ["Réponse libre", "Réponse libre", "", ""],
                "correct_answer": "A",
                "explanation": explanation,
            })
        elif section in comprehension_tasks:
            title, instruction, question, options, correct, explanation = comprehension_tasks[section][i % len(comprehension_tasks[section])]
            questions.append({
                "title": title,
                "instruction": instruction,
                "question": question,
                "options": options,
                "correct_answer": correct,
                "explanation": explanation,
            })
        else:
            questions.append({
                "title": f"Question {i + 1}",
                "instruction": "Choisis la meilleure réponse.",
                "question": f"Quel est l'élément central du thème: {theme} ?",
                "options": [
                    theme[:240],
                    "Une information contraire au document",
                    "Un détail sans rapport avec la question",
                    "Une généralisation trop large",
                ],
                "correct_answer": "A",
                "explanation": "La bonne réponse reprend directement le thème ciblé. Les autres options sont soit hors sujet, soit trop larges.",
            })
    return {"lesson_html": lesson_html, "questions": questions}


def _ai_payload(obj, count: int) -> dict:
    from ai_engine.services.llm_service import call_llm

    system = (
        "Tu es un concepteur pédagogique expert TEF Canada, TCF Canada, DELF, DALF. "
        "Tu produis uniquement du JSON valide, sans markdown."
    )
    user = {
        "task": "Créer une mini-leçon et des exercices corrigés à partir d'un sujet d'examen fréquent.",
        "section": obj.section,
        "level": obj.level,
        "exam_code": getattr(obj, "exam_code", "cecr"),
        "title": obj.title,
        "source": _source_text(obj)[:6000],
        "count": count,
        "schema": {
            "lesson_html": "<p>mini leçon ciblée</p>",
            "questions": [{
                "title": "titre court",
                "instruction": "consigne",
                "question": "question ou sujet",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "explanation": "correction détaillée",
            }],
        },
    }
    raw = call_llm(system, json.dumps(user, ensure_ascii=False))
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise ValueError("Réponse IA invalide")
    return data


def generate_exercises_for_source(obj, *, count: int = 6, use_ai: bool = True, replace: bool = False) -> dict:
    try:
        if use_ai:
            payload = _ai_payload(obj, count)
            generated_by = "ia"
        else:
            payload = _fallback_payload(obj, count)
            generated_by = "fallback"
    except Exception as exc:
        payload = _fallback_payload(obj, count)
        generated_by = f"fallback: {exc}"

    questions = payload.get("questions") or []
    lesson_html = payload.get("lesson_html") or _fallback_payload(obj, count)["lesson_html"]

    with transaction.atomic():
        lesson = getattr(obj, "related_lesson", None)
        if replace:
            obj.exercises.clear()
            if lesson:
                lesson.exercises.all().delete()
        if not lesson:
            lesson = CourseLesson.objects.create(
                section=obj.section,
                level=obj.level,
                title=obj.title,
                slug=_unique_slug(f"{obj.section}-{obj.level}-{obj.title}"),
                locale=getattr(obj, "language", "fr") or "fr",
                content_html=lesson_html,
                order=999,
                is_published=True,
            )
            obj.related_lesson = lesson
            obj.save(update_fields=["related_lesson", "updated_at"])
        elif lesson_html and not lesson.content_html:
            lesson.content_html = lesson_html
            lesson.save(update_fields=["content_html", "updated_at"])

        created = []
        start_order = lesson.exercises.count() + 1
        for idx, q in enumerate(questions[:count], start=start_order):
            options = list(q.get("options") or [])
            while len(options) < 4:
                options.append("")
            correct = (q.get("correct_answer") or "A").upper()[:1]
            if correct not in {"A", "B", "C", "D"}:
                correct = "A"
            ex = CourseExercise.objects.create(
                lesson=lesson,
                title=(q.get("title") or f"Exercice {idx}")[:255],
                instruction=q.get("instruction") or "Réponds à la question.",
                question_text=q.get("question") or obj.title,
                option_a=options[0][:255] or "Réponse libre",
                option_b=options[1][:255] or "Réponse libre",
                option_c=options[2][:255],
                option_d=options[3][:255],
                correct_option=correct,
                summary=q.get("explanation") or "",
                order=idx,
                is_active=True,
            )
            created.append(ex)

        if hasattr(obj, "exercises"):
            obj.exercises.add(*created)

    return {"lesson": lesson, "created": len(created), "generated_by": generated_by}
