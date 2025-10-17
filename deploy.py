#!/usr/bin/env python3
"""
ProofOrigin - Deployment Script
Script de déploiement et configuration pour la production
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path

class ProofOriginDeployer:
    """Déployeur pour ProofOrigin"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.config = self.load_config()
    
    def load_config(self):
        """Charge la configuration de déploiement"""
        config_file = self.project_root / "deploy_config.json"
        
        default_config = {
            "environment": "production",
            "host": "0.0.0.0",
            "port": 5000,
            "debug": False,
            "database_url": "sqlite:///instance/ledger.db",
            "blockchain": {
                "rpc_url": "https://polygon-rpc.com",
                "private_key": None,
                "enabled": False
            },
            "fuzzy_matching": {
                "enabled": True,
                "image_threshold": 0.8,
                "text_threshold": 0.7
            },
            "security": {
                "https": True,
                "cors": True,
                "rate_limit": 1000
            }
        }
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def check_dependencies(self):
        """Vérifie que toutes les dépendances sont installées"""
        print("🔍 Vérification des dépendances...")
        
        required_packages = [
            'flask',
            'cryptography',
            'web3',
            'eth-account',
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
                print(f"  ✅ {package}")
            except ImportError:
                missing_packages.append(package)
                print(f"  ❌ {package}")
        
        if missing_packages:
            print(f"\n📦 Installation des packages manquants...")
            for package in missing_packages:
                subprocess.run([sys.executable, '-m', 'pip', 'install', package])
        
        print("✅ Toutes les dépendances sont installées")
    
    def setup_environment(self):
        """Configure l'environnement de production"""
        print("⚙️ Configuration de l'environnement...")
        
        # Variables d'environnement
        env_vars = {
            'FLASK_ENV': 'production',
            'FLASK_DEBUG': 'False',
            'PROOFORIGIN_ENV': self.config['environment'],
            'PROOFORIGIN_DATABASE': str(self.project_root / 'instance' / 'ledger.db'),
            'PROOFORIGIN_KEYS': str(self.project_root / 'keys'),
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
            print(f"  {key}={value}")
        
        # Créer les dossiers nécessaires
        directories = ['instance', 'instance/tmp', 'instance/exports', 'keys']
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"  📁 Créé: {directory}/")
    
    def generate_keys(self):
        """Génère les clés cryptographiques si elles n'existent pas"""
        print("🔑 Vérification des clés cryptographiques...")
        
        private_key_path = self.project_root / "keys" / "private.pem"
        public_key_path = self.project_root / "keys" / "public.pem"

        if not private_key_path.exists() or not public_key_path.exists():
            print("  🔧 Génération des nouvelles clés...")
            subprocess.run([sys.executable, "scripts/generate_keys.py"], check=True)
            print("  ✅ Clés générées")
        else:
            print("  ✅ Clés existantes trouvées")

    def initialize_database(self):
        """Initialise la base de données"""
        print("🗄️ Initialisation de la base de données...")

        sys.path.append(str(self.project_root))
        from prooforigin.config import ProofOriginConfig
        from prooforigin.database import init_db

        config = ProofOriginConfig()
        init_db(config.database)
        print("  ✅ Base de données initialisée")
    
    def setup_ssl(self):
        """Configure SSL/TLS pour HTTPS"""
        if not self.config['security']['https']:
            print("🔒 HTTPS désactivé")
            return
        
        print("🔒 Configuration SSL...")
        
        # Vérifier si les certificats existent
        cert_path = self.project_root / "cert.pem"
        key_path = self.project_root / "key.pem"
        
        if not cert_path.exists() or not key_path.exists():
            print("  ⚠️ Certificats SSL non trouvés")
            print("  💡 Pour la production, utilisez Let's Encrypt ou un certificat valide")
            print("  💡 Pour les tests, vous pouvez générer des certificats auto-signés:")
            print("     openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes")
        else:
            print("  ✅ Certificats SSL trouvés")
    
    def setup_cron_jobs(self):
        """Configure les tâches cron pour l'ancrage blockchain"""
        print("⏰ Configuration des tâches cron...")
        
        cron_script = self.project_root / "cron_anchor.py"
        
        # Créer le script cron
        cron_content = f'''#!/usr/bin/env python3
"""
Script cron pour l'ancrage quotidien
"""

import sys
import os
sys.path.append('{self.project_root}')

from prooforigin.services.blockchain import run_daily_anchoring

if __name__ == "__main__":
    run_daily_anchoring(
        rpc_url="{self.config['blockchain']['rpc_url']}",
        private_key="{self.config['blockchain']['private_key']}",
        db_file=os.path.join('{self.project_root}', 'instance', 'ledger.db')
    )
'''
        
        with open(cron_script, 'w') as f:
            f.write(cron_content)
        
        # Rendre exécutable
        os.chmod(cron_script, 0o755)
        
        print("  📝 Script cron créé: cron_anchor.py")
        print("  💡 Ajoutez cette ligne à votre crontab pour l'ancrage quotidien:")
        print("     0 2 * * * cd /path/to/prooforigin && python cron_anchor.py")
    
    def create_systemd_service(self):
        """Crée un service systemd pour la production"""
        print("🔧 Création du service systemd...")
        
        service_content = f'''[Unit]
Description=ProofOrigin API Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory={self.project_root}
Environment=PATH={self.project_root}/venv/bin
ExecStart={self.project_root}/venv/bin/python -m prooforigin
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
'''
        
        service_file = Path("/etc/systemd/system/prooforigin.service")
        
        if os.geteuid() == 0:  # Root user
            with open(service_file, 'w') as f:
                f.write(service_content)
            print("  ✅ Service systemd créé")
            print("  💡 Pour activer: systemctl enable prooforigin && systemctl start prooforigin")
        else:
            print("  ⚠️ Exécution en tant que root requise pour créer le service systemd")
            print(f"  📝 Contenu du service à sauvegarder dans /etc/systemd/system/prooforigin.service:")
            print(service_content)
    
    def run_health_check(self):
        """Effectue une vérification de santé du système"""
        print("🏥 Vérification de santé du système...")
        
        checks = [
            ("Base de données", self.check_database),
            ("Clés cryptographiques", self.check_crypto_keys),
            ("Dépendances", self.check_dependencies),
            ("Permissions", self.check_permissions)
        ]
        
        for check_name, check_func in checks:
            try:
                check_func()
                print(f"  ✅ {check_name}")
            except Exception as e:
                print(f"  ❌ {check_name}: {e}")
    
    def check_database(self):
        """Vérifie la base de données"""
        import sqlite3
        conn = sqlite3.connect(self.project_root / "instance" / "ledger.db")
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = c.fetchall()
        conn.close()
        
        required_tables = ['proofs', 'anchors', 'similarities']
        for table in required_tables:
            if (table,) not in tables:
                raise Exception(f"Table manquante: {table}")
    
    def check_crypto_keys(self):
        """Vérifie les clés cryptographiques"""
        private_key = self.project_root / "keys" / "private.pem"
        public_key = self.project_root / "keys" / "public.pem"
        
        if not private_key.exists() or not public_key.exists():
            raise Exception("Clés cryptographiques manquantes")
    
    def check_permissions(self):
        """Vérifie les permissions des fichiers"""
        important_files = ['app.py', 'keys/private.pem', 'keys/public.pem']

        for file_path in important_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                raise Exception(f"Fichier manquant: {file_path}")

            # Vérifier que private.pem n'est pas lisible par tous
            if file_path == 'keys/private.pem':
                stat = full_path.stat()
                if stat.st_mode & 0o077:
                    raise Exception("Clé privée accessible par d'autres utilisateurs")
    
    def deploy(self):
        """Lance le déploiement complet"""
        print("🚀 Déploiement de ProofOrigin")
        print("=" * 40)
        
        steps = [
            ("Vérification des dépendances", self.check_dependencies),
            ("Configuration de l'environnement", self.setup_environment),
            ("Génération des clés", self.generate_keys),
            ("Initialisation de la base de données", self.initialize_database),
            ("Configuration SSL", self.setup_ssl),
            ("Configuration des tâches cron", self.setup_cron_jobs),
            ("Création du service systemd", self.create_systemd_service),
            ("Vérification de santé", self.run_health_check)
        ]
        
        for step_name, step_func in steps:
            print(f"\n📋 {step_name}...")
            try:
                step_func()
            except Exception as e:
                print(f"❌ Erreur: {e}")
                return False
        
        print("\n🎉 Déploiement terminé avec succès!")
        print("\n📝 Prochaines étapes:")
        print("  1. Configurez votre reverse proxy (nginx/apache)")
        print("  2. Activez HTTPS avec Let's Encrypt")
        print("  3. Configurez les tâches cron pour l'ancrage")
        print("  4. Testez l'API: curl http://localhost:5000/api/proofs")
        
        return True

def main():
    """Fonction principale"""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python deploy.py [--config config.json]")
        print("\nOptions:")
        print("  --config    Fichier de configuration personnalisé")
        print("  --help      Affiche cette aide")
        return
    
    deployer = ProofOriginDeployer()
    success = deployer.deploy()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
