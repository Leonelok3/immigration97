from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid

from core.constants import LEVEL_CHOICES, LEVEL_ORDER

# =====================================================
# 📘 EXAMENS
# =====================================================

class Exam(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    language = models.CharField(
        max_length=2,
        choices=[("fr", "Français"), ("en", "Anglais"), ("de", "Allemand")],
    )
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class ExamSection(models.Model):
    class SectionCode(models.TextChoices):
        CO = "co", _("Compréhension orale")
        CE = "ce", _("Compréhension écrite")
        EE = "ee", _("Expression écrite")
        EO = "eo", _("Expression orale")

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="sections")
    code = models.CharField(max_length=2, choices=SectionCode.choices)
    order = models.PositiveIntegerField(default=1)
    duration_sec = models.PositiveIntegerField(default=600)

    def __str__(self):
        return f"{self.exam.code.upper()} - {self.code.upper()}"


# =====================================================
# 📚 CONTENU
# =====================================================

class Passage(models.Model):
    title = models.CharField(max_length=200, blank=True)
    text = models.TextField()

    def __str__(self):
        return self.title or f"Passage {self.pk}"


class Asset(models.Model):
    kind = models.CharField(
        max_length=20,
        choices=[("audio", "Audio"), ("image", "Image"), ("video", "Video")],
    )
    file = models.FileField(upload_to="assets/")
    lang = models.CharField(max_length=10, default="fr")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.kind} ({self.lang})"

    @property
    def public_url(self) -> str:
        """
        URL classique (non protégée) servie par MEDIA_URL.
        Ne casse rien : c'est le comportement actuel.
        """
        try:
            return self.file.url
        except Exception:
            return ""

    @property
    def secure_url(self) -> str:
        """
        URL protégée : passe par /protected-media/...
        Compatible avec notre endpoint mediafiles (dev/prod-ready).
        """
        if not self.file:
            return ""

        # file.name ressemble à "assets/xxx.mp3"
        # On veut /protected-media/assets/xxx.mp3
        return f"{settings.PROTECTED_MEDIA_URL}{self.file.name}"



# =====================================================
# 📝 QUESTIONS
# =====================================================

class Question(models.Model):
    SUBTYPE_CHOICES = [
        ("mcq", "Choix multiple"),
        ("text", "Texte libre"),
        ("audio", "Audio"),
    ]

    DIFFICULTY_CHOICES = [
        ("easy", "Facile"),
        ("medium", "Moyen"),
        ("hard", "Difficile"),
    ]

    section = models.ForeignKey(ExamSection, on_delete=models.CASCADE, related_name="questions")
    stem = models.TextField()
    passage = models.ForeignKey(Passage, null=True, blank=True, on_delete=models.SET_NULL)
    asset = models.ForeignKey(Asset, null=True, blank=True, on_delete=models.SET_NULL)
    subtype = models.CharField(max_length=10, choices=SUBTYPE_CHOICES, default="mcq")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default="medium")

    def __str__(self):
        return f"Question {self.pk}"


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)


class Explanation(models.Model):
    question = models.OneToOneField(Question, on_delete=models.CASCADE)
    text_md = models.TextField()


# =====================================================
# ⏱️ SESSIONS
# =====================================================

class Session(models.Model):
    MODE_CHOICES = [
        ("practice", "Entraînement"),
        ("mock", "Examen blanc"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exam_sessions")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    section = models.ForeignKey(
        ExamSection,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sessions"
    )

    mode = models.CharField(max_length=10, choices=MODE_CHOICES)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    total_score = models.FloatField(default=0)
    duration_sec = models.PositiveIntegerField(default=0)


class Attempt(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="attempts")
    section = models.ForeignKey(ExamSection, on_delete=models.CASCADE)

    raw_score = models.PositiveIntegerField(default=0)
    total_items = models.PositiveIntegerField(default=0)

    score_percent = models.FloatField(default=0)



class Answer(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    is_correct = models.BooleanField(default=False)
    payload = models.JSONField(default=dict)


# =====================================================
# 📖 COURS (TOUS ACCESSIBLES)
# =====================================================

from django.db import models

class CourseLesson(models.Model):
    """
    📘 Leçon CECR universelle (TRANSITION)
    """

    # 🔒 ANCIEN LIEN (NE PAS SUPPRIMER MAINTENANT)
    exam = models.ForeignKey(
        "preparation_tests.Exam",
        on_delete=models.CASCADE,
        related_name="legacy_lessons",
        null=True,
        blank=True,
    )

    # 🆕 NOUVEAU LIEN MULTI-EXAMENS (PRO)
    exams = models.ManyToManyField(
        "preparation_tests.Exam",
        related_name="lessons",
        blank=True,
        help_text="Examens utilisant cette leçon (TEF, TCF, DELF, DALF)",
    )

    section = models.CharField(
        max_length=2,
        choices=[
            ("co", "Compréhension Orale"),
            ("ce", "Compréhension Écrite"),
            ("ee", "Expression Écrite"),
            ("eo", "Expression Orale"),
        ],
    )

    level = models.CharField(
        max_length=2,
        choices=[
            ("A1", "A1"),
            ("A2", "A2"),
            ("B1", "B1"),
            ("B2", "B2"),
            ("C1", "C1"),
            ("C2", "C2"),
        ],
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    locale = models.CharField(max_length=5, default="fr")

    content_html = models.TextField()

    order = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["level", "order"]
        verbose_name = "Leçon"
        verbose_name_plural = "Leçons"

    def __str__(self):
        exams = ", ".join(e.code.upper() for e in self.exams.all())
        return f"[{self.level}] {self.section.upper()} – {self.title} ({exams})"

    @property
    def cefr_level(self):
        return self.level

    def is_accessible_by(self, user):
        return True


###############################################################################

class CourseExercise(models.Model):
    lesson = models.ForeignKey(
        CourseLesson,
        on_delete=models.CASCADE,
        related_name="exercises",
    )

    title = models.CharField(max_length=255)
    instruction = models.TextField(blank=True)
    question_text = models.TextField()

    audio = models.ForeignKey(
        Asset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exercise_audios",
    )

    image = models.ForeignKey(
        Asset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exercise_images",
    )

    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255, blank=True)
    option_d = models.CharField(max_length=255, blank=True)

    correct_option = models.CharField(
        max_length=1,
        choices=[
            ("A", "A"),
            ("B", "B"),
            ("C", "C"),
            ("D", "D"),
        ],
    )

    summary = models.TextField(blank=True)

    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.lesson.title} – Exercice {self.order}"

    @property
    def audio_url(self) -> str:
        """
        URL audio publique — servie via /media/ par Django (dev) ou Nginx (prod).
        La protection premium est gérée au niveau du template (row.can_audio).
        """
        if not self.audio or self.audio.kind != "audio":
            return ""
        return self.audio.public_url

    @property
    def audio_public_url(self) -> str:
        """
        URL audio publique (legacy) si tu as besoin de comparer.
        """
        if not self.audio or self.audio.kind != "audio":
            return ""
        return self.audio.public_url


# =====================================================
# 📊 PROGRESSION & CERTIFICATS
# =====================================================

class UserSkillProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    exam_code = models.CharField(max_length=20)
    skill = models.CharField(max_length=2)
    score_percent = models.PositiveIntegerField(default=0)
    # Niveau CECR courant (A1..C2)
    current_level = models.CharField(
        max_length=2,
        choices=LEVEL_CHOICES,
        default="A1",
    )
    # Nombre total de tentatives prises en compte
    total_attempts = models.PositiveIntegerField(default=0)


class UserSkillResult(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    section = models.ForeignKey(
        ExamSection,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    score_percent = models.PositiveIntegerField()
    total_questions = models.PositiveIntegerField()
    correct_answers = models.PositiveIntegerField()

class UserLessonProgress(models.Model):
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="lesson_progress",
    )

    lesson = models.ForeignKey(
        CourseLesson,
        on_delete=models.CASCADE,
        related_name="user_progress",
    )

    percent = models.PositiveIntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    completed_exercises = models.PositiveIntegerField(default=0)
    total_exercises = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

class CEFRCertificate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    exam_code = models.CharField(max_length=20)
    level = models.CharField(max_length=2)

    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )

    issued_at = models.DateTimeField(auto_now_add=True)

# =====================================================
# 🗺️ PLAN D'ÉTUDE
# =====================================================

class StudyPlanProgress(models.Model):
    """
    Suivi du plan d'étude personnalisé de l'utilisateur
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    exam_code = models.CharField(max_length=20)
    current_day = models.PositiveIntegerField(default=1)
    total_days = models.PositiveIntegerField(default=30)
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ["user", "exam_code"]
        ordering = ["-last_activity"]

    def __str__(self):
        return f"{self.user.username} - {self.exam_code} (Jour {self.current_day}/{self.total_days})"


class CoachIAReport(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coach_reports",
    )

    exam_code = models.CharField(max_length=20)
    scope = models.CharField(
        max_length=20,
        choices=[
            ("global", "Global"),
            ("co", "Compréhension orale"),
            ("ce", "Compréhension écrite"),
            ("ee", "Expression écrite"),
            ("eo", "Expression orale"),
        ],
        default="global",
    )

    data = models.JSONField()  # analyse IA complète
    score_snapshot = models.JSONField(default=dict)  # scores au moment T

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"IA {self.exam_code} ({self.scope}) – {self.created_at:%Y-%m-%d}"


from django.db import models
from django.conf import settings
from django.utils import timezone


class UserExerciseProgress(models.Model):
    """
    1 ligne par (user, exercise).
    Permet d’éviter le double comptage et d’avoir une progression fiable.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lesson = models.ForeignKey("preparation_tests.CourseLesson", on_delete=models.CASCADE)
    exercise = models.ForeignKey("preparation_tests.CourseExercise", on_delete=models.CASCADE)

    is_completed = models.BooleanField(default=False)  # completed = réponse correcte validée
    attempts = models.PositiveIntegerField(default=0)
    last_answer = models.CharField(max_length=1, blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "exercise")
        indexes = [
            models.Index(fields=["user", "lesson"]),
            models.Index(fields=["user", "exercise"]),
        ]

    def mark_attempt(self, selected: str, correct: bool):
        self.attempts = (self.attempts or 0) + 1
        self.last_answer = (selected or "").upper()

        if correct and not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()


class DetailedError(models.Model):
    """
    Erreur pédagogique exploitable par la révision intelligente.
    Une ligne suit une difficulté utilisateur sur un exercice donné, avec
    catégorie, historique et planification de révision espacée.
    """
    CATEGORY_CHOICES = [
        ("grammar", "Grammaire"),
        ("lexical", "Lexique"),
        ("comprehension", "Compréhension"),
        ("listening", "Écoute"),
        ("strategy", "Stratégie d'examen"),
        ("writing", "Expression écrite"),
        ("speaking", "Expression orale"),
    ]
    STATUS_CHOICES = [
        ("active", "À revoir"),
        ("resolved", "Maîtrisée"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="detailed_errors")
    lesson = models.ForeignKey("preparation_tests.CourseLesson", on_delete=models.CASCADE, related_name="detailed_errors")
    exercise = models.ForeignKey("preparation_tests.CourseExercise", on_delete=models.CASCADE, related_name="detailed_errors")

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="comprehension", db_index=True)
    source = models.CharField(max_length=30, blank=True, default="lesson", db_index=True)
    selected_answer = models.CharField(max_length=10, blank=True, default="")
    correct_answer = models.CharField(max_length=10, blank=True, default="")
    explanation = models.TextField(blank=True)

    occurrences = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active", db_index=True)

    ease_factor = models.FloatField(default=2.5)
    interval_days = models.PositiveIntegerField(default=1)
    repetitions = models.PositiveIntegerField(default=0)
    lapses = models.PositiveIntegerField(default=0)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    next_review_at = models.DateTimeField(default=timezone.now, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "exercise")
        indexes = [
            models.Index(fields=["user", "status", "next_review_at"]),
            models.Index(fields=["user", "category", "status"]),
            models.Index(fields=["user", "lesson"]),
        ]
        ordering = ["next_review_at", "-occurrences", "-updated_at"]
        verbose_name = "Erreur détaillée"
        verbose_name_plural = "Erreurs détaillées"

    def __str__(self):
        return f"{self.user} — {self.get_category_display()} — {self.exercise_id}"


# =====================================================
# 🎤 SOUMISSIONS EO / EE
# =====================================================

class EOSubmission(models.Model):
    """
    Enregistrement audio soumis par un étudiant pour un exercice EO.
    L'IA transcrit (Whisper) puis évalue la prise de parole.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="eo_submissions")
    exercise = models.ForeignKey("preparation_tests.CourseExercise", on_delete=models.CASCADE, related_name="eo_submissions")
    audio_file = models.FileField(upload_to="eo_submissions/", blank=True)
    transcript = models.TextField(blank=True)
    score = models.FloatField(null=True, blank=True)  # 0–100
    feedback_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"EO #{self.pk} — {self.user} — {self.score}/100"


class EESubmission(models.Model):
    """
    Texte rédigé par un étudiant pour un exercice EE.
    L'IA corrige la production écrite et la note.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ee_submissions")
    exercise = models.ForeignKey("preparation_tests.CourseExercise", on_delete=models.CASCADE, related_name="ee_submissions")
    text = models.TextField()
    word_count = models.PositiveIntegerField(default=0)
    score = models.FloatField(null=True, blank=True)  # 0–100
    feedback_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"EE #{self.pk} — {self.user} — {self.score}/100"



# =====================================================
# 🧪 HISTORIQUE EXAMENS BLANCS PAR NIVEAU CECR
# =====================================================

class MockExamResult(models.Model):
    """
    Enregistre le résultat d'un examen blanc par niveau CECR.
    Un enregistrement par passage (POST de level_mock_exam).
    """
    LEVEL_CHOICES = [
        ("A1", "A1"), ("A2", "A2"),
        ("B1", "B1"), ("B2", "B2"),
        ("C1", "C1"), ("C2", "C2"),
    ]

    user          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mock_exam_results",
    )
    level         = models.CharField(max_length=2, choices=LEVEL_CHOICES, db_index=True)
    score_co      = models.PositiveIntegerField(null=True, blank=True)
    score_ce      = models.PositiveIntegerField(null=True, blank=True)
    score_global  = models.PositiveIntegerField(null=True, blank=True)
    co_correct    = models.PositiveIntegerField(default=0)
    co_total      = models.PositiveIntegerField(default=0)
    ce_correct    = models.PositiveIntegerField(default=0)
    ce_total      = models.PositiveIntegerField(default=0)
    cefr_estimate = models.CharField(max_length=10, blank=True)
    taken_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-taken_at"]
        verbose_name = "Résultat examen blanc"
        verbose_name_plural = "Résultats examens blancs"

    def __str__(self):
        return f"{self.user} — {self.level} — {self.score_global}% ({self.taken_at:%Y-%m-%d})"


# =====================================================
# 🏆 RÉSULTATS EXAMENS BLANCS FORMAT OFFICIEL
# TEF / TCF / DELF / DALF
# =====================================================

class ExamFormatResult(models.Model):
    """
    Enregistre le résultat d'un examen blanc format officiel.
    Un enregistrement par passage POST de exam_format_exam.
    """
    EXAM_CHOICES = [
        ("tef", "TEF Canada"),
        ("tcf", "TCF Canada"),
        ("delf", "DELF"),
        ("dalf", "DALF"),
    ]
    LEVEL_CHOICES = [
        ("A1", "A1"), ("A2", "A2"),
        ("B1", "B1"), ("B2", "B2"),
        ("C1", "C1"), ("C2", "C2"),
    ]

    user         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exam_format_results",
    )
    exam_code    = models.CharField(max_length=6, choices=EXAM_CHOICES, db_index=True)
    level        = models.CharField(max_length=2, choices=LEVEL_CHOICES, db_index=True)
    co_correct   = models.PositiveIntegerField(default=0)
    co_total     = models.PositiveIntegerField(default=0)
    ce_correct   = models.PositiveIntegerField(default=0)
    ce_total     = models.PositiveIntegerField(default=0)
    co_pct       = models.PositiveIntegerField(default=0)
    ce_pct       = models.PositiveIntegerField(default=0)
    global_pct   = models.PositiveIntegerField(default=0)
    co_score     = models.PositiveIntegerField(default=0)   # brut (0-450 TEF, 0-25 DELF…)
    ce_score     = models.PositiveIntegerField(default=0)
    global_score = models.PositiveIntegerField(default=0)   # co_score + ce_score
    score_max    = models.PositiveIntegerField(default=50)  # 450, 699, 50 selon exam
    cefr_co      = models.CharField(max_length=10, blank=True)
    cefr_ce      = models.CharField(max_length=10, blank=True)
    cefr_global  = models.CharField(max_length=10, blank=True)
    passed       = models.BooleanField(null=True, blank=True)  # None=TEF/TCF, T/F=DELF/DALF
    taken_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-taken_at"]
        verbose_name = "Résultat examen officiel"
        verbose_name_plural = "Résultats examens officiels"

    def __str__(self):
        return f"{self.user} — {self.get_exam_code_display()} {self.level} — {self.global_pct}% ({self.taken_at:%Y-%m-%d})"


# =====================================================
# 📅 PACKS MENSUELS & ANCIENS SUJETS D'EXAMEN
# =====================================================

LANG_CHOICES_PREP = [
    ("fr", "Français"),
    ("de", "Allemand"),
    ("en", "Anglais"),
]
SECTION_CHOICES_PREP = [
    ("co", "Compréhension Orale"),
    ("ce", "Compréhension Écrite"),
    ("eo", "Expression Orale"),
    ("ee", "Expression Écrite"),
]
LEVEL_CHOICES_PREP = [
    ("A1", "A1"), ("A2", "A2"),
    ("B1", "B1"), ("B2", "B2"),
    ("C1", "C1"), ("C2", "C2"),
]
EXAM_CODE_CHOICES_PREP = [
    ("cecr", "CECR"),
    ("tef", "TEF Canada"),
    ("tcf", "TCF Canada"),
    ("delf", "DELF"),
    ("dalf", "DALF"),
]


class MonthlyTrainingPack(models.Model):
    language = models.CharField(max_length=5, choices=LANG_CHOICES_PREP, default="fr", db_index=True)
    section = models.CharField(max_length=2, choices=SECTION_CHOICES_PREP, db_index=True)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES_PREP, default="B1", db_index=True)
    exam_code = models.CharField(max_length=10, choices=EXAM_CODE_CHOICES_PREP, default="cecr", db_index=True)
    month = models.DateField(db_index=True)

    title = models.CharField(max_length=220)
    slug = models.SlugField(unique=True)
    subtitle = models.CharField(max_length=300, blank=True)
    objective = models.TextField(blank=True)
    lesson_html = models.TextField(blank=True)
    correction_html = models.TextField(blank=True)
    recurring_theme = models.CharField(max_length=220, blank=True)

    related_lesson = models.ForeignKey(
        CourseLesson,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="monthly_packs",
    )
    exercises = models.ManyToManyField(CourseExercise, blank=True, related_name="monthly_packs")

    is_premium = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-month", "order", "-created_at"]
        verbose_name = "Pack mensuel"
        verbose_name_plural = "Packs mensuels"

    def __str__(self):
        return f"{self.get_section_display()} {self.level} — {self.title}"

    @property
    def description(self):
        return self.objective

    @property
    def content_html(self):
        return self.lesson_html


class PastExamSubject(models.Model):
    language = models.CharField(max_length=5, choices=LANG_CHOICES_PREP, default="fr", db_index=True)
    exam_code = models.CharField(max_length=10, choices=EXAM_CODE_CHOICES_PREP, db_index=True)
    section = models.CharField(max_length=2, choices=SECTION_CHOICES_PREP, db_index=True)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES_PREP, default="B1", db_index=True)

    title = models.CharField(max_length=220)
    slug = models.SlugField(unique=True)
    source_label = models.CharField(max_length=160, blank=True, help_text="Ex: TEF Canada 2024, DELF B2 session exemple")
    recurring_theme = models.CharField(max_length=220, blank=True)
    frequency_score = models.PositiveIntegerField(default=50, help_text="0-100 : probabilité/récurrence du thème")

    subject_html = models.TextField(blank=True)
    correction_html = models.TextField(blank=True)
    pdf_subject = models.FileField(upload_to="past_exam_subjects/subjects/", blank=True, null=True)
    pdf_correction = models.FileField(upload_to="past_exam_subjects/corrections/", blank=True, null=True)

    related_lesson = models.ForeignKey(
        CourseLesson,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="past_exam_subjects",
    )
    exercises = models.ManyToManyField(CourseExercise, blank=True, related_name="past_exam_subjects")

    is_premium = models.BooleanField(default=True)
    is_published = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-frequency_score", "order", "-created_at"]
        verbose_name = "Ancien sujet d'examen"
        verbose_name_plural = "Anciens sujets d'examen"

    def __str__(self):
        return f"{self.get_exam_code_display()} {self.section.upper()} {self.level} — {self.title}"


# =====================================================
# 🌟 CONTENUS MIS EN AVANT (admin-managed)
# =====================================================

class FeaturedContent(models.Model):
    LANG_CHOICES = [
        ("fr", "Français"),
        ("de", "Allemand"),
        ("en", "Anglais"),
    ]
    SECTION_CHOICES = [
        ("co", "Compréhension Orale"),
        ("ce", "Compréhension Écrite"),
        ("eo", "Expression Orale"),
        ("ee", "Expression Écrite"),
        ("general", "Général"),
    ]
    TYPE_CHOICES = [
        ("monthly", "Sujet du mois"),
        ("subject", "Sujet officiel"),
        ("correction", "Correction officielle"),
        ("tip", "Conseil / Astuce"),
    ]

    language = models.CharField(max_length=5, choices=LANG_CHOICES, default="fr", db_index=True)
    section = models.CharField(max_length=10, choices=SECTION_CHOICES, default="general", db_index=True)
    content_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default="subject", verbose_name="Type")

    title = models.CharField(max_length=200, verbose_name="Titre")
    subtitle = models.CharField(max_length=300, blank=True, verbose_name="Sous-titre")
    description = models.TextField(blank=True, verbose_name="Description courte")
    content_html = models.TextField(blank=True, verbose_name="Contenu HTML (correction, conseils…)")
    pdf_file = models.FileField(
        upload_to="featured_content/",
        blank=True, null=True,
        verbose_name="Fichier PDF (sujet / correction)",
    )

    is_premium = models.BooleanField(
        default=False,
        verbose_name="Réservé Premium",
        help_text="Cocher = visible seulement pour les abonnés",
    )
    is_published = models.BooleanField(default=True, verbose_name="Publié")

    month = models.DateField(
        null=True, blank=True,
        verbose_name="Mois (pour 'Sujet du mois')",
        help_text="Mettre le 1er du mois concerné, ex: 2026-04-01",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-month", "order", "-created_at"]
        verbose_name = "Contenu mis en avant"
        verbose_name_plural = "Contenus mis en avant"

    def __str__(self):
        return f"[{self.get_language_display()} – {self.get_section_display()}] {self.get_content_type_display()} – {self.title}"
