from flask import Flask, request, jsonify
import yfinance as yf
from flask_cors import CORS
import os
import json
import threading
import time
import base64
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
CORS(app)

# 🔹 Decode Firebase JSON from Base64 (Render doesn't support JSON env vars)
firebase_json = os.getenv("FIREBASE_CREDENTIALS") 

if not firebase_json:
    raise ValueError("FIREBASE_CREDENTIALS environment variable is not set. Please add it in Render.")

decoded_json = base64.b64decode(firebase_json).decode("utf-8")
firebase_credentials = json.loads(decoded_json)

# 🔹 Initialize Firebase
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

# 🔹 Update stock prices in Firestore every 3 minutes
def update_stock_prices():
    while True:
        try:
            stocks_ref = db.collection("stocks")  # Collection: "stocks"
            docs = stocks_ref.stream()

            for doc in docs:
                stock = doc.id  # Stock symbol (document ID)
                price = get_stock_price(stock)
                stocks_ref.document(stock).set({"price": price, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)

            print("✅ Stock prices updated in Firebase!")
        except Exception as e:
            print("❌ Error updating stock prices:", str(e))

        time.sleep(180)  # 🔹 Update every 3 minutes

# 🔹 API to get stock prices from Firebase
@app.route("/get_prices", methods=["POST"])
def get_prices():
    try:
        data = request.get_json()
        stocks = data.get("stocks", [])
        prices = {}

        for stock in stocks:
            stock_doc = db.collection("stocks").document(stock).get()
            if stock_doc.exists:
                prices[stock] = stock_doc.to_dict().get("price", "Not Available")
            else:
                prices[stock] = "Stock Not Found in Firestore"

        return jsonify(prices)
    except Exception as e:
        return jsonify({"error": str(e)})

# 🔹 Start background thread to update prices
thread = threading.Thread(target=update_stock_prices, daemon=True)
thread.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
