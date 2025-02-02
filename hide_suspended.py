import sys
from run import app
from app import db
from app.models import Card

# Permet de masquer les uniques d'un personnage suspendu

name = sys.argv[1]
faction = sys.argv[2]

with app.app_context() :
    result = db.session.query(Card).filter(Card.character_en_us == name, Card.faction == faction).all()
    for card in result :
        card.hide = 1
    db.session.commit()