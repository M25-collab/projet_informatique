from flask import Flask, render_template, jsonify, request
import yfinance as yf
import time
import json
import os
import feedparser
import re
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import csv
from flask import send_file
import subprocess
import threading


app = Flask(__name__)


def safe_get_history(ticker_str, period="6mo", interval="1wk"):
    retries = 5
    wait = 30
    for attempt in range(retries):
        try:
            ticker = yf.Ticker(ticker_str)
            hist = ticker.history(period=period, interval=interval)
            time.sleep(1)
            return hist
        except Exception as e:
            if "Too Many Requests" in str(e):
                print(f"Rate limit hit for {ticker_str}. Retrying in {wait}s...")
                time.sleep(wait)
                wait *= 2
            else:
                print(f"Erreur sur {ticker_str} : {e}")
                break
    return None

# --------------------------- CACHE + STOCK DATA ---------------------------

CACHE_FILE = "cache_stock_data.json"
LOG_FILE = "stock_data_log.jsonl"
CACHE_DURATION = 30  # secondes
cache = {"data": None, "timestamp": 0}

def load_cache_from_file():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                if "timestamp" in data and "data" in data:
                    return data
        except Exception as e:
            print(f"Erreur cache disque: {e}")
    return {"data": None, "timestamp": 0}

def save_cache_to_file(cache_data):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
    except Exception as e:
        print(f"Erreur sauvegarde cache: {e}")

def get_stock_price(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        price = info.get("currentPrice")
        return float(price) if price else None
    except Exception as e:
        print(f"Erreur {ticker_symbol}: {e}")
        return None

def fetch_all_prices():
    data = {
        "danone": [get_stock_price("BN.PA") or 0],
        "loreal": [get_stock_price("OR.PA") or 0],
        "airfrance": [get_stock_price("AF.PA") or 0]
    }
    log_data(data)
    return data

def log_data(data):
    entry = {"timestamp": time.strftime('%Y-%m-%d %H:%M:%S'), "data": data}
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        print(f"Erreur de log: {e}")

@app.route('/')
def accueil():
    return render_template('accueil.html')

@app.route('/utilisateurs')
def utilisateurs():
    return render_template('utilisateurs.html')

@app.route('/ressources')
def ressources():
    pdf_folder = os.path.join(app.static_folder, 'pdfs')
    fichiers = os.listdir(pdf_folder)

    fichiers_par_entreprise = {
        "danone": [],
        "loreal": [],
        "airfrance": []
    }

    for fichier in fichiers:
        lower = fichier.lower()
        if lower.startswith("danone"):
            fichiers_par_entreprise["danone"].append(fichier)
            time.sleep(5)
        elif lower.startswith("loreal") or lower.startswith("loréal"):
            fichiers_par_entreprise["loreal"].append(fichier)
            time.sleep(5)
        elif lower.startswith("airfrance"):
            fichiers_par_entreprise["airfrance"].append(fichier)
            time.sleep(5)

    for entreprise in fichiers_par_entreprise:
        fichiers_par_entreprise[entreprise].sort()
        time.sleep(2)

    return render_template("ressources.html", fichiers=fichiers_par_entreprise)

@app.route('/actualites')  
def actualites():
    return render_template('actualites.html')

CACHE_FILE = "cache_stock_data.json"  # Fichier pour cache persistant sur disque

# Charger cache depuis disque au démarrage (sinon vide)
def load_cache_from_file():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                # Vérifier que le timestamp est présent
                if "timestamp" in cache_data and "data" in cache_data:
                    return cache_data
        except Exception as e:
            print(f"Erreur chargement cache disque: {e}")
    return {"data": None, "timestamp": 0}

# Sauvegarder cache dans fichier
def save_cache_to_file(cache_data):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
    except Exception as e:
        print(f"Erreur sauvegarde cache disque: {e}")

# Initialisation cache mémoire en important les données du fichier au démarrage
cache = load_cache_from_file()

CACHE_DURATION = 30  # secondes (tu peux augmenter)

@app.route('/api/stock-data')
def api_stock_data():
    now = time.time()

    # 1) Vérifier si cache mémoire est valide
    if cache["data"] and now - cache["timestamp"] < CACHE_DURATION:
        print("✅ Données servies depuis le cache mémoire")
        return jsonify(cache["data"])
    
    # 2) Sinon, essayer de charger cache depuis disque (persistant)
    cache_file_data = load_cache_from_file()
    if cache_file_data["data"] and now - cache_file_data["timestamp"] < CACHE_DURATION:
        # Mettre à jour cache mémoire depuis cache disque
        cache["data"] = cache_file_data["data"]
        cache["timestamp"] = cache_file_data["timestamp"]
        print("✅ Données servies depuis le cache disque")
        return jsonify(cache["data"])

    # 3) Sinon, recharger depuis yfinance
    print("🔄 Mise à jour des données avec yfinance...")
    data = fetch_all_prices()

    # 4) Mettre à jour cache mémoire et disque
    cache["data"] = data
    cache["timestamp"] = now
    save_cache_to_file(cache)

    return jsonify(data)

# --- FIN modification cache persistante ---

# --- A COMMENTER ou supprimer si tu veux, car remplacé par le cache persisté
"""
@app.route('/api/stock-data')
def api_stock_data():
    now = time.time()
    if cache["data"] and now - cache["timestamp"] < CACHE_DURATION:
        print("✅ Données servies depuis le cache")
        return jsonify(cache["data"])
    
    print("🔄 Mise à jour des données avec yfinance...")
    data = fetch_all_prices()
    cache["data"] = data
    cache["timestamp"] = now
    return jsonify(data)
"""

@app.route('/api/historical-stock-data')
def api_historical_stock_data():
    try:
        period = "6mo"
        interval = "1wk"

        tickers = {
            "danone": "BN.PA",
            "loreal": "OR.PA",
            "airfrance": "AF.PA"
        }

        # --- Modification: centraliser l'appel yfinance ici ---
        ticker_symbols_str = " ".join(tickers.values())  # "BN.PA OR.PA AF.PA"
        tickers_obj = yf.Tickers(ticker_symbols_str)

        data = {}
        for name, symbol in tickers.items():
            # Utilisation du ticker centralisé
            # ATTENTION: yfinance ne garantit pas toujours la fiabilité sur plusieurs tickers
            hist = safe_get_history(symbol, period=period, interval=interval)
            time.sleep(5)  # diminuer par rapport à avant (45s)
            if hist is None or hist.empty:
                data[name] = {"dates": [], "values": []}
            else:
                data[name] = {
                    "dates": hist.index.strftime('%Y-%m-%d').tolist(),
                    "values": hist["Close"].fillna(0).tolist()
                }

        return jsonify(data)
    except Exception as e:
        print("Erreur données historiques :", e)
        return jsonify({"error": str(e)}), 500
    

# Partie actu_geo.py : Actualités géopolitiques

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

# Récupérer les articles géopolitiques depuis un flux RSS
def get_rss_articles():
    url = 'https://www.lemonde.fr/rss/une.xml'
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries:
        articles.append({
            'title': entry.title,
            'description': entry.description,
            'url': entry.link
        })
    return articles

# Scraper les articles et les évaluer
def scrape_articles():
    global evaluated_articles
    articles = get_rss_articles()
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
    top_articles = sorted(evaluated_articles, key=lambda x: x['score'], reverse=True)[:3]
    return jsonify(top_articles)

# Planifier la mise à jour des articles toutes les 24 heures à 6h (heure française)
def schedule_article_update():
    scheduler = BackgroundScheduler()
    paris_tz = pytz.timezone('Europe/Paris')
    scheduler.add_job(scrape_articles, 'cron', hour=6, timezone=paris_tz)
    scheduler.start()



#ici pour l'IA
def export_historique_csv(company, filename='historique.csv'):
    symbol = {"danone": "BN.PA", "loreal": "OR.PA", "airfrance": "AF.PA"}[company]
    hist = safe_get_history(symbol)
    if hist is None or hist.empty:
        return
    avg_score = sum((a['score'] for a in evaluated_articles), 0) / max(len(evaluated_articles), 1)
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['jour','prix','score'])
        for i, price in enumerate(hist['Close'].fillna(0).tolist()):
            writer.writerow([i, price, avg_score])

def lancer_ia(company):
    csv_hist = f'historique_{company}.csv'
    txt_corr = f'prediction_{company}_corr.txt'
    txt_init = f'prediction_{company}_init.txt'
    if not os.path.exists('mon_ia_c.exe') or not os.path.exists(csv_hist):
        return
    try:
        subprocess.run(['mon_ia_c.exe', csv_hist, txt_init, txt_corr], check=True)
    except Exception as e:
        print(f"Erreur IA {company}: {e}")

@app.route('/api/prediction-data')
def prediction_data():
    data = {}
    for company in ['danone', 'loreal', 'airfrance']:
        path = f'prediction_{company}.txt'
        try:
            with open(path, 'r') as f:
                data[company] = [float(x) for x in f if x.strip()]
        except:
            data[company] = []
    return jsonify(data)
    # Vérifie si l'exécutable existe
    if not os.path.isfile(exe_name):
        print(f"❌ L'exécutable '{exe_name}' est introuvable dans le répertoire actuel.")
        return

    # Vérifie si le fichier CSV existe
    if not os.path.isfile(csv_hist):
        print(f"❌ Le fichier '{csv_hist}' est introuvable.")
        return

    try:
        # Appel du programme IA via subprocess
        result = subprocess.run(
            [exe_name, csv_hist, txt_init, txt_corr],  # Passe les fichiers appropriés
            stdout=subprocess.PIPE,  # Capture la sortie standard
            stderr=subprocess.PIPE,  # Capture les erreurs
            check=True  # Lève une exception en cas d'erreur
        )
        print(f"✅ Prédiction générée pour {company} → {txt_corr}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de l'exécution de l'IA : {e.stderr.decode()}")
    except FileNotFoundError as e:
        print(f"❌ Erreur : {e}")


"""@app.route('/api/prediction-data', methods=['GET'])
def prediction_data():
    result = {}
    for company in ['danone', 'loreal', 'airfrance']:
        filepath = f'prediction_{company}.txt'
        try:
            with open(filepath, 'r') as f:
                lignes = f.read().splitlines()
                result[company] = [float(val) for val in lignes if val.strip()]
        except FileNotFoundError:
            result[company] = []
    return jsonify(result)"""


#Routes vers les nouvelles pages

@app.route('/mentions')
def mentions():
    return render_template('mentions.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/reseaux')
def reseaux():
    return render_template('reseaux.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/support')
def support():
    return render_template('support.html')


# Démarrage de l'application
if __name__ == '__main__':
    load_coefficients()
    scrape_articles()
    scheduler = BackgroundScheduler()
    scheduler.add_job(scrape_articles, 'cron', hour=6, timezone=pytz.timezone('Europe/Paris'))
    scheduler.start()

    for company in ['danone', 'loreal', 'airfrance']:
        export_historique_csv(company, f'historique_{company}.csv')
        lancer_ia(company)

    # Lancer le serveur sans reloader
    app.run(debug=False, use_reloader=False)


