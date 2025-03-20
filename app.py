from flask import Flask, request, jsonify
import yfinance as yf
from flask_cors import CORS
import os
import json
import threading
import time
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
CORS(app)

# Initialize Firebase
firebase_json = os.getenv("FIREBASE_CONFIG")
firebase_credentials = json.loads(firebase_json)
cred = credentials.Certificate(firebase_credentials)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Function to fetch stock price
def get_stock_price(stock):
    """Fetch latest stock price from Yahoo Finance."""
    try:
        if not stock.upper().endswith(".NS"):
            stock += ".NS"

        ticker = yf.Ticker(stock)
        history_data = ticker.history(period="1d")

        if history_data.empty:
            return ticker.info.get("previousClose", 0)  # Use previous close if no data
        
        return round(history_data["Close"].iloc[-1], 2)
    except Exception as e:
        return str(e)

# Function to fetch stock symbols from Firebase
def get_stock_symbols():
    """Fetch stock symbols from Firebase Firestore."""
    try:
        stocks_ref = db.collection("market_indices")  # Adjust collection name if needed
        docs = stocks_ref.stream()
        return [doc.id for doc in docs]  # Return list of stock symbols
    except Exception as e:
        print("Error fetching stocks from Firestore:", str(e))
        return []

# Function to update stock prices in Firestore
def update_firestore_prices():
    """Fetch latest stock prices and update Firestore."""
    try:
        stocks = get_stock_symbols()  # Get only the required stocks
        for stock in stocks:
            price = get_stock_price(stock)
            db.collection("market_indices").document(stock).update({"price": price})
        print("Stock prices updated in Firestore ✅")
    except Exception as e:
        print("Error updating Firestore:", str(e))

# Background thread to update stock prices every 3 minutes
def scheduled_price_updates():
    while True:
        update_firestore_prices()
        time.sleep(180)  # Update every 3 minutes

# API to return requested stock prices from Firestore
@app.route("/get_prices", methods=["POST"])
def get_prices():
    try:
        data = request.get_json()
        stocks = data.get("stocks", [])
        prices = {}

        for stock in stocks:
            doc_ref = db.collection("market_indices").document(stock)
            doc = doc_ref.get()
            if doc.exists:
                prices[stock] = doc.to_dict().get("price", "N/A")
            else:
                prices[stock] = "Not Found"

        return jsonify(prices)
    except Exception as e:
        return jsonify({"error": str(e)})

# Start background thread for automatic updates
thread = threading.Thread(target=scheduled_price_updates, daemon=True)
thread.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
