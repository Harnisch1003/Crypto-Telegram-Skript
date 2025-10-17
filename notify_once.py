
import os
import ccxt
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TIMEFRAME = "15m"
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]

def get_exchange():
    try:
        ex = ccxt.binance()
        ex.load_markets()
        print("✅ Using Binance API")
        return ex
    except Exception as e:
        print("⚠️ Binance unavailable, switching to Bybit:", e)
        return ccxt.bybit()

BINANCE = get_exchange()

def fetch_data(symbol, limit=100):
    ohlcv = BINANCE.fetch_ohlcv(symbol, TIMEFRAME, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def add_indicators(df):
    df['ema20'] = df['close'].ewm(span=20).mean()
    df['rsi'] = compute_rsi(df['close'])
    return df

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def predict_next_candle(df):
    last_close = df['close'].iloc[-1]
    last_ema = df['ema20'].iloc[-1]
    last_rsi = df['rsi'].iloc[-1]

    if last_close > last_ema and last_rsi < 70:
        return "📈 Bullish (Up)"
    elif last_close < last_ema and last_rsi > 30:
        return "📉 Bearish (Down)"
    else:
        return "⚖️ Sideways / Neutral"

def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Missing TELEGRAM_TOKEN or CHAT_ID environment variables.")
        return
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        bot.send_message(chat_id=CHAT_ID, text=message)
        print("✅ Telegram message sent")
    except Exception as e:
        print("❌ Telegram send failed:", e)

def main():
    results = []
    for sym in SYMBOLS:
        try:
            df = add_indicators(fetch_data(sym))
            prediction = predict_next_candle(df)
            results.append(f"{sym}: {prediction}")
        except Exception as e:
            results.append(f"{sym}: Error fetching data ({e})")

    message = f"🔔 Crypto Signal ({datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')})\n" + "\n".join(results)
    print(message)
    send_telegram_message(message)

if __name__ == "__main__":
    main()
