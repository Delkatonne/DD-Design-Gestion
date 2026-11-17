from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nom_complet = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default="vendeur")  # admin / vendeur
    actif = db.Column(db.Boolean, default=True)
    ventes = db.relationship("Vente", backref="vendeur", lazy=True)

class Categorie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), unique=True, nullable=False)
    type_boutique = db.Column(db.String(20), default="friperie")  # friperie / pret_a_porter
    articles = db.relationship("Article", backref="categorie", lazy=True)

class Fournisseur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(20))
    type_fournisseur = db.Column(db.String(20), default="friperie")  # friperie / pret_a_porter
    articles = db.relationship("Article", backref="fournisseur", lazy=True)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    nom = db.Column(db.String(120), nullable=False)
    categorie_id = db.Column(db.Integer, db.ForeignKey("categorie.id"), nullable=False)
    fournisseur_id = db.Column(db.Integer, db.ForeignKey("fournisseur.id"))
    taille = db.Column(db.String(10))
    couleur = db.Column(db.String(30))
    etat = db.Column(db.String(20), default="occasion")  # neuf / semi_neuf / occasion
    prix_achat = db.Column(db.Float, default=0)
    prix_vente = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    photo = db.Column(db.String(255))
    seuil_alerte = db.Column(db.Integer, default=5)
    actif = db.Column(db.Boolean, default=True)
    lignes = db.relationship("LigneVente", backref="article", lazy=True)

    @property
    def marge(self):
        return self.prix_vente - self.prix_achat

class MouvementStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("article.id"), nullable=False)
    type_mouvement = db.Column(db.String(10), nullable=False)  # entree / sortie
    quantite = db.Column(db.Integer, nullable=False)
    prix_unitaire = db.Column(db.Float, default=0)  # utile pour achat au poids/pièce
    date = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.String(255))
    article = db.relationship("Article", backref="mouvements")

class Vente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    mode_paiement = db.Column(db.String(20), default="especes")  # especes / wave / orange_money / carte
    montant_total = db.Column(db.Float, nullable=False)
    montant_recu = db.Column(db.Float, default=0)
    monnaie_rendue = db.Column(db.Float, default=0)
    lignes = db.relationship("LigneVente", backref="vente", lazy=True,
                             cascade="all, delete-orphan")

    @property
    def nb_articles(self):
        return sum(l.quantite for l in self.lignes)

class LigneVente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vente_id = db.Column(db.Integer, db.ForeignKey("vente.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("article.id"), nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    prix_unitaire = db.Column(db.Float, nullable=False)
