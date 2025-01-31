import sys
from run import app
from app import db
from app.models import User

# Inutile actuellement mais pourra servir si je fais une interface administrateur, notamment pour lancer les script ou accéder a des stats

username = sys.argv[1]

with app.app_context() :
    user = db.session.query(User).filter(User.username == username).first()
    if username :
        user.admin = 1
        db.session.commit()
        print(f"{user.username} est désormais admin.")
    else :
        print("Utilisateur introuvable.")