import ccxt, pandas as pd, numpy as np, os, datetime
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
TIMEFRAME = "15m"
BACKTEST_LENGTH = 1000
BINANCE = ccxt.binance({'enableRateLimit': True})
bot = Bot(token=TELEGRAM_TOKEN)

def add_indicators(df):
    df = df.copy()
    df['ema20'] = df['close'].ewm(span=20).mean()
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd_hist'] = ema12 - ema26 - (ema12 - ema26).ewm(span=9).mean()
    delta = df['close'].diff()
    gain = np.where(delta>0, delta, 0)
    loss = np.where(delta<0, -delta, 0)
    rs = pd.Series(gain).rolling(14).mean() / (pd.Series(loss).rolling(14).mean() + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    df['bb_mid'] = df['close'].rolling(20).mean()
    df['bb_std'] = df['close'].rolling(20).std()
    df['bb_pos'] = (df['close'] - (df['bb_mid'] - 2*df['bb_std'])) / (4*df['bb_std'] + 1e-9)
    df['body'] = df['close'] - df['open']
    return df.dropna()

def predict_next_candle(df):
    last = df.iloc[-1]; score = 0
    if last['close']>last['ema20']: score+=1
    if last['macd_hist']>0: score+=1
    if 50<last['rsi']<70: score+=0.5
    if last['bb_pos']>0.6: score+=0.5
    if last['body']>0: score+=0.5
    if last['close']<last['ema20']: score-=1
    if last['macd_hist']<0: score-=1
    if last['rsi']>70 or last['rsi']<30: score-=0.5
    if last['bb_pos']<0.4: score-=0.5
    if last['body']<0: score-=0.5
    return "bullish" if score>=1 else "bearish" if score<=-1 else "neutral"

def fetch_data(symbol, limit=200):
    ohlcv = BINANCE.fetch_ohlcv(symbol, TIMEFRAME, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['ts','open','high','low','close','volume'])
    df['ts']=pd.to_datetime(df['ts'],unit='ms',utc=True)
    df.set_index('ts',inplace=True)
    return df

def run_backtest(symbol):
    df = add_indicators(fetch_data(symbol, 1100))
    preds, reals = [], []
    for i in range(len(df)-1):
        p = predict_next_candle(df.iloc[:i+1])
        r = "bullish" if df['close'].iloc[i+1]>df['close'].iloc[i] else "bearish"
        preds.append(p); reals.append(r)
    pr = [(p,r) for p,r in zip(preds,reals) if p!="neutral"]
    return round(np.mean([p==r for p,r in pr])*100,2) if pr else None

def main():
    msg_lines=[]
    next_time=None
    for sym in SYMBOLS:
        df=add_indicators(fetch_data(sym))
        pred=predict_next_candle(df)
        acc=run_backtest(sym)
        close=df['close'].iloc[-1]; nxt=df.index[-1]+pd.Timedelta(minutes=15)
        next_time=nxt; emoji="📈" if pred=="bullish" else "📉" if pred=="bearish" else "⚖️"
        msg_lines.append(f"{sym}: {emoji} *{pred.upper()}* ({close:.2f} USDT) – Backtest: {acc}%")
    msg=f"🕒 *Crypto 15 min Forecast*\nVorhersage für {next_time.strftime('%H:%M UTC')}:\n\n" + "\n".join(msg_lines)
    bot.send_message(chat_id=CHAT_ID,text=msg,parse_mode="Markdown")
    print("Sent Telegram update:",datetime.datetime.utcnow())

if __name__=="__main__":
    main()
