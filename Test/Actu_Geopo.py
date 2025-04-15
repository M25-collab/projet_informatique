from flask import Flask, jsonify, request
import requests
import re
import json
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz

app = Flask(__name__)

# Liste de mots clés pour l'évaluation des articles
mots_negatifs = [
    "guerre", "conflit", "récession", "inflation", "crise économique", "panne", "grève", "licenciements",
    "réduction des coûts", "réduction des effectifs", "fermeture d'usine", "détérioration", "incertitude",
    "perte", "faillite", "scandale", "retard", "suspension", "dépôt de bilan", "chômage", "problèmes de production",
    "plan de restructuration", "mauvais résultats", "abandon de projet", "pollution", "manque de financement",
    "concurrence accrue", "instabilité", "déclin", "crise de confiance", "ralentissement", "embargo", "désastre",
    "controverse", "disruption", "contraction", "scandale fiscal", "non-conformité", "mauvaise performance",
    "rétrogradation", "mauvaise gestion", "non-rentabilité", "retards significatifs", "dissolution de partenariat",
    "impact environnemental négatif", "démission du PDG", "départ d'un cadre clé", "appels à la liquidation",
    "perte de contrats majeurs", "dérives éthiques"
]

mots_neutres = [
    "projet", "rapport", "investissement", "expansion", "nouvelle technologie", "révision", "progrès", "lancement",
    "réflexion", "collaboration", "nouveau partenariat", "recrutement", "diversification", "initiative", "fusion",
    "acquisition", "présentation", "discussion", "objectif", "recherche", "protocole", "test", "investisseur",
    "consensus", "marché", "indicateur", "analyse", "partenariat stratégique", "évaluation"
]

mots_positifs = [
    "bons résultats", "croissance", "succès", "innovation", "révolutionnaire", "expansion", "rentabilité",
    "part de marché", "leadership", "nouveau produit", "collaboration fructueuse", "forte demande",
    "augmentation des bénéfices", "nouveaux contrats", "augmentation des ventes", "augmentation de la production",
    "bonnes perspectives", "récompense", "réalisation", "partenariat stratégique", "recrutement renforcé",
    "confiance", "durabilité", "prise de leadership", "investissement fructueux", "valeur ajoutée",
    "expansion internationale", "développement", "réussite", "excellence", "soutien gouvernemental",
    "amélioration", "performance exceptionnelle", "progrès exceptionnels", "croissance exponentielle",
    "innovation de rupture", "leadership sur le marché", "partenariat gagnant-gagnant", "prise de part de marché",
    "recrutement d'experts", "augmentation de la rentabilité", "récupération post-crise"
]

# Coefficients de pondération pour les mots positifs, négatifs et la variation du cours
coefficients = {
    'mots_positifs': 1.0,
    'mots_negatifs': -1.0,
    'variation_cours': 0.5
}

# Variable globale pour stocker les articles évalués
evaluated_articles = []

# Charger les coefficients depuis un fichier JSON
def load_coefficients():
    global coefficients
    try:
        with open('coefficients.json', 'r') as file:
            coefficients = json.load(file)
    except FileNotFoundError:
        pass

# Sauvegarder les coefficients dans un fichier JSON
def save_coefficients():
    with open('coefficients.json', 'w') as file:
        json.dump(coefficients, file)

# Évaluer le texte en fonction des mots clés et des coefficients de pondération
def evaluate_text(text):
    score = 0
    words = re.findall(r'\b\w+\b', text.lower())
    for word in words:
        if word in mots_positifs:
            score += coefficients['mots_positifs']
        elif word in mots_negatifs:
            score += coefficients['mots_negatifs']
    return score

# Récupérer les articles géopolitiques depuis News API
def get_news_api_articles():
    url = 'https://newsapi.org/v2/top-headlines'
    params = {
        'category': 'world',
        'apiKey': 'VOTRE_CLE_API'  # Remplacez par votre clé API News API
    }
    response = requests.get(url, params=params)
    articles = response.json()['articles']
    return articles

# Scraper les articles et les évaluer
def scrape_articles():
    global evaluated_articles
    articles = get_news_api_articles()
    evaluated_articles = []
    for article in articles:
        titre = article['title']
        description = article['description']
        full_text = titre + " " + (description or "")

        # Évaluer le texte de l'article
        score = evaluate_text(full_text)
        evaluated_articles.append({
            'titre': titre,
            'description': description,
            'url': article['url'],
            'score': score
        })

# Endpoint pour obtenir les 3 premiers articles évalués
@app.route('/actu', methods=['GET'])
def get_actu():
    # Retourne les 3 premiers articles pour l'affichage sur le site HTML
    top_articles = sorted(evaluated_articles, key=lambda x: x['score'], reverse=True)[:3]
    return jsonify(top_articles)

# Endpoint pour obtenir tous les articles évalués
@app.route('/all_articles', methods=['GET'])
def get_all_articles():
    return jsonify(evaluated_articles)

# Endpoint pour recevoir les feedbacks et ajuster les coefficients de pondération
# @app.route('/correct', methods=['POST'])
# def correct():
#     data = request.json
#     predicted_score = data['predicted_score']
#     actual_score = data['actual_score']
#     auto_correct(predicted_score, actual_score)
#     return jsonify({'status': 'success'})

# Auto-correction des coefficients de pondération en fonction de l'écart entre le score prédit et le score réel
# def auto_correct(predicted_score, actual_score):
#     global coefficients
#     if abs(predicted_score - actual_score) > 0.5:  # Seuil d'écart
#         if predicted_score > actual_score:
#             coefficients['mots_positifs'] -= 0.1
#             coefficients['mots_negatifs'] += 0.1
#         else:
#             coefficients['mots_positifs'] += 0.1
#             coefficients['mots_negatifs'] -= 0.1
#         save_coefficients()

# Planifier la mise à jour des articles toutes les 24 heures à 6h (heure française)
def schedule_article_update():
    scheduler = BackgroundScheduler()
    # Définir le fuseau horaire pour l'heure française
    paris_tz = pytz.timezone('Europe/Paris')
    # Planifier la tâche à 6h (heure française)
    scheduler.add_job(scrape_articles, 'cron', hour=6, timezone=paris_tz)
    scheduler.start()

if __name__ == '__main__':
    load_coefficients()  # Charger les coefficients au démarrage
    scrape_articles()  # Récupérer et évaluer les articles au démarrage
    schedule_article_update()  # Planifier la mise à jour des articles
    app.run(debug=True)  # Lancer le serveur Flask en mode debug
