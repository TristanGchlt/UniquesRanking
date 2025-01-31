import requests
from app.models import Card, Duel, User
from flask import current_app as app
from flask import request
from app import db
from sqlalchemy import func
import random
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64


def card_from_ref(reference):
    api = 'https://api.altered.gg/cards/'
    url = api + reference
    response = requests.get(url)
    if response.status_code == 200 :
        json = response.json()
        faction = json['mainFaction']['name']
        num = json['reference'].split('_')[-1]
        character_en_us = json['name']
        url_en_us = json['imagePath']
        image_response = requests.get(url_en_us)
        if image_response.status_code != 200 :
            return None
        else :
            response_fr = requests.get(url, headers = {'Accept-Language' : 'fr-fr'})
            if response_fr.status_code == 200 :
                json_fr = response_fr.json()
                character_fr_fr = json_fr['name']
                url_fr_fr = json_fr['imagePath']
                response_es = requests.get(url, headers = {'Accept-Language' : 'es-es'})
                if response_es.status_code == 200 :
                    json_es = response_es.json()
                    character_es_es = json_es['name']
                    url_es_es = json_es['imagePath']
                    response_it = requests.get(url, headers = {'Accept-Language' : 'it-it'})
                    if response_it.status_code == 200 :
                        json_it = response_it.json()
                        character_it_it = json_it['name']
                        url_it_it = json_it['imagePath']
                        response_de = requests.get(url, headers = {'Accept-Language' : 'de-de'})
                        if response_de.status_code == 200 :
                            json_de = response_de.json()
                            character_de_de = json_de['name']
                            url_de_de = json_de['imagePath']
                            card=Card(reference=reference, 
                                        faction=faction, 
                                        num=num, 
                                        character_en_us=character_en_us, 
                                        url_en_us=url_en_us,
                                        character_fr_fr=character_fr_fr,
                                        url_fr_fr=url_fr_fr,
                                        character_es_es=character_es_es,
                                        url_es_es=url_es_es,
                                        character_it_it=character_it_it,
                                        url_it_it=url_it_it,
                                        character_de_de=character_de_de,
                                        url_de_de=url_de_de)
                            return card
    return None


def update_card_from_ref(card, reference):
    api = 'https://api.altered.gg/cards/'
    url = api + reference
    response = requests.get(url)
    if response.status_code == 200 :
        json = response.json()
        url_en_us = json['imagePath']
        image_response = requests.get(url_en_us)
        if image_response.status_code != 200 :
            return None
        else :
            response_fr = requests.get(url, headers = {'Accept-Language' : 'fr-fr'})
            if response_fr.status_code == 200 :
                json_fr = response_fr.json()
                url_fr_fr = json_fr['imagePath']
                response_es = requests.get(url, headers = {'Accept-Language' : 'es-es'})
                if response_es.status_code == 200 :
                    json_es = response_es.json()
                    url_es_es = json_es['imagePath']
                    response_it = requests.get(url, headers = {'Accept-Language' : 'it-it'})
                    if response_it.status_code == 200 :
                        json_it = response_it.json()
                        url_it_it = json_it['imagePath']
                        response_de = requests.get(url, headers = {'Accept-Language' : 'de-de'})
                        if response_de.status_code == 200 :
                            json_de = response_de.json()
                            url_de_de = json_de['imagePath']
                            card.url_en_us = url_en_us
                            card.url_fr_fr = url_fr_fr
                            card.url_es_es = url_es_es
                            card.url_it_it = url_it_it
                            card.url_de_de = url_de_de
                            db.session.commit()
                            return card
    return None


def get_locale() :
    lang = request.cookies.get('lang','en')
    if lang in app.config['BABEL_SUPPORTED_LOCALES']:
        return lang
    return request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LOCALES'])


def calculate_elo_delta(winner_elo, loser_elo, K_winner, K_loser, draw) :
    se_winner = 1/(1+10**((loser_elo - winner_elo)/400))
    delta_winner = K_winner * ((1 - (0.5 * draw)) - se_winner)
    se_loser = 1/(1+10**((winner_elo - loser_elo)/400))
    delta_loser = K_loser * ((0 + (0.5 * draw)) - se_loser)
    return delta_winner, delta_loser


def get_K_factor(nb_played) :
    if nb_played > 100 :
        k = 16
    elif nb_played > 50 :
        k = 24
    elif nb_played > 15 :
        k = 32
    else :
        k = 50
    return k


def create_duel_fact(user) :
    cards = db.session.query(Card).filter(Card.hide==0).all()
    weights = [4 if card.nb_duel < 5 else 1 for card in cards]
    card_a = random.choices(cards, weights=weights, k=1)[0]
    cards_fact = db.session.query(Card).filter_by(faction=card_a.faction, hide=0).all()
    cards_fact.remove(card_a)
    card_b = random.choice(cards_fact)
    duelfact = Duel(card_a_id=card_a.id, card_b_id=card_b.id, user_id=user.id, type='fact')
    db.session.add(duelfact)
    db.session.commit()
    user.duel_fact_id = duelfact.id
    db.session.commit()
    return duelfact

def create_duel_rand(user) :
    cards = db.session.query(Card).filter(Card.hide==0).all()
    weights = [4 if card.nb_duel < 5 else 1 for card in cards]
    card_a = random.choices(cards, weights=weights, k=1)[0]
    cards.remove(card_a)
    card_b = random.choice(cards)
    duelrand = Duel(card_a_id=card_a.id, card_b_id=card_b.id, user_id=user.id, type='rand')
    db.session.add(duelrand)
    db.session.commit()
    user.duel_rand_id = duelrand.id
    db.session.commit()
    return duelrand

def create_duel_char(user) :
    cards = db.session.query(Card).filter(Card.hide==0).all()
    weights = [4 if card.nb_duel < 5 else 1 for card in cards]
    card_a = random.choices(cards, weights=weights, k=1)[0]
    cards_char = db.session.query(Card).filter_by(character_en_us=card_a.character_en_us, faction=card_a.faction, hide=0).all()
    cards_char.remove(card_a)
    card_b = random.choice(cards_char)
    duelchar = Duel(card_a_id=card_a.id, card_b_id=card_b.id, user_id=user.id, type='char')
    db.session.add(duelchar)
    db.session.commit()
    user.duel_char_id = duelchar.id
    db.session.commit()
    return duelchar


def can_refill(user_id):
    threshold = func.datetime('now', '-24 hours')
    user = User.query.filter(
        User.id == user_id, 
        User.last_refill <= threshold
    ).first()
    return user is not None


def card_graph(elo_list, faction, title, min_elo, max_elo, card_elo):
    binwidth=25
    faction_color = {"Axiom" : "#A56B57",
                     "Bravos" : "#C41731",
                     "Lyra" : "#CE4C78",
                     "Muna" : "#4A7D3A",
                     "Ordis" : "#007FA8",
                     "Yzmir" : "#A0679E"}
    fig, ax = plt.subplots()
    g = sns.histplot(elo_list, binwidth=binwidth, binrange=(min_elo,max_elo), kde=False)
    for bar in g.patches :
        if bar.xy[0] <= card_elo < bar.xy[0] + bar._width :
            bar.set_facecolor('#DFA52E')
        else :
            bar.set_facecolor(faction_color[faction])
    ax.set_title(title)
    ax.set_xlabel('Elo')
    ax.set_ylabel('')
    ax.set_facecolor('#ffffff')
    ax.set_yticks([])
    ax.set_xlim(min_elo-binwidth,max_elo+binwidth)
    fig.patch.set_facecolor('#ffffff')
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    plt.close(fig)
    return image_base64