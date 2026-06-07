# Déploiement immigration97.com sur AWS EC2

## 1. Créer une instance EC2 (AWS Console)

### Via la console AWS :
1. Allez sur https://console.aws.amazon.com/ec2/
2. **EC2 > Instances > Launch instances**
3. Configurez comme suit :

| Paramètre | Valeur |
|-----------|--------|
| **AMI** | Ubuntu 22.04 LTS (ami-*) |
| **Instance type** | t2.micro (free tier) ou t3.small |
| **Key pair** | eshelle-prod-key (créez si n'existe pas) |
| **VPC** | default |
| **Subnet** | default |
| **Auto-assign Public IP** | Enable |
| **Security Group** | Créez nouveau : "immigration97-sg" |

### Configuration du Security Group :
- **Type: SSH**, Protocol: TCP, Port: 22, Source: 0.0.0.0/0 (ou votre IP)
- **Type: HTTP**, Protocol: TCP, Port: 80, Source: 0.0.0.0/0
- **Type: HTTPS**, Protocol: TCP, Port: 443, Source: 0.0.0.0/0

4. **Launch instance**
5. Attendez 2-3 min que le statut passe à **running**
6. **Copiez l'IP publique** (colonne Public IPv4)

---

## 2. Première connexion SSH

```powershell
# Depuis PowerShell (Windows)
$IP = "X.X.X.X"  # Remplacez par l'IP publique
ssh -i "$env:USERPROFILE\.ssh\eshelle-prod-key.pem" ubuntu@$IP
```

À la première connexion, acceptez la fingerprint (tapez `yes`).

---

## 3. Setup du serveur (exécutez sur le serveur EC2)

Une fois connecté en SSH, lancez :

```bash
#!/bin/bash
set -e

echo "=== MISE À JOUR SYSTÈME ==="
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-venv python3-pip python3-dev \
    build-essential nginx postgresql postgresql-contrib postgresql-client \
    certbot python3-certbot-nginx curl wget

echo "=== CRÉER UTILISATEUR DEPLOYER ==="
sudo adduser --disabled-password --gecos "" deployer || true
sudo usermod -aG sudo deployer

echo "=== CONFIGURER UFW (FIREWALL) ==="
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo "=== CRÉER STRUCTURE RÉPERTOIRES ==="
sudo mkdir -p /home/deployer/projects
sudo chown -R deployer:deployer /home/deployer/projects

echo "=== CONFIGURER POSTGRESQL ==="
sudo systemctl start postgresql
sudo -u postgres psql -c "CREATE USER immigration97_user WITH PASSWORD 'immigration97StrongPass2026' CREATEDB;" || true
sudo -u postgres psql -c "CREATE DATABASE immigration97_db OWNER immigration97_user;" || true
sudo -u postgres psql -c "ALTER USER immigration97_user WITH PASSWORD 'immigration97StrongPass2026';" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE immigration97_db TO immigration97_user;" || true

echo "✅ Setup serveur terminé!"
```

Copiez-collez cette commande **entièrement** (depuis `#!/bin/bash` jusqu'au dernier `echo`).

---

## 4. Déployer le code (sur le serveur)

```bash
# Se connecter en tant que deployer
sudo su - deployer

# Cloner le repo (adapter l'URL Git)
cd ~/projects
git clone https://github.com/VOTRE_USERNAME/immigration97.git
cd immigration97

# Créer et activer venv
python3 -m venv .venv
source .venv/bin/activate

# Installer dépendances
pip install --upgrade pip
pip install -r requirements.txt

# Créer fichier .env
cat > .env << 'EOF'
SECRET_KEY=change-this-to-a-real-secret-key-in-production
DEBUG=False
ALLOWED_HOSTS=immigration97.com,www.immigration97.com
DATABASE_URL=postgresql://immigration97_user:immigration97StrongPass2026@localhost:5432/immigration97_db
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
EOF

# Migrations et collectstatic
python manage.py migrate
python manage.py collectstatic --noinput --clear

# Créer superuser (optionnel)
# python manage.py createsuperuser

exit  # Revenir à ubuntu
```

---

## 5. Configurer Gunicorn (sur le serveur, en tant qu'ubuntu)

```bash
# Créer fichier de service systemd
sudo tee /etc/systemd/system/immigration97.service > /dev/null << 'EOF'
[Unit]
Description=Gunicorn for immigration97
After=network.target postgresql.service

[Service]
Type=notify
User=deployer
Group=www-data
WorkingDirectory=/home/deployer/projects/immigration97
EnvironmentFile=/home/deployer/projects/immigration97/.env
ExecStart=/home/deployer/projects/immigration97/.venv/bin/gunicorn \
    --access-logfile - \
    --workers 3 \
    --bind unix:/run/immigration97.sock \
    --timeout 30 \
    core.wsgi:application

Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

# Activer et démarrer
sudo systemctl daemon-reload
sudo systemctl enable --now immigration97
sudo systemctl status immigration97
```

---

## 6. Configurer Nginx (sur le serveur)

```bash
# Créer config site
sudo tee /etc/nginx/sites-available/immigration97 > /dev/null << 'EOF'
server {
    listen 80;
    server_name immigration97.com www.immigration97.com;

    location = /favicon.ico { 
        access_log off; 
        log_not_found off; 
    }

    location /static/ {
        alias /home/deployer/projects/immigration97/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /home/deployer/projects/immigration97/media/;
        expires 7d;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/immigration97.sock;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF

# Activer site
sudo ln -sf /etc/nginx/sites-available/immigration97 /etc/nginx/sites-enabled/

# Tester et redémarrer
sudo nginx -t
sudo systemctl restart nginx
```

---

## 7. Configurer SSL avec Certbot

```bash
# Obtenir certificat (interactive)
sudo certbot --nginx -d immigration97.com -d www.immigration97.com

# Vérifier renouvellement auto
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

---

## 8. Vérifications finales

```bash
# Tester le site
curl -I https://immigration97.com

# Voir les logs de l'appli
sudo journalctl -u immigration97 -f

# Voir les logs Nginx
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Status des services
sudo systemctl status nginx
sudo systemctl status immigration97
sudo systemctl status postgresql
```

---

## 9. Workflow de déploiement (local → AWS)

### En local :
```bash
git status
git add .
git commit -m "maj: description"
git push origin main
```

### Sur le serveur :
```bash
ssh -i "$env:USERPROFILE\.ssh\eshelle-prod-key.pem" ubuntu@<IP>
sudo su - deployer
cd ~/projects/immigration97
git pull origin main
source .venv/bin/activate

# Complet (avec dépendances + migrations)
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput --clear
sudo systemctl restart immigration97

# Rapide (HTML/CSS/Python seulement)
# python manage.py collectstatic --noinput --clear
# sudo systemctl restart immigration97
```

### Vérifier :
```bash
sudo systemctl status immigration97
curl -I https://immigration97.com
sudo journalctl -u immigration97 -n 50 --no-pager
```

---

## 10. Mise à jour DNS (Hostinger)

1. Allez sur https://hpanel.hostinger.com/
2. **Domains > immigration97.com > DNS / Nameservers**
3. Modifier l'enregistrement **A** existant :
   - **Name**: `www` ou `@`
   - **Type**: A
   - **Value**: `<IP-PUBLIQUE-EC2>`
   - **TTL**: 3600
4. Sauvegarder

Attendre 5-15 min pour que le DNS se propage.

---

## Troubleshooting

| Problème | Solution |
|----------|----------|
| **502 Bad Gateway** | `sudo systemctl status immigration97` → voir les logs ; `curl http://unix:/run/immigration97.sock` |
| **Connection refused** | Vérifier Security Group (port 80/443 ouvert) ; `sudo systemctl restart nginx` |
| **Permission denied** | Vérifier propriété fichiers : `sudo chown -R deployer:deployer ~/projects/immigration97` |
| **Database error** | `sudo -u postgres psql immigration97_db` → `\dt` pour voir les tables |
| **SSL certificate error** | `sudo certbot renew --force-renewal` ; `sudo nginx -t` |

