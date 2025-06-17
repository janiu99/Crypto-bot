import os
import time
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

client = Client(api_key, api_secret)

PAIRS = os.getenv("PAIRS", "BTCUSDC,ETHUSDC,BNBUSDC").split(",")
CAPITAL_SPLIT = int(os.getenv("CAPITAL_SPLIT", 3))
TRADE_INTERVAL = int(os.getenv("TRADE_INTERVAL_SEC", 900))

positions = {}

def is_trading_hour():
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    return 14 <= now.hour < 22

def get_price(pair):
    klines = client.get_klines(symbol=pair, interval=Client.KLINE_INTERVAL_15MINUTE, limit=2)
    open_price = float(klines[0][1])
    close_price = float(klines[-1][4])
    return open_price, close_price

def trade(pair, usdc_balance):
    try:
        open_price, close_price = get_price(pair)
        change = (close_price - open_price) / open_price * 100
        print(f"[{pair}] Zmiana ceny: {change:.2f}%")

        if pair in positions:
            entry_price = positions[pair]
            profit = (close_price - entry_price) / entry_price * 100

            if profit >= 1:
                symbol = pair.replace("USDC", "")
                quantity = float(client.get_asset_balance(asset=symbol)["free"])
                if quantity > 0:
                    client.order_market_sell(symbol=pair, quantity=round(quantity, 6))
                    print(f"[{pair}] Sprzedaż z zyskiem {profit:.2f}%")
                    del positions[pair]

            elif profit <= -2:
                symbol = pair.replace("USDC", "")
                quantity = float(client.get_asset_balance(asset=symbol)["free"])
                if quantity > 0:
                    client.order_market_sell(symbol=pair, quantity=round(quantity, 6))
                    print(f"[{pair}] STOP-LOSS {profit:.2f}%")
                    del positions[pair]

        else:
            if change <= -1:
                usdc_part = usdc_balance / CAPITAL_SPLIT
                qty = round(usdc_part / close_price, 5)
                client.order_market_buy(symbol=pair, quantity=qty)
                positions[pair] = close_price
                print(f"[{pair}] Kupno po spadku: {close_price:.2f}")

    except BinanceAPIException as e:
        print(f"Błąd Binance ({pair}): {e}")
    except Exception as e:
        print(f"Inny błąd ({pair}): {e}")

while True:
    try:
        if is_trading_hour():
            usdc_balance = float(client.get_asset_balance(asset='USDC')["free"])
            print(f"Saldo USDC: {usdc_balance:.2f}")
            for pair in PAIRS:
                trade(pair, usdc_balance)
        else:
            print("⏸️ Poza godzinami handlu – bot śpi 😴")
        print("⏳ Oczekiwanie...")
        time.sleep(TRADE_INTERVAL)

    except KeyboardInterrupt:
        print("Bot zatrzymany ręcznie.")
        break
    except Exception as e:
        print(f"Błąd ogólny: {e}")
