import os
import time
import math
import json
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Dane z Railway
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

client = Client(api_key, api_secret)

# Konfiguracja
PAIRS = os.getenv("PAIRS", "BTCUSDC,ETHUSDC,BNBUSDC").split(",")
CAPITAL_SPLIT = int(os.getenv("CAPITAL_SPLIT", 3))
TRADE_INTERVAL = int(os.getenv("TRADE_INTERVAL_SEC", 900))  # 15 minut

positions_file = "positions.json"
positions = {}
stop_loss_count = {}
blocked_pairs = {}
BLOCK_DURATION = 12 * 60 * 60  # 12h

# Ładowanie pozycji z pliku
if os.path.exists(positions_file):
    with open(positions_file, "r") as f:
        positions = json.load(f)

def save_positions():
    with open(positions_file, "w") as f:
        json.dump(positions, f)

def get_price(pair):
    klines = client.get_klines(symbol=pair, interval=Client.KLINE_INTERVAL_15MINUTE, limit=2)
    open_price = float(klines[0][1])
    close_price = float(klines[-1][4])
    return open_price, close_price

def get_lot_size(pair):
    info = client.get_symbol_info(pair)
    for f in info['filters']:
        if f['filterType'] == 'LOT_SIZE':
            step = float(f['stepSize'])
            min_qty = float(f['minQty'])
            return step, min_qty
    return 0.001, 0.0001

def round_step_size(quantity, step_size):
    precision = int(round(-math.log(step_size, 10), 0))
    return round(quantity, precision)

def trade(pair, usdc_balance):
    try:
        now = time.time()
        symbol = pair.replace("USDC", "")

        # Zablokowanie po 3x stop-loss
        if pair in blocked_pairs and now - blocked_pairs[pair] < BLOCK_DURATION:
            print(f"[{pair}] ❌ Zablokowana para (stop-loss 3x)")
            return
        elif pair in blocked_pairs:
            del blocked_pairs[pair]
            stop_loss_count[pair] = 0

        open_price, close_price = get_price(pair)
        change = (close_price - open_price) / open_price * 100
        print(f"[{pair}] Zmiana ceny: {change:.2f}%")

        balance = float(client.get_asset_balance(asset=symbol)["free"])
        step, min_qty = get_lot_size(pair)

        if pair in positions:
            entry_price = positions[pair]
            profit = (close_price - entry_price) / entry_price * 100

            if profit >= 0.9 or profit <= -1.5:
                if balance >= min_qty:
                    qty = round_step_size(balance, step)
                    client.order_market_sell(symbol=pair, quantity=qty)
                    print(f"[{pair}] {'✅ Zysk' if profit >= 0.9 else '🛑 STOP-LOSS'}: {profit:.2f}%")
                    del positions[pair]
                    save_positions()

                    if profit <= -1.5:
                        stop_loss_count[pair] = stop_loss_count.get(pair, 0) + 1
                        if stop_loss_count[pair] >= 3:
                            blocked_pairs[pair] = time.time()
                            print(f"[{pair}] ⚠️ Zablokowane po 3 stratach")

                else:
                    print(f"[{pair}] ⚠️ Za małe saldo {symbol} do sprzedaży: {balance}")

        else:
            if balance >= min_qty:
                print(f"[{pair}] ⛔ Już masz {symbol} ({balance}), pomijam zakup.")
                return

            if change <= -0.5:
                usdc_part = usdc_balance / CAPITAL_SPLIT
                qty = round_step_size(usdc_part / close_price, step)

                if qty >= min_qty:
                    client.order_market_buy(symbol=pair, quantity=qty)
                    positions[pair] = close_price
                    save_positions()
                    print(f"[{pair}] 🟢 Kupno {qty} po {close_price:.2f}")
                else:
                    print(f"[{pair}] ❗ Ilość {qty} < minQty {min_qty}, pomijam zakup.")

    except BinanceAPIException as e:
        print(f"Błąd Binance ({pair}): {e}")
    except Exception as e:
        print(f"Inny błąd ({pair}): {e}")

# Główna pętla
while True:
    try:
        usdc_balance = float(client.get_asset_balance(asset='USDC')["free"])
        print(f"\n💰 Saldo USDC: {usdc_balance:.2f}")

        for pair in PAIRS:
            trade(pair, usdc_balance)

        print("⏳ Czekam...")
        time.sleep(TRADE_INTERVAL)

    except KeyboardInterrupt:
        print("⛔ Zatrzymano bota.")
        break
    except Exception as e:
        print(f"Błąd główny: {e}")
