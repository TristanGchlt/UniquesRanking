import sys
from run import app
from app import db
from app.models import Card

# Permet de réinitialiser le score des uniques d'un personnage qui a subi un errata

name = sys.argv[1]
faction = sys.argv[2]

with app.app_context() :
    result = db.session.query(Card).filter(Card.character_en_us == name, Card.faction == faction).all()
    for card in result :
        card.elo = 1000
        card.nb_duel = 0
    db.session.commit()