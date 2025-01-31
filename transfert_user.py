import sys
from run import app
from app import db
from app.models import User, Duel, favorites

old_username = sys.argv[1]
new_username = sys.argv[2]

# Transferer les duels d'un utilisateur
# Ajouter les cartes favorites de l'ancien utilisateur vers le nouveau

# Utilisation exceptionnel en cas de mot de passe oublié ou bien pour les anciens comptes liés à discord

with app.app_context() :
    # Sélection des utilisateurs à traiter
    old_user = db.session.query(User).filter(User.username == old_username).first()
    new_user = db.session.query(User).filter(User.username == new_username).first()
    # Sélection des duels attribués à l'ancien compte
    duelchar = db.session.query(Duel).filter(Duel.user_id == old_user.id, Duel.result != "not_played", Duel.type == 'char').all()
    duelfact = db.session.query(Duel).filter(Duel.user_id == old_user.id, Duel.result != "not_played", Duel.type == 'fact').all()
    duelrand = db.session.query(Duel).filter(Duel.user_id == old_user.id, Duel.result != "not_played", Duel.type == 'rand').all()
    # Attribution des duels au nouveau compte
    for duel in duelchar :
        duel.user_id = new_user.id
    for duel in duelfact :
        duel.user_id = new_user.id
    for duel in duelrand :
        duel.user_id = new_user.id
    # Attribution des cartes favorites de l'ancien compte au nouveau
    favs = old_user.favcards
    new_favs = new_user.favcards
    for fav in favs :
        if fav not in new_favs : 
            new_fav = favorites.insert().values(user_id = new_user.id, card_id = fav.id)
            db.session.execute(new_fav)
    db.session.commit()