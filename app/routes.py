from flask import render_template, redirect, url_for, request, make_response, flash, session, jsonify, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from flask import current_app as app
from flask_babel import _
from sqlalchemy import delete
from app import db
from app.models import User, Card, Duel, favorites
from app.functions import card_from_ref, get_locale, create_duel_char, create_duel_fact, create_duel_rand, can_refill, get_K_factor, calculate_elo_delta, card_graph, update_card_from_ref
from app.forms import RegistrationForm, LoginForm
import re
import pytz
import os


# Nombre de duels autorisés par jour
max_fact = 50
max_char = 50
max_rand = 50

# Chemins vers les répertoires d'images
PNG_DIR = 'static/image/png'
WEBP_DIR = 'static/image/webp'



# Contexte global pour injecter des variables dans toutes les routes
@app.context_processor
def inject_globals():
    if current_user.is_authenticated:
        # On récupère l'ID de l'utilisateur et la date de son dernier refill
        user_id = current_user.id
        last_refill = current_user.last_refill
        # On recupère alors son nombre de duels de chaque type jouées DEPUIS le dernier refill
        played_fact = db.session.query(db.func.count(Duel.id)).filter(Duel.user_id == user_id, Duel.type == 'fact', Duel.ended > last_refill).scalar() 
        played_char = db.session.query(db.func.count(Duel.id)).filter(Duel.user_id == user_id, Duel.type == 'char', Duel.ended > last_refill).scalar() 
        played_rand = db.session.query(db.func.count(Duel.id)).filter(Duel.user_id == user_id, Duel.type == 'rand', Duel.ended > last_refill).scalar()
        # On récupère la timezone de l'utilisateur et on met à jour la date du dernier Refill en conséquence pour l'affichage.
        timezone=request.cookies.get('timezone','UTC')
        utc_last_refill = pytz.utc.localize(current_user.last_refill)
        last_refill = utc_last_refill.astimezone(pytz.timezone(timezone))
        return {
            'max_fact': max_fact,
            'max_char': max_char,
            'max_rand': max_rand,
            'played_fact': played_fact,
            'played_char': played_char,
            'played_rand': played_rand,
            'last_refill': last_refill
        }
    else:
        # Si l'utilisateur n'est pas connecté, aucune des ces informations n'est renvoyée
        return {}



# Cette route permet de vérifier sur l'utilisateur est déjà connecté sur ce navigateur.
@app.before_request
def load_user_from_cookie():
    # On récupère le cookie "se souvenir de moi" de l'utilisateur
    token = request.cookies.get('remember_token')
    if token :
        # On vérifie si ce cookie correspond à un utilisateur du site.
        user = User.verify_remember_token(token)
        if user :
            # Si c'est le cas, on connecte cet utilisateur.
            login_user(user)



# Cette route permet de récupérer la timezone de l'utilisateur, elle est utilisée en javascript de la page Base
@app.route('/set_timezone', methods=['POST'])
def set_timezone():
    # On récupère le json renvoyé par le javascript
    timezone = request.json.get('timezone')
    if timezone:
        response = make_response(jsonify(success=True))
        # On crée le cookie de timezone qui permettra aux heures de s'afficher dans le bon fuseau
        response.set_cookie('timezone', timezone)
        return response
    return jsonify(success=False, message="Timezone non fournie"), 400



# Cette route permet à un utilisateur de se connecter ou de s'inscrire.
@app.route('/register', methods=['GET', 'POST'])
def register() :
    # Création des formulaires de connexion et d'inscription.
    reg_form = RegistrationForm()
    log_form = LoginForm()
    # Si la page charge un renvoi de formulaire :
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        # On vérifie de quel formulaire il s'agit, si c'est le formulaire d'inscription :
        if form_type == 'register' and reg_form.validate_on_submit():
            # On vérifie si le formulaire a été spammé, on bloque l'inscription à 2 par session.
            if session.get('created_account', 0) > 2 :
                return redirect(url_for('register'))
            # On vérifie si le nom d'utilisateur choisi est bon. Il doit être nouveau, et ne pas finir par _d (réservé aux utilisateurs discord)
            if db.session.query(User).filter_by(username=reg_form.username.data).first() or reg_form.username.data.endswith('_d') :
                regnameerror = _('regnameerror')
                flash(regnameerror, 'register')
                return redirect(url_for('register'))
            # Traitement du formulaire d'inscription
            user = User(username=reg_form.username.data)
            user.set_password(reg_form.password.data)
            db.session.add(user)
            db.session.commit()
            create_duel_char(user)
            create_duel_fact(user)
            #create_duel_mass(user)
            create_duel_rand(user)
            session['created_account'] = session.get('created_account', 0) + 1
            # Un utilisateur qui crée son compte est alors connecté et renvoyé en page d'accueil.
            login_user(user)
            return redirect(url_for('home'))
        # dans le cas ou c'est le formulaire de connexion :
        elif form_type == 'login' and log_form.validate_on_submit():
            # On bloque la session à 10 tentatives.
            if session.get('login_attempts', 0) > 10 :
                return redirect(url_for('register'))
            # Traitement du formulaire de connexion
            user = User.query.filter_by(username=log_form.username.data).first()
            if user:
                if user.check_password(log_form.password.data):
                    login_user(user)
                    # Une connexion réussie remet à zero le nombre de tentatives pour la suite.
                    session['login_attempts'] = 0
                    remember_me = log_form.remember_me.data
                    response = redirect(url_for('home'))
                    # Si l'utilisateur veut rester connecté, le token est alors ajouté dans son objet, et dans ses cookies.
                    if remember_me :
                        token = user.generate_remember_token()
                        response.set_cookie('remember_token', token, max_age=30*24*60*60)
                    return response
                else:
                    logpasserror = _('logpasserror')
                    flash(logpasserror, 'login')
                    session['login_attempts'] = session.get('login_attempts', 0) + 1
            else:
                logusererror = _('logemailerror')
                flash(logusererror, 'login')
            return redirect(url_for('register'))

        # Erreur lorsque les deux mot de passe sont différent à l'inscription.
        if reg_form.errors:
            for field, errors in reg_form.errors.items():
                if field == "password2":
                    regpasserror = _('regpasserror')
                    flash(regpasserror, 'register')
    return render_template('register.html', reg_form=reg_form, log_form=log_form)



# Cette route permet la déconnexion d'un utilisateur connecté.
@app.route('/logout')
@login_required
def logout() :
    logout_user()
    response = redirect(url_for('home'))
    # On supprime le cookie qui permet de rester connecté pour que l'utilisateur ne se reconnecte pas automatiquement a la prochaine session.
    response.delete_cookie('remember_token')
    return response



# Route de la page d'accueil
@app.route('/')
def home() :
    top_card = db.session.query(Card).filter(Card.hide==0).order_by(Card.elo.desc()).all()[:3]
    return render_template('home.html', top_card=top_card)



# Route pour la page d'ajout de cartes
@app.route('/add_cards', methods=['GET', 'POST'])
@login_required
def add_cards() :
    # La variable card participe à déterminer le message à afficher.
    card=None
    if request.method=="POST" :
        card_string = request.form['card_string']
        # Les vérifications sur le champ permettent de vérifier si la taille et la forme correspondent à une référence d'unique
        if bool(re.match(r'^ALT_(CORE(KS)?|ALIZE)_B_[A-Z]{2}_\d{2}_U_\d+$', card_string)) and len(card_string)<30 :
            card=db.session.query(Card).filter_by(reference=card_string).first()
            if card :
                if card.hide == 0 :
                    # Message pour une carte déjà présente sur le site
                    already_available = _('alreadyavailable')
                    flash(already_available)
                else :
                    card = update_card_from_ref(card, card_string)
                    if card :
                        card.hide = 0
                        db.session.commit()
                        new = _('newcard')
                        flash(new)
                    else :
                        card_not_found = _('cardnotfound')
                        flash(card_not_found)
            else :
                # Si la carte n'est pas déjà présente, requête api equinox pour la récuperer
                new_card = card_from_ref(card_string)
                if new_card :
                    # Si la requete en api fonctionne, on ajoute la carte et on informe l'utilisateur
                    new = _('newcard')
                    flash(new)
                    db.session.add(new_card)
                    db.session.commit()
                    user_id = current_user.id
                    card_id = new_card.id
                    # On met aussi la carte directement dans ses favorites
                    fav = favorites.insert().values(user_id=user_id, card_id=card_id)
                    db.session.execute(fav)
                    db.session.commit()
                    card = db.session.query(Card).filter_by(reference=card_string).first()
                else :
                    # Si la requete api ne fonctionne pas, on informe l'utilisateur
                    card_not_found = _('cardnotfound')
                    flash(card_not_found)
        else :
            # Si la référence ne respecte pas le format, on informe l'utilisateur
            wrong_reference = _('wrongref')
            flash(wrong_reference)
    return render_template('add_cards.html', existing_card=card)



# Route pour le classement
@app.route('/ladder')
def ladder() :
    # Le nombre de pages est en brut pour le moment, on pourra éventuellement le rendre modifiable par l'utilisateur
    per_page=20
    # Récupération des choix de tri et de filtre
    page = request.args.get('page', default=1, type=int)
    sort = request.args.get('sort')
    faction = request.args.get('faction')
    character = request.args.get('character')
    hidden = request.args.get('hidden', "False")
    # Récupération de la liste des cartes correspondant au filtre
    if hidden == "True" :
        query = db.session.query(Card)
    else :
        query = db.session.query(Card).filter(Card.hide==0)
    if faction :
        query = query.filter_by(faction=faction)
    lang = get_locale()
    if lang == 'fr' :
        all_characters = query.with_entities(Card.character_fr_fr).distinct().all()
        if character :
            query = query.filter_by(character_fr_fr = character)
    elif lang == 'it' :
        all_characters = query.with_entities(Card.character_it_it).distinct().all()
        if character :
            query = query.filter_by(character_it_it = character)
    elif lang == 'es' :
        all_characters = query.with_entities(Card.character_es_es).distinct().all()
        if character :
            query = query.filter_by(character_es_es = character)
    elif lang == 'de' :
        all_characters = query.with_entities(Card.character_de_de).distinct().all()
        if character :
            query = query.filter_by(character_de_de = character)
    elif lang == 'en' :
        all_characters = query.with_entities(Card.character_en_us).distinct().all()
        if character :
            query = query.filter_by(character_en_us = character)
    all_cards = sorted([character[0] for character in all_characters])
    # Tri des cartes selon l'option choisie
    if sort == 'asc' :
        cards = query.order_by(Card.elo.asc()).paginate(per_page = per_page)
    else :
        cards = query.order_by(Card.elo.desc()).paginate(per_page = per_page)
    return render_template('ladder.html', cards=cards.items, pagination=cards, start_num=(page-1) * per_page, all_cards=all_cards, selected_character=character)



# Cette route permet d'accéder au duel de faction
@app.route('/duel_fact', methods=['GET', 'POST'])
@login_required
def duel_fact() :
    lang = get_locale()
    action = '/duel_fact'
    played_fact = db.session.query(db.func.count(Duel.id)).filter(
                        Duel.user_id == current_user.id,
                        Duel.type == 'fact',
                        Duel.ended > current_user.last_refill
                        ).scalar() 
    # On vérifie si le nombre de duels joués de l'utilisateur lui permet d'en lancer un nouveau
    if played_fact >= max_fact :
        return jsonify({'message': 'Vous avez atteint la limite de duels de faction pour aujourd\'hui.'}), 403
    if request.method == 'POST':
        # On vérifie le choix de la carte gagnante (ou égalité) si il n'y en a pas, on redirige vers la page en méthode GET
        choice = request.form.get('choice')
        if choice :
            duel = current_user.duel_fact
            card_a = duel.card_a
            card_b = duel.card_b
            # Les mises en session permettent d'afficher les duels précédents
            session['fact_card_a'] = card_a.id
            session['fact_card_b'] = card_b.id
            if choice == "1" :
                card_win = card_a
                card_lose = card_b
                draw = False
                session['fact_result'] = 'left'
                duel.result= 'card_a_win'
            elif choice == "2" :
                card_win = card_b
                card_lose = card_a
                draw = False
                session['fact_result'] = 'right'
                duel.result= 'card_b_win'
            elif choice == "0" :
                card_win = card_a
                card_lose = card_b
                draw = True
                session['fact_result'] = 'draw'
                duel.result= 'draw'
            else :
                return redirect(url_for('home'))
            card_win.nb_duel += 1
            card_lose.nb_duel += 1
            K_win = get_K_factor(card_win.nb_duel)
            K_lose = get_K_factor(card_lose.nb_duel)
            elo_delta_win, elo_delta_lose = calculate_elo_delta(card_win.elo, card_lose.elo, K_win, K_lose, draw=draw)
            session['fact_delta_win'] = elo_delta_win
            session['fact_delta_lose'] = elo_delta_lose
            card_win.elo += elo_delta_win
            card_lose.elo += elo_delta_lose
            duel.ended = db.func.now()
            db.session.commit()
            create_duel_fact(current_user)
            user_refill = current_user.last_refill
            played_fact = db.session.query(db.func.count(Duel.id)).filter(
                            Duel.user_id == current_user.id,
                            Duel.type == 'fact',
                            Duel.ended > user_refill
                            ).scalar() 
            if played_fact < max_fact :
                return redirect(url_for('duel_fact'))
            else :
                return redirect(url_for('home'))
        else :
            return redirect(url_for('duel_fact'))
    else :
        duel = current_user.duel_fact
        card_a = duel.card_a
        card_b = duel.card_b
        last_duel=None
        if session.get('fact_result') :
            last_card_right_id = session.get('fact_card_b')
            last_card_left_id = session.get('fact_card_a')
            last_result = session.get('fact_result')
            if last_result == 'right' :
                delta_left = session.get('fact_delta_lose')
                delta_right = session.get('fact_delta_win')
            else :
                delta_left = session.get('fact_delta_win')
                delta_right = session.get('fact_delta_lose')
            last_card_right = db.session.query(Card).filter_by(id=last_card_right_id).first()
            last_card_left = db.session.query(Card).filter_by(id=last_card_left_id).first()
            if lang == 'fr' :
                character_left = last_card_left.character_fr_fr
                character_right = last_card_right.character_fr_fr
            elif lang == 'en' :
                character_left = last_card_left.character_en_us
                character_right = last_card_right.character_en_us
            elif lang == 'es' :
                character_left = last_card_left.character_es_es
                character_right = last_card_right.character_es_es
            elif lang == 'de' :
                character_left = last_card_left.character_de_de
                character_right = last_card_right.character_de_de
            elif lang == 'it' :
                character_left = last_card_left.character_it_it
                character_right = last_card_right.character_it_it
            last_duel = {
                'character_left' : f'{character_left} # {last_card_left.num}',
                'character_right' : f'{character_right} # {last_card_right.num}',
                'elo_left' : last_card_left.elo,
                'elo_right' : last_card_right.elo,
                'delta_left' : delta_left,
                'delta_right' : delta_right,
                'ref_left' : last_card_left.reference,
                'ref_right' : last_card_right.reference,
                'played_left' : last_card_left.nb_duel,
                'played_right' : last_card_right.nb_duel,
                'url_left' : last_card_left.url_en_us,
                'url_right' : last_card_right.url_en_us
            }
        altered_card_link = 'https://www.altered.gg/cards/'
        left_ref_split = card_a.reference.split('_')
        card_left_rare_url = altered_card_link + f'{left_ref_split[0]}_{left_ref_split[1]}_{left_ref_split[2]}_{left_ref_split[3]}_{left_ref_split[4]}_'
        if left_ref_split[3].startswith(card_a.faction[0]):
            card_left_rare_url += 'R1'
        else :
            card_left_rare_url += 'R2' 
        right_ref_split = card_b.reference.split('_')
        card_right_rare_url = altered_card_link + f'{right_ref_split[0]}_{right_ref_split[1]}_{right_ref_split[2]}_{right_ref_split[3]}_{right_ref_split[4]}_'
        if right_ref_split[3].startswith(card_b.faction[0]):
            card_right_rare_url += 'R1'
        else :
            card_right_rare_url += 'R2'
    return render_template('duel.html', card_left = card_a, card_right = card_b, card_right_rare_url = card_right_rare_url, card_left_rare_url=card_left_rare_url, last_duel=last_duel, action=action)



@app.route('/duel_char', methods=['GET', 'POST'])
@login_required
def duel_char() :
    lang = get_locale()
    action = '/duel_char'
    played_char = db.session.query(db.func.count(Duel.id)).filter(
                        Duel.user_id == current_user.id,
                        Duel.type == 'char',
                        Duel.ended > current_user.last_refill
                        ).scalar() 
    if played_char >= max_char :
        # Envoyer un message pour afficher une popup
        return jsonify({'message': 'Vous avez atteint la limite de duels de personnage pour aujourd\'hui.'}), 403
    if request.method == 'POST':
        choice = request.form.get('choice')
        if choice :
            duel = current_user.duel_char
            card_a = duel.card_a
            card_b = duel.card_b
            session['char_card_a'] = card_a.id
            session['char_card_b'] = card_b.id
            if choice == "1" :
                card_win = card_a
                card_lose = card_b
                draw = False
                session['char_result'] = 'left'
                duel.result= 'card_a_win'
            elif choice == "2" :
                card_win = card_b
                card_lose = card_a
                draw = False
                session['char_result'] = 'right'
                duel.result= 'card_b_win'
            elif choice == "0" :
                card_win = card_a
                card_lose = card_b
                draw = True
                session['char_result'] = 'draw'
                duel.result= 'draw'
            else :
                return redirect(url_for('home'))
            card_win.nb_duel += 1
            card_lose.nb_duel += 1
            K_win = get_K_factor(card_win.nb_duel)
            K_lose = get_K_factor(card_lose.nb_duel)
            elo_delta_win, elo_delta_lose = calculate_elo_delta(card_win.elo, card_lose.elo, K_win, K_lose, draw=draw)
            session['char_delta_win'] = elo_delta_win
            session['char_delta_lose'] = elo_delta_lose
            card_win.elo += elo_delta_win
            card_lose.elo += elo_delta_lose
            duel.ended = db.func.now()
            db.session.commit()
            create_duel_char(current_user)
            user_refill = current_user.last_refill
            played_char = db.session.query(db.func.count(Duel.id)).filter(
                            Duel.user_id == current_user.id,
                            Duel.type == 'char',
                            Duel.ended > user_refill
                            ).scalar() 
            if played_char < max_char :
                return redirect(url_for('duel_char'))
            else :
                return redirect(url_for('home'))
        else :
            return redirect(url_for('duel_char'))
    else :
        duel = current_user.duel_char
        card_a = duel.card_a
        card_b = duel.card_b
        last_duel=None
        if session.get('char_result') :
            last_card_right_id = session.get('char_card_b')
            last_card_left_id = session.get('char_card_a')
            last_result = session.get('char_result')
            if last_result == 'right' :
                delta_left = session.get('char_delta_lose')
                delta_right = session.get('char_delta_win')
            else :
                delta_left = session.get('char_delta_win')
                delta_right = session.get('char_delta_lose')
            last_card_right = db.session.query(Card).filter_by(id=last_card_right_id).first()
            last_card_left = db.session.query(Card).filter_by(id=last_card_left_id).first()
            if lang == 'fr' :
                character_left = last_card_left.character_fr_fr
                character_right = last_card_right.character_fr_fr
            elif lang == 'en' :
                character_left = last_card_left.character_en_us
                character_right = last_card_right.character_en_us
            elif lang == 'es' :
                character_left = last_card_left.character_es_es
                character_right = last_card_right.character_es_es
            elif lang == 'de' :
                character_left = last_card_left.character_de_de
                character_right = last_card_right.character_de_de
            elif lang == 'it' :
                character_left = last_card_left.character_it_it
                character_right = last_card_right.character_it_it
            last_duel = {
                'character_left' : f'{character_left} # {last_card_left.num}',
                'character_right' : f'{character_right} # {last_card_right.num}',
                'elo_left' : last_card_left.elo,
                'elo_right' : last_card_right.elo,
                'delta_left' : delta_left,
                'delta_right' : delta_right,
                'ref_left' : last_card_left.reference,
                'ref_right' : last_card_right.reference,
                'played_left' : last_card_left.nb_duel,
                'played_right' : last_card_right.nb_duel,
                'url_left' : last_card_left.url_en_us,
                'url_right' : last_card_right.url_en_us
            }
        altered_card_link = 'https://www.altered.gg/cards/'
        left_ref_split = card_a.reference.split('_')
        card_left_rare_url = altered_card_link + f'{left_ref_split[0]}_{left_ref_split[1]}_{left_ref_split[2]}_{left_ref_split[3]}_{left_ref_split[4]}_'
        if left_ref_split[3].startswith(card_a.faction[0]):
            card_left_rare_url += 'R1'
        else :
            card_left_rare_url += 'R2'
        right_ref_split = card_b.reference.split('_')
        card_right_rare_url = altered_card_link + f'{right_ref_split[0]}_{right_ref_split[1]}_{right_ref_split[2]}_{right_ref_split[3]}_{right_ref_split[4]}_'
        if right_ref_split[3].startswith(card_b.faction[0]):
            card_right_rare_url += 'R1'
        else :
            card_right_rare_url += 'R2'
    return render_template('duel.html', card_left = card_a, card_right = card_b, card_right_rare_url = card_right_rare_url, card_left_rare_url=card_left_rare_url, last_duel=last_duel, action=action)



@app.route('/duel_rand', methods=['GET', 'POST'])
@login_required
def duel_rand() :
    lang = get_locale()
    action = '/duel_rand'
    played_rand = db.session.query(db.func.count(Duel.id)).filter(
                        Duel.user_id == current_user.id,
                        Duel.type == 'rand',
                        Duel.ended > current_user.last_refill
                        ).scalar() 
    if played_rand >= max_rand :
        # Envoyer un message pour afficher une popup
        return jsonify({'message': 'Vous avez atteint la limite de duels aléatoire pour aujourd\'hui.'}), 403
    if request.method == 'POST':
        choice = request.form.get('choice')
        if choice :
            duel = current_user.duel_rand
            card_a = duel.card_a
            card_b = duel.card_b
            session['rand_card_a'] = card_a.id
            session['rand_card_b'] = card_b.id
            if choice == "1" :
                card_win = card_a
                card_lose = card_b
                draw = False
                session['rand_result'] = 'left'
                duel.result= 'card_a_win'
            elif choice == "2" :
                card_win = card_b
                card_lose = card_a
                draw = False
                session['rand_result'] = 'right'
                duel.result= 'card_b_win'
            elif choice == "0" :
                card_win = card_a
                card_lose = card_b
                draw = True
                session['rand_result'] = 'draw'
                duel.result= 'draw'
            else :
                return redirect(url_for('home'))
            card_win.nb_duel += 1
            card_lose.nb_duel += 1
            K_win = get_K_factor(card_win.nb_duel)
            K_lose = get_K_factor(card_lose.nb_duel)
            elo_delta_win, elo_delta_lose = calculate_elo_delta(card_win.elo, card_lose.elo, K_win, K_lose, draw=draw)
            session['rand_delta_win'] = elo_delta_win
            session['rand_delta_lose'] = elo_delta_lose
            card_win.elo += elo_delta_win
            card_lose.elo += elo_delta_lose
            duel.ended = db.func.now()
            db.session.commit()
            create_duel_rand(current_user)
            user_refill = current_user.last_refill
            played_rand = db.session.query(db.func.count(Duel.id)).filter(
                            Duel.user_id == current_user.id,
                            Duel.type == 'rand',
                            Duel.ended > user_refill
                            ).scalar() 
            if played_rand < max_rand :
                return redirect(url_for('duel_rand'))
            else :
                return redirect(url_for('home'))
        else :
            return redirect(url_for('duel_rand'))
    else :
        duel = current_user.duel_rand
        card_a = duel.card_a
        card_b = duel.card_b
        last_duel=None
        if session.get('rand_result') :
            last_card_right_id = session.get('rand_card_b')
            last_card_left_id = session.get('rand_card_a')
            last_result = session.get('rand_result')
            if last_result == 'right' :
                delta_left = session.get('rand_delta_lose')
                delta_right = session.get('rand_delta_win')
            else :
                delta_left = session.get('rand_delta_win')
                delta_right = session.get('rand_delta_lose')
            last_card_right = db.session.query(Card).filter_by(id=last_card_right_id).first()
            last_card_left = db.session.query(Card).filter_by(id=last_card_left_id).first()
            if lang == 'fr' :
                character_left = last_card_left.character_fr_fr
                character_right = last_card_right.character_fr_fr
            elif lang == 'en' :
                character_left = last_card_left.character_en_us
                character_right = last_card_right.character_en_us
            elif lang == 'es' :
                character_left = last_card_left.character_es_es
                character_right = last_card_right.character_es_es
            elif lang == 'de' :
                character_left = last_card_left.character_de_de
                character_right = last_card_right.character_de_de
            elif lang == 'it' :
                character_left = last_card_left.character_it_it
                character_right = last_card_right.character_it_it
            last_duel = {
                'character_left' : f'{character_left} # {last_card_left.num}',
                'character_right' : f'{character_right} # {last_card_right.num}',
                'elo_left' : last_card_left.elo,
                'elo_right' : last_card_right.elo,
                'delta_left' : delta_left,
                'delta_right' : delta_right,
                'ref_left' : last_card_left.reference,
                'ref_right' : last_card_right.reference,
                'played_left' : last_card_left.nb_duel,
                'played_right' : last_card_right.nb_duel,
                'url_left' : last_card_left.url_en_us,
                'url_right' : last_card_right.url_en_us
            }
        altered_card_link = 'https://www.altered.gg/cards/'
        left_ref_split = card_a.reference.split('_')
        card_left_rare_url = altered_card_link + f'{left_ref_split[0]}_{left_ref_split[1]}_{left_ref_split[2]}_{left_ref_split[3]}_{left_ref_split[4]}_'
        if left_ref_split[3].startswith(card_a.faction[0]):
            card_left_rare_url += 'R1'
        else :
            card_left_rare_url += 'R2'
        right_ref_split = card_b.reference.split('_')
        card_right_rare_url = altered_card_link + f'{right_ref_split[0]}_{right_ref_split[1]}_{right_ref_split[2]}_{right_ref_split[3]}_{right_ref_split[4]}_'
        if right_ref_split[3].startswith(card_b.faction[0]):
            card_right_rare_url += 'R1'
        else :
            card_right_rare_url += 'R2'
    return render_template('duel.html', card_left = card_a, card_right = card_b, card_right_rare_url = card_right_rare_url, card_left_rare_url=card_left_rare_url, last_duel=last_duel, action=action)



@app.route('/refill')
@login_required
def refill():
    user_id = current_user.id
    if can_refill(user_id) :
        current_user.last_refill = db.func.now()
        db.session.commit()
        return redirect(url_for('home'))
    else :
        timezone=request.cookies.get('timezone','UTC')
        utc_last_refill = pytz.utc.localize(current_user.last_refill)
        refill_date = utc_last_refill.astimezone(pytz.timezone(timezone))
        return jsonify({'message': f"{_('refilldelay')} {_('lastrefill')} : {refill_date.strftime('%b-%d %H:%M')}"}), 403



@app.route('/profile')
@login_required
def profile() :    
    cards=[]
    page = request.args.get('page', default=1, type=int)
    per_page = 20
    favorites = current_user.favcards
    for fav in favorites :
        fav_card = db.session.query(Card).filter_by(id=fav.id).first()
        cards.append(fav_card)
    user_id = int(current_user.id)
    charduels = db.session.query(db.func.count(Duel.id)).filter(Duel.user_id == user_id, Duel.type == 'char').scalar()-1
    factduels = db.session.query(db.func.count(Duel.id)).filter(Duel.user_id == user_id, Duel.type == 'fact').scalar()-1
    randduels = db.session.query(db.func.count(Duel.id)).filter(Duel.user_id == user_id, Duel.type == 'rand').scalar()-1
    if len(cards) > 0 :
        cards.sort(key=lambda x: x.elo, reverse=True)
        max_pages=max(len(cards)//per_page + 1 - ((len(cards)%per_page)==0),1)
        cards = cards[(page-1)*per_page:min(page*per_page, len(cards))]
    else :
        max_pages=1
    return render_template('profile.html', cards=cards, charduels=charduels, factduels=factduels, randduels=randduels, max_pages=max_pages, page=page)



@app.route('/card/<string:card_ref>')
@login_required
def cardview(card_ref) :
    card = db.session.query(Card).filter_by(reference=card_ref).first()
    if card :
        if card.hide == 0 :
            favcards = current_user.favcards
            favorites = []
            for c in favcards :
                favorites.append(c.id)
            lang = get_locale()
            duel_min=5
            avg_elo = db.session.query(db.func.avg(Card.elo)).filter(
                Card.hide == 0,
                Card.character_en_us == card.character_en_us,
                Card.faction == card.faction,
                Card.nb_duel >= duel_min).scalar()
            rank = db.session.query(db.func.count(Card.id)).filter(
                Card.hide == 0,
                Card.elo > card.elo,
                Card.nb_duel >= duel_min).scalar() +1
            total_cards = len(db.session.query(Card).filter(Card.nb_duel >= duel_min, Card.hide==0).all())
            all_elos = [c.elo for c in db.session.query(Card).filter(
                                            Card.character_en_us == card.character_en_us,
                                            Card.faction == card.faction,
                                            Card.nb_duel >= duel_min).all()
                        ]
            max_elo = max(all_elos)+50
            min_elo = min(all_elos)-50
            lang = get_locale()
            if lang == 'fr' :
                character = card.character_fr_fr
                title = "Graphique de répartition du Elo"
            elif lang == "en" :
                character = card.character_en_us
                title = "Elo Distribution Chart"
            elif lang == "es" :
                character = card.character_es_es
                title = "Gráfico de Distribución de Elo"
            elif lang == "it" :
                character = card.character_it_it
                title = "Grafico di Distribuzione Elo"
            elif lang == "de" :
                character = card.character_de_de
                title = "Elo-Verteilungsgrafik"
            graph = card_graph(all_elos, card.faction, title=f'{title}\n{card.faction} - {character}', min_elo=min_elo, max_elo=max_elo, card_elo=card.elo)
            html_graph = f'<img src="data:image/png;base64,{graph}">'
        else :
            card = update_card_from_ref(card, card_ref)
            if card :
                card.hide = 0
                db.session.commit()
                return redirect(url_for('cardview', card_ref=card_ref))
            else :
                return redirect(url_for('add_cards'))
    else :
        return redirect(url_for('add_cards'))
    return render_template('card.html', card=card, avg_elo=avg_elo,rank=rank,total_cards=total_cards, favorites=favorites, graph=html_graph)



@app.route('/add_favorite/<int:card_id>', methods=['POST'])
@login_required
def add_favorite(card_id):
    card = db.session.query(Card).filter(Card.hide==0).filter_by(id=card_id).first()
    if not card :
        redirect(url_for('home'))
    card_ref = card.reference
    user_id = current_user.id
    if card in current_user.favcards :
        remove_fav = delete(favorites).where(favorites.c.user_id == user_id, favorites.c.card_id == card_id)
        db.session.execute(remove_fav)
        db.session.commit()
    else :
        fav = favorites.insert().values(user_id=user_id, card_id=card_id)
        db.session.execute(fav)
        db.session.commit()
    return redirect(url_for('cardview', card_ref=card_ref))



@app.route('/set_language/<language>')
def set_language(language):
    if language in app.config['BABEL_SUPPORTED_LOCALES']:
        response = make_response(redirect(request.referrer or '/'))
        response.set_cookie('lang', language, max_age=60*60*24*365)
        return response
    return redirect(request.referrer or '/')



@app.route('/json/<string:card_ref>')
def json_route(card_ref):
    json = {
        'error' : 1,
        'elo' : 0,
        'avg_elo' : 0,
        'nb_duel' : 0
    }
    if bool(re.match(r'^ALT_(CORE(KS)?|ALIZE)_B_[A-Z]{2}_\d{2}_U_\d+$', card_ref)) :
        card = db.session.query(Card).filter_by(reference=card_ref).first()
        if card :
            json['error'] = 0
            json['elo'] = card.elo
            json['avg_elo'] = db.session.query(db.func.avg(Card.elo)).filter_by(character_en_us=card.character_en_us, faction=card.faction).scalar()
            json['nb_duel'] = card.nb_duel
    return jsonify(json)



@app.route('/cgu')
def cgu() :
    return render_template('cgu.html')



@app.route('/images/<filename>')
def serve_image(filename):
    accept_header = request.headers.get('Accept', '')
    use_webp = 'image/webp' in accept_header
    webp_filename = f"{os.path.splitext(filename)[0]}.webp"
    dir = PNG_DIR
    file = filename
    if use_webp :
        dir = WEBP_DIR
        file = webp_filename
    response = make_response(send_from_directory(dir, file))
    response.headers[ 'Cache-Control'] = 'public, max-age=31536000'
    return response