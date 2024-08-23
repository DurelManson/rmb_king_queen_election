import os
from flask import Flask, render_template, request, redirect, jsonify, request, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'rmb.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SESSION_TYPE'] = 'filesystem'

db = SQLAlchemy(app)
Session(app)

ADMIN_PASSWORD = 'admin123'

# Modèle pour les utilisateurs
class Utilisateur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(80), nullable=False)
    numero_telephone = db.Column(db.String(20), unique=True, nullable=False)

# Modèle pour les candidats
class Candidat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(80), nullable=False)
    nombre_de_votes = db.Column(db.Integer, default=0)

# Modèle pour les Reines
class Reine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidat_id = db.Column(db.Integer, db.ForeignKey('candidat.id'), nullable=False)
    nom = db.Column(db.String(80), nullable=False)
    nombre_de_votes = db.Column(db.Integer, default=0)

    candidat = db.relationship('Candidat', backref=db.backref('reine', uselist=False))

# Modèle pour les Rois
class Roi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidat_id = db.Column(db.Integer, db.ForeignKey('candidat.id'), nullable=False)
    nom = db.Column(db.String(80), nullable=False)
    nombre_de_votes = db.Column(db.Integer, default=0)

    candidat = db.relationship('Candidat', backref=db.backref('roi', uselist=False))

# Limiter le nombre de vote par utilisateur
class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    candidat_id = db.Column(db.Integer, db.ForeignKey('candidat.id'), nullable=False)

    utilisateur = db.relationship('Utilisateur', backref=db.backref('votes', lazy=True))
    candidat = db.relationship('Candidat', backref=db.backref('votes', lazy=True))

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/vote/queen')
def vote_queen():
    queens = Reine.query.all()
    return render_template('rmb_queen.html', queens = queens)

@app.route('/vote/king')
def vote_king():
    kings = Roi.query.all()
    return render_template('rmb_king.html', kings = kings)

@app.route('/vote', methods=['POST'])
def vote():
    utilisateur_nom = request.form['utilisateur_nom']
    utilisateur_telephone = request.form['utilisateur_telephone']
    candidat_nom = request.form['candidat_nom']

    # Verifier et initialiser les votes si ce n'est pas fait
    if 'voted_king' not in session or 'voted_queen' not in session:
        session['voted_king'] = 0
        session['voted_queen'] = 0

    if 'votes_king' not in session or 'votes_queen' not in session:
        session['votes_king'] = 0
        session['votes_queen'] = 0

    # Verifier si l'utilisateur existe
    utilisateur = Utilisateur.query.filter_by(numero_telephone=utilisateur_telephone).first()
    if not utilisateur:
        utilisateur = Utilisateur(nom = utilisateur_nom, numero_telephone = utilisateur_telephone)
        db.session.add(utilisateur)
        db.session.commit()

    # Verifier si le candidat existe
    candidat = Candidat.query.filter_by(nom=candidat_nom).first()
    if not candidat:
        return jsonify({'message': 'Candidat non trouve'}), 404

    
    # Limiter les votes par session
    if candidat.roi and session['voted_king'] and session['voted_king']:
        return jsonify({'message': 'Vous avez deja vote pour un roi dans cette session'}), 403
    if candidat.reine and session['voted_queen'] and session['voted_queen']:
        return jsonify({'message': 'Vous avez deja vote pour une reine dans cette session'}), 403

    # Creer et ajouter le nouveau vote
    nouveau_vote = Vote(utilisateur_id=utilisateur.id, candidat_id=candidat.id)

    db.session.add(nouveau_vote)

    # Mettre a jour le nombre de votes si le candidat est une reine ou un roi
    candidat.nombre_de_votes += 1
    if candidat.reine:
        candidat.reine.nombre_de_votes = candidat.nombre_de_votes
        # Marquer la session comme ayant vote
        session['voted_queen'] = True
        session['votes_queen'] += 1 # incrementer le compteur de votes
    if candidat.roi:
        candidat.roi.nombre_de_votes = candidat.nombre_de_votes
        # Marquer la session comme ayant vote
        session['voted_king'] = True
        session['votes_king'] += 1 # incrementer le compteur de votes

    db.session.commit()

    return redirect(url_for('results'))

@app.route('/resutls')
def results():
    candidats = Candidat.query.all()
    return render_template('results.html', candidats=candidats)

@app.route('/api/results', methods=['GET'])
def api_results():
    candidats = Candidat.query.all()
    results = {candidat.nom: candidat.nombre_de_votes for candidat in candidats}
    return jsonify(results)

# Gestion de l'administration
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.methods == 'POST':
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Mot de passe incorrect')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    candidats = Candidat.query.all()
    utilisateurs = Utilisateur.query.all()
    return render_template('admin_dashboard.html', candidats=candidats, utilisateurs=utilisateurs)

@app.route('/admin/add_candidat', methods=['POST'])
def add_candidat():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    nom = request.form['nom']
    nouveau_candidat = Candidat(nom=nom)
    db.session.add(nouveau_candidat)
    db.session.commit()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_candidat/<int:id>')
def delete_candidat(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    candidat = Candidat.query.get(id)
    if candidat:
        db.session.delete(candidat)
        db.session.commit()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

if __name__ == "__main__":
    app.run(debug=True)
