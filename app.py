import os, json
from datetime import datetime, date
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, abort)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from config import Config
from models import db, User, Categorie, Fournisseur, Article, MouvementStock, Vente, LigneVente

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Accès réservé à l'administrateur.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper

def devise():
    return app.config["DEVISE"]

# ============================================================
# AUTH
# ============================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        u = User.query.filter_by(username=request.form["username"]).first()
        if u and u.actif and check_password_hash(u.password_hash, request.form["password"]):
            login_user(u)
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Identifiants invalides ou compte désactivé.", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ============================================================
# TABLEAU DE BORD
# ============================================================
@app.route("/")
@login_required
def dashboard():
    today = date.today()
    ventes_jour = Vente.query.filter(db.func.date(Vente.date) == today).all()
    ca_jour = sum(v.montant_total for v in ventes_jour)
    premier = today.replace(day=1)
    ventes_mois = Vente.query.filter(Vente.date >= premier).all()
    ca_mois = sum(v.montant_total for v in ventes_mois)
    nb_articles = Article.query.filter_by(actif=True).count()
    stock_total = db.session.query(db.func.sum(Article.stock)).filter_by(actif=True).scalar() or 0
    stock_bas = Article.query.filter(Article.actif == True, Article.stock <= Article.seuil_alerte).all()
    alertes_stock_bas = sum(1 for a in Article.query.filter_by(actif=True) if a.stock <= a.seuil_alerte)
    dernieres_ventes = Vente.query.order_by(Vente.date.desc()).limit(8).all()
    return render_template("dashboard.html", ca_jour=ca_jour, ca_mois=ca_mois,
                           nb_articles=nb_articles, stock_total=stock_total,
                           stock_bas=stock_bas, alertes=alertes_stock_bas,
                           dernieres_ventes=dernieres_ventes, devise=devise())

@app.route("/stats/api")
@login_required
def stats_api():
    # CA des 14 derniers jours
    labels, ca = [], []
    for i in range(13, -1, -1):
        d = date.today().fromordinal(date.today().toordinal() - i)
        total = db.session.query(db.func.sum(Vente.montant_total))\
            .filter(db.func.date(Vente.date) == d).scalar() or 0
        labels.append(d.strftime("%d/%m"))
        ca.append(round(total, 0))
    # Top 5 articles
    top = db.session.query(Article.nom, db.func.sum(LigneVente.quantite).label("qte"))\
        .join(LigneVente).group_by(Article.id).order_by(db.desc("qte")).limit(5).all()
    return jsonify({"labels": labels, "ca": ca,
                    "top_labels": [t[0] for t in top], "top_qte": [t[1] for t in top]})

# ============================================================
# ARTICLES
# ============================================================
def save_photo(f):
    if f and f.filename:
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext in ALLOWED_EXT:
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{f.filename}")
            f.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            return filename
    return None

@app.route("/articles")
@login_required
def articles_list():
    q = request.args.get("q", "").strip()
    cat = request.args.get("cat", type=int)
    query = Article.query.filter_by(actif=True)
    if q:
        query = query.filter(db.or_(Article.nom.ilike(f"%{q}%"),
                                    Article.reference.ilike(f"%{q}%")))
    if cat:
        query = query.filter_by(categorie_id=cat)
    articles = query.order_by(Article.nom).all()
    categories = Categorie.query.order_by(Categorie.nom).all()
    return render_template("articles/list.html", articles=articles,
                           categories=categories, q=q, cat=cat or 0, devise=devise())

@app.route("/articles/nouveau", methods=["GET", "POST"])
@login_required
def article_new():
    if request.method == "POST":
        f = request.form
        ref = f["reference"].strip()
        if Article.query.filter_by(reference=ref).first():
            flash("Cette référence existe déjà.", "danger")
        else:
            a = Article(
                reference=ref, nom=f["nom"].strip(),
                categorie_id=f["categorie_id"], fournisseur_id=f.get("fournisseur_id") or None,
                taille=f.get("taille"), couleur=f.get("couleur"), etat=f.get("etat", "occasion"),
                prix_achat=float(f.get("prix_achat") or 0),
                prix_vente=float(f["prix_vente"]),
                stock=int(f.get("stock") or 0),
                seuil_alerte=int(f.get("seuil_alerte") or 5),
                photo=save_photo(request.files.get("photo")),
            )
            db.session.add(a)
            if a.stock > 0:
                db.session.add(MouvementStock(article=a, type_mouvement="entree",
                                              quantite=a.stock, prix_unitaire=a.prix_achat,
                                              note="Stock initial"))
            db.session.commit()
            flash("Article créé avec succès.", "success")
            return redirect(url_for("articles_list"))
    return render_template("articles/form.html", article=None,
                           categories=Categorie.query.order_by(Categorie.nom).all(),
                           fournisseurs=Fournisseur.query.order_by(Fournisseur.nom).all())

@app.route("/articles/<int:aid>/edit", methods=["GET", "POST"])
@login_required
def article_edit(aid):
    a = Article.query.get_or_404(aid)
    if request.method == "POST":
        f = request.form
        a.nom = f["nom"].strip()
        a.categorie_id = f["categorie_id"]
        a.fournisseur_id = f.get("fournisseur_id") or None
        a.taille = f.get("taille"); a.couleur = f.get("couleur")
        a.etat = f.get("etat", "occasion")
        a.prix_achat = float(f.get("prix_achat") or 0)
        a.prix_vente = float(f["prix_vente"])
        a.seuil_alerte = int(f.get("seuil_alerte") or 5)
        photo = save_photo(request.files.get("photo"))
        if photo:
            a.photo = photo
        db.session.commit()
        flash("Article modifié.", "success")
        return redirect(url_for("articles_list"))
    return render_template("articles/form.html", article=a,
                           categories=Categorie.query.order_by(Categorie.nom).all(),
                           fournisseurs=Fournisseur.query.order_by(Fournisseur.nom).all())

@app.route("/articles/<int:aid>/supprimer", methods=["POST"])
@login_required
@admin_required
def article_delete(aid):
    a = Article.query.get_or_404(aid)
    a.actif = False  # suppression douce pour préserver l'historique des ventes
    db.session.commit()
    flash("Article désactivé.", "success")
    return redirect(url_for("articles_list"))

# ============================================================
# VENTES (CAISSE)
# ============================================================
@app.route("/ventes/nouvelle")
@login_required
def vente_nouvelle():
    articles = Article.query.filter_by(actif=True, ).order_by(Article.nom).all()
    articles_json = [{"id": a.id, "nom": a.nom, "reference": a.reference,
                      "prix": a.prix_vente, "stock": a.stock,
                      "taille": a.taille or "", "photo": a.photo} for a in articles]
    return render_template("ventes/pos.html", articles=articles, devise=devise(),
                           articles_json=json.dumps(articles_json))

@app.route("/ventes/api/creer", methods=["POST"])
@login_required
def vente_creer():
    data = request.get_json(force=True)
    lignes_data = data.get("lignes", [])
    if not lignes_data:
        return jsonify({"ok": False, "erreur": "Le panier est vide."}), 400
    v = Vente(user_id=current_user.id, mode_paiement=data.get("mode_paiement", "especes"),
              montant_recu=float(data.get("montant_recu") or 0))
    total = 0
    try:
        for ld in lignes_data:
            a = db.session.get(Article, int(ld["article_id"]))
            qte = int(ld["quantite"])
            if not a or not a.actif:
                return jsonify({"ok": False, "erreur": "Article introuvable."}), 400
            if a.stock < qte:
                return jsonify({"ok": False, "erreur": f"Stock insuffisant pour {a.nom} (reste {a.stock})."}), 400
            total += a.prix_vente * qte
            a.stock -= qte
            db.session.add(LigneVente(vente=v, article=a, quantite=qte, prix_unitaire=a.prix_vente))
            db.session.add(MouvementStock(article=a, type_mouvement="sortie",
                                          quantite=qte, prix_unitaire=a.prix_vente,
                                          note=f"Vente #{v.id or ''}"))
        v.montant_total = total
        v.monnaie_rendue = max(0, v.montant_recu - total)
        db.session.add(v)
        db.session.commit()
        return jsonify({"ok": True, "vente_id": v.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "erreur": str(e)}), 500

@app.route("/ventes")
@login_required
def ventes_list():
    page = request.args.get("page", 1, type=int)
    pagination = Vente.query.order_by(Vente.date.desc()).paginate(page=page, per_page=15)
    return render_template("ventes/list.html", pagination=pagination, devise=devise())

@app.route("/ventes/<int:vid>")
@login_required
def vente_detail(vid):
    v = Vente.query.get_or_404(vid)
    return render_template("ventes/ticket.html", v=v, devise=devise())

# ============================================================
# STOCK
# ============================================================
@app.route("/stock")
@login_required
def stock_list():
    articles = Article.query.filter_by(actif=True).order_by(Article.nom).all()
    return render_template("stock/list.html", articles=articles, devise=devise())

@app.route("/stock/entree", methods=["GET", "POST"])
@login_required
def stock_entree():
    if request.method == "POST":
        f = request.form
        a = db.session.get(Article, int(f["article_id"]))
        qte = int(f["quantite"])
        if a and qte > 0:
            prix = float(f.get("prix_unitaire") or a.prix_achat)
            a.stock += qte
            if prix > 0:
                a.prix_achat = prix
            db.session.add(MouvementStock(article=a, type_mouvement="entree",
                                          quantite=qte, prix_unitaire=prix,
                                          note=f.get("note")))
            db.session.commit()
            flash(f"Entrée de stock enregistrée : +{qte} × {a.nom}", "success")
            return redirect(url_for("stock_list"))
    articles = Article.query.filter_by(actif=True).order_by(Article.nom).all()
    mouvements = MouvementStock.query.order_by(MouvementStock.date.desc()).limit(30).all()
    return render_template("stock/entree.html", articles=articles,
                           mouvements=mouvements, devise=devise())

@app.route("/stock/sortie", methods=["GET", "POST"])
@login_required
@admin_required
def stock_sortie():
    if request.method == "POST":
        f = request.form
        a = db.session.get(Article, int(f["article_id"]))
        qte = int(f["quantite"])
        if a and 0 < qte <= a.stock:
            a.stock -= qte
            db.session.add(MouvementStock(article=a, type_mouvement="sortie",
                                          quantite=qte, note=f.get("note") or "Sortie manuelle"))
            db.session.commit()
            flash(f"Sortie de stock enregistrée : -{qte} × {a.nom}", "success")
            return redirect(url_for("stock_list"))
        flash("Quantité invalide (stock insuffisant).", "danger")
    articles = Article.query.filter_by(actif=True).order_by(Article.nom).all()
    return render_template("stock/sortie.html", articles=articles)

# ============================================================
# FOURNISSEURS & CATEGORIES
# ============================================================
@app.route("/fournisseurs")
@login_required
def fournisseurs_list():
    return render_template("fournisseurs/list.html",
                           fournisseurs=Fournisseur.query.order_by(Fournisseur.nom).all())

@app.route("/fournisseurs/nouveau", methods=["GET", "POST"])
@login_required
def fournisseur_new():
    if request.method == "POST":
        f = request.form
        db.session.add(Fournisseur(nom=f["nom"].strip(), telephone=f.get("telephone"),
                                   type_fournisseur=f.get("type_fournisseur", "friperie")))
        db.session.commit()
        flash("Fournisseur ajouté.", "success")
        return redirect(url_for("fournisseurs_list"))
    return render_template("fournisseurs/form.html", fournisseur=None)

@app.route("/fournisseurs/<int:fid>/edit", methods=["GET", "POST"])
@login_required
def fournisseur_edit(fid):
    fr = Fournisseur.query.get_or_404(fid)
    if request.method == "POST":
        f = request.form
        fr.nom = f["nom"].strip()
        fr.telephone = f.get("telephone")
        fr.type_fournisseur = f.get("type_fournisseur", "friperie")
        db.session.commit()
        flash("Fournisseur modifié.", "success")
        return redirect(url_for("fournisseurs_list"))
    return render_template("fournisseurs/form.html", fournisseur=fr)

@app.route("/fournisseurs/<int:fid>/supprimer", methods=["POST"])
@login_required
@admin_required
def fournisseur_delete(fid):
    fr = Fournisseur.query.get_or_404(fid)
    if fr.articles:
        flash("Impossible : des articles sont liés à ce fournisseur.", "danger")
    else:
        db.session.delete(fr)
        db.session.commit()
        flash("Fournisseur supprimé.", "success")
    return redirect(url_for("fournisseurs_list"))

# ============================================================
# UTILISATEURS (admin)
# ============================================================
@app.route("/utilisateurs")
@login_required
@admin_required
def users_list():
    return render_template("utilisateurs/list.html", users=User.query.all())

@app.route("/utilisateurs/nouveau", methods=["GET", "POST"])
@login_required
@admin_required
def user_new():
    if request.method == "POST":
        f = request.form
        if User.query.filter_by(username=f["username"]).first():
            flash("Ce nom d'utilisateur existe déjà.", "danger")
        else:
            db.session.add(User(username=f["username"].strip(),
                                password_hash=generate_password_hash(f["password"]),
                                nom_complet=f["nom_complet"].strip(),
                                role=f.get("role", "vendeur")))
            db.session.commit()
            flash("Utilisateur créé.", "success")
            return redirect(url_for("users_list"))
    return render_template("utilisateurs/form.html", user=None)

@app.route("/utilisateurs/<int:uid>/toggle", methods=["POST"])
@login_required
@admin_required
def user_toggle(uid):
    u = User.query.get_or_404(uid)
    if u.id == current_user.id:
        flash("Vous ne pouvez pas désactiver votre propre compte.", "danger")
    else:
        u.actif = not u.actif
        db.session.commit()
        flash(f"Compte {'activé' if u.actif else 'désactivé'}.", "success")
    return redirect(url_for("users_list"))

# ============================================================
# INITIALISATION
# ============================================================
def init_db():
    db.create_all()
    if not User.query.first():
        db.session.add(User(username="admin",
                            password_hash=generate_password_hash("admin123"),
                            nom_complet="Administrateur", role="admin"))
        for nom, typ in [("Hauts friperie", "friperie"), ("Pantalons friperie", "friperie"),
                         ("Chaussures friperie", "friperie"), ("Robes", "pret_a_porter"),
                         ("Ensembles", "pret_a_porter")]:
            db.session.add(Categorie(nom=nom, type_boutique=typ))
        db.session.commit()

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
