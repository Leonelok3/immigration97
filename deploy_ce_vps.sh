#!/bin/bash
# Script de déploiement CE en VPS
# Exécuter sur le VPS: bash deploy_ce_vps.sh

set -e

PROJECT_DIR="${PROJECT_DIR:-/home/deployer/projects/immigration97}"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"

echo ""
echo "🚀 DÉPLOIEMENT COMPRÉHENSION ÉCRITE (CE) - VPS"
echo "============================================================"
echo "📁 Projet: $PROJECT_DIR"

# 1. GIT PULL
echo ""
echo "📥 [1/6] Git pull..."
cd "$PROJECT_DIR"
git pull origin main
echo "✅ Git pull réussi"

# 2. MIGRATE
echo ""
echo "🗄️  [2/6] Database migrations..."
"$PYTHON_BIN" manage.py migrate --noinput
"$PYTHON_BIN" manage.py showmigrations resources
echo "✅ Database migrations OK"

# 3. IMPORT CURRICULUM
echo ""
echo "📚 [3/6] Import curriculum CE (A1-C2)..."
"$PYTHON_BIN" manage.py import_reading_curriculum --file ai_engine/learning_content/reading_curriculum_A1_fr.json --clear
"$PYTHON_BIN" manage.py import_reading_curriculum --file ai_engine/learning_content/reading_curriculum_A2_fr.json
"$PYTHON_BIN" manage.py import_reading_curriculum --file ai_engine/learning_content/reading_curriculum_B1_fr.json
"$PYTHON_BIN" manage.py import_reading_curriculum --file ai_engine/learning_content/reading_curriculum_B2_fr.json
"$PYTHON_BIN" manage.py import_reading_curriculum --file ai_engine/learning_content/reading_curriculum_C1_fr.json
"$PYTHON_BIN" manage.py import_reading_curriculum --file ai_engine/learning_content/reading_curriculum_C2_fr.json
echo "✅ Curriculum CE importé (900 exercices)"

# 4. IMPORT EXAMS
echo ""
echo "📋 [4/6] Import exams CE (A1-C2)..."
"$PYTHON_BIN" manage.py import_reading_exams --file ai_engine/learning_content/exams_reading_a_b_fr.json --clear
"$PYTHON_BIN" manage.py import_reading_exams --file ai_engine/learning_content/exams_reading_c_fr.json
echo "✅ Exams CE importés (195 questions)"

# 5. STATIC FILES
echo ""
echo "📦 [5/6] Static files..."
"$PYTHON_BIN" manage.py collectstatic --noinput
echo "✅ Static files OK"

# 6. RESTART SERVICES
echo ""
echo "🔄 [6/6] Redémarrage services..."
sudo systemctl restart immigration97
sudo systemctl restart nginx
echo "✅ Services redémarrés"

# VÉRIFICATION FINAL
echo ""
echo "============================================================"
echo "✨ VÉRIFICATION FINALE"
echo "============================================================"
echo ""
"$PYTHON_BIN" manage.py shell << PYTHON_CMD
import django
from preparation_tests.models import CourseLesson, Question

lessons = CourseLesson.objects.filter(section="ce").count()
exercises = 0
for l in CourseLesson.objects.filter(section="ce"):
    exercises += l.exercises.count()
questions = Question.objects.filter(section__code="ce").count()

print(f"📘 Curriculum CE: {lessons} leçons, {exercises} exercices")
print(f"📋 Exams CE: {questions} questions")
print(f"✅ Total: {exercises + questions} contenus CE en production")
PYTHON_CMD

echo ""
echo "============================================================"
echo "🎉 DÉPLOIEMENT CE RÉUSSI!"
echo "============================================================"
echo ""
echo "📊 Status:"
echo "  ✅ Code déployé"
echo "  ✅ Database mise à jour"
echo "  ✅ Services redémarrés"
echo "  ✅ Production live"
echo ""
echo "🔗 App: https://immigration97.com"
echo "📞 Support: contact@immigration97.com"
echo ""
