import sys
from run import app
from app import db
from app.models import User

old_username = sys.argv[1]
new_username = sys.argv[2]

# Permet de rename un utilisateur

# Lorsque mot de passe oublié, afin de ne pas demander aux utilisateurs leur mail (je veux récup le moins d'info perso possible) :
# - je rename le compte avec un suffixe _old (ou autre)
# - la personne crée un nouveau compte avec son nom d'utilsateur
# - j'utilise transfer_user.py pour que le nouveau compte récupère toutes les données du compte dont le mot de passe a été oublié

with app.app_context() :
    user = db.session.query(User).filter(User.username == old_username).first()
    username_taken = db.session.query(User).filter(User.username == new_username).first()
    if username_taken :
        print('Nom déjà pris')
    else :
        user.username = new_username
        db.session.commit()
        print('Nom changé')