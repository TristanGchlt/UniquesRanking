from flask_login import UserMixin
from sqlalchemy import Enum as sqlalchemy_enum
from werkzeug.security import generate_password_hash, check_password_hash

import enum
import os
import binascii

from app import db

# Entre membre et cards (cartes favorites d'un membre ou membres qui ont la carte en favorite)
favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"), primary_key=True),
    db.Column('card_id', db.Integer, db.ForeignKey('card.id', ondelete="CASCADE"), primary_key=True)
)

# DECLARATIONS DE VARIABLE ENUMEREES
# Résultats possibles pour un duel
class DuelResult(enum.Enum) :
    not_played = 0
    draw = 1
    card_a_win = 2
    card_b_win = 3

# TABLES
# Carte : 
class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reference = db.Column(db.String(32), nullable=False, index=True)
    faction = db.Column(db.String(16), nullable=False)
    num = db.Column(db.Integer, nullable=False)
    nb_duel = db.Column(db.Integer, default=0)
    elo = db.Column(db.Float, default=1000)
    character_en_us = db.Column(db.String(64), nullable=False)
    url_en_us = db.Column(db.String(256), nullable=False)
    character_fr_fr = db.Column(db.String(64), nullable=True)
    url_fr_fr = db.Column(db.String(256), nullable=True)
    character_it_it = db.Column(db.String(64), nullable=True)
    url_it_it = db.Column(db.String(256), nullable=True)
    character_es_es = db.Column(db.String(64), nullable=True)
    url_es_es = db.Column(db.String(256), nullable=True)
    character_de_de = db.Column(db.String(64), nullable=True)
    url_de_de = db.Column(db.String(256), nullable=True)
    url_art = db.Column(db.String(256), nullable=True)
    hide = db.Column(db.Integer, default=0)

# Utilisateurs :
class User(db.Model, UserMixin) :
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(32), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=True)
    remember_token = db.Column(db.String(120), unique=True, nullable=True)
    admin = db.Column(db.Integer, default=0)
    def set_password(self, password):
        self.password = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password, password)
    def generate_remember_token(self):
        token = binascii.hexlify(os.urandom(24)).decode()
        self.remember_token = token
        db.session.commit()
        return token
    def verify_remember_token(token) :
        return User.query.filter_by(remember_token=token).first()
    created = db.Column(db.DateTime, default=db.func.now())
    duel_fact_id = db.Column(db.Integer, db.ForeignKey('duel.id'), nullable=True)
    duel_rand_id = db.Column(db.Integer, db.ForeignKey('duel.id'), nullable=True)
    duel_char_id = db.Column(db.Integer, db.ForeignKey('duel.id'), nullable=True)
    last_refill = db.Column(db.DateTime, default=db.func.now())
    favcards = db.relationship('Card', secondary=favorites, backref=db.backref('favusers', lazy=True))
    duel_fact = db.relationship('Duel', foreign_keys=[duel_fact_id], lazy=True)
    duel_rand = db.relationship('Duel', foreign_keys=[duel_rand_id], lazy=True)
    duel_char = db.relationship('Duel', foreign_keys=[duel_char_id], lazy=True)


class Duel(db.Model) :
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    card_a_id = db.Column(db.Integer, db.ForeignKey('card.id', ondelete="CASCADE"), nullable=False)
    card_b_id = db.Column(db.Integer, db.ForeignKey('card.id', ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created = db.Column(db.DateTime, default=db.func.now())
    ended = db.Column(db.DateTime, nullable=True)
    result = db.Column(sqlalchemy_enum(DuelResult), default=DuelResult.not_played)
    type = db.Column(db.String(4), nullable=True)
    card_a = db.relationship('Card', foreign_keys=[card_a_id], backref='duels_as_a', lazy=True)
    card_b = db.relationship('Card', foreign_keys=[card_b_id], backref='duels_as_b', lazy=True)
    user = db.relationship('User', foreign_keys=[user_id], backref='duels', lazy=True)