# DD Design — Gestion Boutique (Friperie & Prêt-à-porter)

Système complet de gestion de boutique (Flask + SQLite + Bootstrap 5).

## Installation

```bash
pip install -r requirements.txt
python app.py
```

Ouvrir http://127.0.0.1:5000

## Connexion par défaut
- **Utilisateur :** `admin`
- **Mot de passe :** `admin123`

⚠️ Changez ce mot de passe en production (créez un nouvel admin puis désactivez le compte par défaut).

## Fonctionnalités
- 📊 Tableau de bord (CA jour/mois, graphiques Chart.js, alertes stock bas)
- 🏷️ Gestion des articles (référence, catégorie, taille, état, photo, prix, marge)
- 🛒 Caisse / POS (panier, paiement espèces/Wave/Orange Money/carte, monnaie rendue)
- 🧾 Tickets de vente imprimables
- 📦 Stock (entrées, sorties, mouvements, seuils d'alerte)
- 🚚 Fournisseurs (friperie / prêt-à-porter)
- 👥 Utilisateurs avec rôles (admin / vendeur)

## Structure
```
app.py            → routes et logique
models.py         → modèles SQLAlchemy
config.py         → configuration
templates/        → pages (Jinja2)
static/           → CSS, JS, photos uploadées
```

## Production
- Changez `SECRET_KEY` dans `config.py`
- Utilisez un vrai serveur : `gunicorn -w 4 "app:app"`
- Migrez vers MySQL/PostgreSQL si besoin

## Déploiement Vercel

Ce projet est en **Flask (server-side)**. Vercel ne sert pas les apps Flask
classiques : il faut un point d'entrée serverless (`api/index.py` + `vercel.json`,
déjà inclus).

1. Pousser le repo sur GitHub
2. Sur vercel.com : **Add New Project** → importer le repo
3. Vercel détecte Python automatiquement (pas de build command nécessaire)

⚠️ **Attention à la base de données** : SQLite écrit dans un fichier local qui
est **éphémère** sur Vercel (réinitialisé à chaque déploiement). Pour la
production, utilise **Neon/Supabase (PostgreSQL gratuit)** et remplace
l'URI dans `config.py`.

## Déploiement alternatif (plus simple pour Flask)

Si tu veux éviter les contraintes serverless : **Render.com** ou **Railway**
(tiers gratuits) exécutent Flask nativement :

- Build command : `pip install -r requirements.txt`
- Start command : `python app.py`
- SQLite persiste normalement
