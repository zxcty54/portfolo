import os
import json
import threading
import time
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request, jsonify
from flask_cors import CORS
import yfinance as yf

app = Flask(__name__)
CORS(app)

# ✅ Load Firebase credentials from Render environment variable
firebase_credentials = os.getenv("FIREBASE_CREDENTIALS")

if firebase_credentials:
    try:
        cred_dict = json.loads(firebase_credentials)  # ✅ Convert string to JSON
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Connected to Firebase Firestore!")
    except Exception as e:
        raise ValueError(f"❌ Firebase Initialization Error: {e}")
else:
    raise ValueError("🚨 FIREBASE_CREDENTIALS environment variable is missing!")

# ✅ Function to Fetch Stock Price
def get_stock_price(stock):
    try:
        if not stock.upper().endswith(".NS"):
            stock += ".NS"
        
        ticker = yf.Ticker(stock)
        history_data = ticker.history(period="1d")

        if history_data.empty:
            return {"price": 0, "change": 0, "prevClose": 0}

        live_price = round(history_data["Close"].iloc[-1], 2)
        prev_close = round(history_data["Close"].iloc[-2], 2) if len(history_data) > 1 else live_price
        change = round(((live_price - prev_close) / prev_close) * 100, 2) if prev_close else 0
        
        return {"price": live_price, "change": change, "prevClose": prev_close}
    
    except Exception as e:
        return {"error": str(e)}

# ✅ Background Thread to Update Stock Prices Every 3 Minutes
def update_stock_prices():
    while True:
        try:
            stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"]  # ✅ Modify as needed
            stock_data = {stock: get_stock_price(stock) for stock in stocks}

            for stock, data in stock_data.items():
                db.collection("live_prices").document(stock).set(data)

            print("✅ Stock prices updated in Firestore:", stock_data)

        except Exception as e:
            print("❌ Error updating stock prices:", str(e))

        time.sleep(180)  # ✅ Update every 3 minutes

# ✅ Start Background Thread
threading.Thread(target=update_stock_prices, daemon=True).start()

@app.route("/")
def home():
    return "✅ Stock Price API is Running!"

@app.route("/get_price/<stock>", methods=["GET"])
def get_price(stock):
    try:
        doc_ref = db.collection("live_prices").document(stock).get()
        if doc_ref.exists:
            return jsonify(doc_ref.to_dict())
        else:
            return jsonify({"error": "Stock not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_prices", methods=["POST"])
def get_prices():
    try:
        data = request.get_json()
        stocks = data.get("stocks", [])
        prices = {}

        for stock in stocks:
            doc_ref = db.collection("live_prices").document(stock).get()
            if doc_ref.exists:
                prices[stock] = doc_ref.to_dict()
            else:
                prices[stock] = {"error": "Stock not found"}

        return jsonify(prices)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
