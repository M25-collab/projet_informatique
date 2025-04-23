from flask import Flask, render_template, jsonify
import yfinance as yf
import time
import json
import os

app = Flask(__name__)

# Cache et log
cache = {
    "data": None,
    "timestamp": 0
}
CACHE_DURATION = 30  # secondes
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
        elif lower.startswith("loreal") or lower.startswith("loréal"):
            fichiers_par_entreprise["loreal"].append(fichier)
        elif lower.startswith("airfrance"):
            fichiers_par_entreprise["airfrance"].append(fichier)

    for entreprise in fichiers_par_entreprise:
        fichiers_par_entreprise[entreprise].sort()

    return render_template("ressources.html", fichiers=fichiers_par_entreprise)

@app.route('/actualites')  
def actualites():
    return render_template('actualites.html')

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

        data = {}
        for name, symbol in tickers.items():
            hist = yf.Ticker(symbol).history(period=period, interval=interval)
            data[name] = {
                "dates": hist.index.strftime('%Y-%m-%d').tolist(),
                "values": hist["Close"].fillna(0).tolist()
            }

        return jsonify(data)
    except Exception as e:
        print("Erreur données historiques :", e)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, 'w').close()
    app.run(debug=True)

