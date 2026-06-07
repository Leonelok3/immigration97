# Workflow Déploiement immigration97 sur AWS

## 🎯 Étapes simplifiées

### ÉTAPE 1 : Créer l'instance EC2 (5 min)
```
AWS Console → EC2 → Launch instances
- AMI: Ubuntu 22.04 LTS
- Type: t2.micro
- Key pair: eshelle-prod-key
- Security group: Autoriser 22, 80, 443
- Launch
- ⏳ Attendre 2 min que "running" s'affiche
- 📋 Copier Public IPv4
```

### ÉTAPE 2 : Se connecter en SSH (1 min)
```powershell
$IP = "X.X.X.X"  # Votre IP publique
ssh -i "$env:USERPROFILE\.ssh\eshelle-prod-key.pem" ubuntu@$IP
```

### ÉTAPE 3 : Setup du serveur (5 min)
Une fois connecté, copiez **tout ce script bash** et lancez-le :
```bash
# Copie complète du script dans AWS_DEPLOYMENT_SETUP.md, section 3
# Depuis le #!/bin/bash jusqu'au dernier echo
```

### ÉTAPE 4 : Déployer le code (3 min)
Toujours connecté en SSH, lancez le bloc de code de la section 4 du guide (git clone, venv, .env, migrations)

### ÉTAPE 5 : Configurer Gunicorn (1 min)
Section 5 du guide

### ÉTAPE 6 : Configurer Nginx (1 min)
Section 6 du guide

### ÉTAPE 7 : SSL avec Certbot (2 min)
Section 7 du guide

### ÉTAPE 8 : Mettre à jour DNS (1 min)
Section 10 du guide (Hostinger)

---

## 📊 Résumé Quick Commands

```bash
# 🟢 Connexion
ssh -i ~/.ssh/eshelle-prod-key.pem ubuntu@IP_PUBLIQUE

# 🟢 Status des services
sudo systemctl status immigration97
sudo systemctl status nginx
sudo systemctl status postgresql

# 🟢 Voir les logs
sudo journalctl -u immigration97 -f
sudo tail -f /var/log/nginx/error.log

# 🟢 Redémarrage après déploiement
cd ~/projects/immigration97
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput --clear
sudo systemctl restart immigration97

# 🟢 Test rapide
curl -I https://immigration97.com
```

---

## 🔄 Workflow après première déploiement

### En LOCAL (sur votre PC) :
```bash
cd immigration97
git add .
git commit -m "description"
git push origin main
```

### Sur AWS (SSH en tant que deployer) :
```bash
ssh ubuntu@IP_PUBLIC
sudo su - deployer
cd ~/projects/immigration97

# Option 1 : Full deploy (avec dépendances + migrations)
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput --clear
sudo systemctl restart immigration97

# Option 2 : Quick deploy (HTML/CSS/JS/Python seulement)
git pull origin main
source .venv/bin/activate
python manage.py collectstatic --noinput --clear
sudo systemctl restart immigration97

# Vérifier
sudo systemctl status immigration97
curl -I https://immigration97.com
```

---

## ✅ Checklist

- [ ] Instance EC2 créée et "running"
- [ ] SSH fonctionne : `ssh ubuntu@IP`
- [ ] Apt update/upgrade exécuté
- [ ] PostgreSQL démarré et user/db crées
- [ ] Repo cloné dans `/home/deployer/projects/immigration97`
- [ ] Venv créé et dépendances installées
- [ ] .env configuré (SECRET_KEY, DB_URL, ALLOWED_HOSTS)
- [ ] Migrations exécutées
- [ ] Collectstatic exécuté
- [ ] Service Gunicorn créé et running
- [ ] Nginx configuré et site actif
- [ ] SSL Certbot configuré
- [ ] DNS immigration97.com pointe vers IP EC2
- [ ] Tester : `curl -I https://immigration97.com` → 200 OK

---

## 🐛 Erreurs courantes

| Erreur | Cause | Solution |
|--------|-------|----------|
| `Connection refused` | Port 80/443 pas ouvert | Vérifier Security Group |
| `502 Bad Gateway` | Gunicorn pas running | `sudo systemctl restart immigration97` |
| `Database error` | PostgreSQL pas running ou user inexistant | `sudo systemctl restart postgresql` + vérifier .env |
| `SSL certificate error` | Domaine ne pointe pas vers l'IP | Attendre propagation DNS, vérifier Hostinger |
| `Permission denied` files | Propriétaire pas deployer | `sudo chown -R deployer:deployer /home/deployer/projects` |

---

## 📌 Fichiers importants

- **Guide complet** : `AWS_DEPLOYMENT_SETUP.md` (ce dossier)
- **Script rapide** : `deploy_immigration97.sh` (à copier sur le serveur si besoin)
- **Requirements** : `requirements.txt` (dépendances Python)
- **Env config** : `.env` (créé sur le serveur, à adapter)

---

## 🚀 Prêt?

1. Créez l'instance EC2 (AWS Console)
2. Notez son IP publique
3. Suivez étape par étape le guide AWS_DEPLOYMENT_SETUP.md
4. Testez avec `curl -I https://immigration97.com`
5. Modifiez localement, `git push`, puis `git pull` sur le serveur et restart!

Besoin d'aide ? Consultez les sections Troubleshooting du guide ou les logs avec `sudo journalctl -u immigration97 -f`
