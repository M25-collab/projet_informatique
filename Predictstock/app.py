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
from flask import redirect, url_for

app = Flask(__name__)


"""def safe_get_history(ticker_str, period="6mo", interval="1wk"):
    retries = 5
    wait = 30
    for attempt in range(retries):
        try:
            ticker = yf.Ticker(ticker_str)
            hist = ticker.history(period=period, interval=interval)
            time.sleep(1)  # petite pause pour être poli
            return hist
        except Exception as e:
            if "Too Many Requests" in str(e):
                print(f"❌ Rate limit hit for {ticker_str}. Waiting {wait} seconds before retry {attempt+1}...")
                time.sleep(wait)
                wait *= 2  # backoff exponentiel
            else:
                print(f"❌ Erreur récupération {ticker_str} : {e}")
                break
    return None"""






# Partie app.py : Stock Data

cache = {
    "data": None,
    "timestamp": 0
}
CACHE_DURATION = 180  # secondes
LOG_FILE = "stock_data_log.jsonl"

def get_stock_price(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        info = ticker.info
        price = info.get("currentPrice")
        return float(price) if price else None
    except Exception as e:
        print(f"Erreur récupération {ticker_symbol}: {e}")
        return None

def fetch_all_prices():
    danone = get_stock_price("BN.PA")
    loreal = get_stock_price("OR.PA")
    airfrance = get_stock_price("AF.PA")

    data = {
        "danone": [danone]*7 if danone else [0]*7,
        "loreal": [loreal]*7 if loreal else [0]*7,
        "airfrance": [airfrance]*7 if airfrance else [0]*7
    }

    log_data(data)
    return data

def log_data(data):
    try:
        log_entry = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "data": data
        }
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
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
            time.sleep(1)
        elif lower.startswith("loreal") or lower.startswith("loréal"):
            fichiers_par_entreprise["loreal"].append(fichier)
            time.sleep(1)
        elif lower.startswith("airfrance"):
            fichiers_par_entreprise["airfrance"].append(fichier)
            time.sleep(1)

    for entreprise in fichiers_par_entreprise:
        fichiers_par_entreprise[entreprise].sort()
        time.sleep(1)

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

"""@app.route('/api/stock-data')
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

    return jsonify(data)"""

# --- FIN modification cache persistante ---

# --- A COMMENTER ou supprimer si tu veux, car remplacé par le cache persisté

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
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)
            time.sleep(1)  # diminuer par rapport à avant (45s)
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
    """
    Exporte les données historiques pour une seule entreprise
    dans un CSV au format : jour,prix,score
    où 'jour' est un indice 0,1,2..., 'prix' est le cours de clôture,
    et 'score' le score d'actualité (ici on mettra 0 ou un score moyen).
    """
    # Récupérer les données historiques (comme dans ton endpoint)
    period = "6mo"; interval = "1wk"
    #hist = yf.Ticker({"danone":"BN.PA","loreal":"OR.PA","airfrance":"AF.PA"}[company]) \
    #       .history(period=period, interval=interval)
    symbol = {"danone":"BN.PA", "loreal":"OR.PA", "airfrance":"AF.PA"}[company]
    time.sleep(1)
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period, interval=interval)
    if hist is None or hist.empty:
        print(f"❌ Impossible de récupérer l'historique pour {company}.")
        return
    time.sleep(1)
    dates   = hist.index.strftime('%Y-%m-%d').tolist()
    closes  = hist["Close"].fillna(0).tolist()

    # Ici on met un score d'actualité par défaut à 0,
    # ou tu peux calculer une moyenne de evaluated_articles si tu veux.
    # Par exemple :
    avg_score = 0
    if evaluated_articles:
        avg_score = sum(a['score'] for a in evaluated_articles) / len(evaluated_articles)

    # Écriture du CSV
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['jour','prix','score'])
        for i, price in enumerate(closes):
            writer.writerow([i, price, avg_score])
    print(f"→ {filename} généré pour {company}")



#pour optimiser les fichier csv
@app.route('/api/export-csv/<company>', methods=['GET'])
def export_csv(company):
    # Déterminer le nom du fichier en fonction de l'entreprise
    filename = f'historique_{company}.csv'
    
    # Générer le fichier CSV si nécessaire
    export_historique_csv(company, filename)
    time.sleep(1)
    
    # Renvoi du fichier CSV
    return send_file(filename, as_attachment=True)


@app.route('/api/predict/<company>', methods=['GET'])
def predict(company):
    filename = f'historique_{company}.csv'
    export_historique_csv(company, filename)
    lancer_ia(company)
    return jsonify({"message": f"Prédiction lancée pour {company}."})


def lancer_ia(company):
    """
    Lance le programme C de prédiction boursière pour une entreprise donnée.
    Il utilise le fichier CSV généré précédemment, et produit un fichier de sortie prediction_<entreprise>.txt
    """
    # Génère les noms des fichiers basés sur le nom de l'entreprise
    csv_hist = f'historique_{company}.csv'  # Fichier CSV historique
    txt_corr = f'prediction_{company}_corr.txt'  # Fichier de sortie pour les résultats
    txt_init = f'prediction_{company}_init.txt'  # Fichier de sortie initial
    exe_name = 'mon_ia_c.exe'  # Nom de l'exécutable C

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

# Il faut ATTENDRE vraiment quelques secondes voir une bonne minute pitié sinon trop de demande, pitié, si fonctionne pas enlever VPN
@app.route('/api/prediction-data', methods=['GET'])
def prediction_data():
    companies = ['danone', 'loreal', 'airfrance']
    prediction_results = {}
    for company in companies:
        prediction_file = f"prediction_{company}_corr.txt"
        try:
            with open(f'ia/{company}_txt_corr.txt', 'r') as file:
                predictions = file.readlines()
                prediction = float(predictions[-1].strip())
                prediction_results[company] = [prediction]
        except FileNotFoundError:
            print(f"Fichier non trouvé : {prediction_file}")
            prediction_results[company] = [0]
    return {"data": prediction_results, "timestamp": time.time()}




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


@app.route('/admin/run_exports')
def run_exports():
    def background_task():
        for company in ['danone', 'loreal', 'airfrance']:
            export_historique_csv(company)
            lancer_ia(company)


    thread = threading.Thread(target=background_task)
    thread.start()

    return jsonify({"status": "Exportation et IA lancés en arrière-plan"})



# Démarrage de l'application
if __name__ == '__main__':
    # 1) Charger les coefficients et récupérer les articles
    load_coefficients()
    scrape_articles()
    schedule_article_update()

    # 2) Générer les CSV historiques + lancer l’IA C pour chaque entreprise
    """for company in ['danone', 'loreal', 'airfrance']:
        # a) CSV prix + score
        export_historique_csv(company, f'historique_{company}.csv')
        
        # b) Appel à l’IA C => création de prediction_<company>.txt
        lancer_ia(company)"""
        

    # 3) Lancer le serveur Flask (une seule fois !)
    app.run(debug=True)





