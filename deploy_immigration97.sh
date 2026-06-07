#!/bin/bash
# Script de déploiement rapide immigration97.com
# Exécutez ceci APRÈS avoir lancé l'instance EC2 et configuré les bases
# Lancez : bash deploy_immigration97.sh

set -e

echo "🚀 Déploiement immigration97.com"
echo "================================="

# Variables
DEPLOYER_USER="deployer"
PROJECT_DIR="/home/$DEPLOYER_USER/projects/immigration97"
REPO_URL="${1:-https://github.com/VOTRE_USERNAME/immigration97.git}"

# Vérifier si connected en tant que ubuntu (root)
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Lancez ce script en tant qu'ubuntu (sudo n'est pas nécessaire)"
    exit 1
fi

echo "1️⃣  Cloner repo..."
sudo su - $DEPLOYER_USER << SUDO_EOF
set -e
mkdir -p ~/projects
cd ~/projects

if [ ! -d "immigration97" ]; then
    git clone $REPO_URL
fi

cd immigration97
echo "✅ Repo cloné/à jour"
SUDO_EOF

echo ""
echo "2️⃣  Créer venv et installer dépendances..."
sudo su - $DEPLOYER_USER << SUDO_EOF
cd ~/projects/immigration97
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dépendances installées"
SUDO_EOF

echo ""
echo "3️⃣  Migrations et collectstatic..."
sudo su - $DEPLOYER_USER << SUDO_EOF
cd ~/projects/immigration97
source .venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput --clear
echo "✅ Migrations et assets OK"
SUDO_EOF

echo ""
echo "4️⃣  Créer/restart service Gunicorn..."
sudo systemctl daemon-reload
sudo systemctl restart immigration97
echo "✅ Service redémarré"

echo ""
echo "5️⃣  Vérifications finales..."
sleep 2
sudo systemctl status immigration97 --no-pager || echo "⚠️  Service pas ok, voir logs:"
echo ""
echo "Logs (dernières 20 lignes):"
sudo journalctl -u immigration97 -n 20 --no-pager
echo ""
echo "6️⃣  Test nginx..."
sudo nginx -t
echo "✅ Config nginx OK"

echo ""
echo "================================="
echo "✅ Déploiement terminé!"
echo ""
echo "Prochaines étapes:"
echo "- Vérifier : curl -I https://immigration97.com"
echo "- Logs: sudo journalctl -u immigration97 -f"
echo ""
