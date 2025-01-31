import sys
from run import app
from app import db
from app.models import Card, favorites, User, Duel
from sqlalchemy import not_, select, update, func
from datetime import datetime, timedelta

# Permet de rendre certaines cartes inactives aux duels pour rendre le site plus dynamique pour les utilisateurs courants.

mode = sys.argv[1]

with app.app_context() :
    if mode == "nonfav" :
        subquery = select(favorites.c.card_id)
        db.session.execute(update(Card).where(not_(Card.id.in_(subquery))).values(hide=1))
        db.session.commit()
        print("Cartes non favorites cachées.")
    elif mode == "inactive" :
        result = db.session.query(User.id, func.max(Duel.ended)).join(Duel, User.id == Duel.user_id).group_by(User.id).all()
        latest_duel_end_dates = {user_id: latest_ended for user_id, latest_ended in result}
        twenty_days_ago = datetime.now() - timedelta(days=20)
        cards = Card.query.filter_by(hide=0).all()
        i=-1
        j=0
        cards_to_hide_ids = []
        for card in cards :
            i+=1
            print(f'{i} cartes traitées. {j} cartes masquées.')
            users_fav = card.favusers
            if not users_fav :
                j+=1
                cards_to_hide_ids.append(card.id)
                continue
            latest_dates = [latest_duel_end_dates.get(user.id) for user in users_fav if latest_duel_end_dates.get(user.id) is not None]
            if not latest_dates :
                j+=1
                cards_to_hide_ids.append(card.id)
                continue
            most_recent_date = max(latest_dates)
            if most_recent_date < twenty_days_ago :
                j+=1
                cards_to_hide_ids.append(card.id)
        if cards_to_hide_ids :
            db.session.execute(Card.__table__.update().where(Card.id.in_(cards_to_hide_ids)).values(hide=1))
            db.session.commit()
    else :
        card = db.session.query(Card).filter(Card.reference == mode).first()
        if card :
            if card.hide == 1 :
                print("Carte déjà cachée.")
            else :
                card.hide = 1
                db.session.commit()
                print("Carte cachée.")
        else :
            print("Carte introuvable.")
