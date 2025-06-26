import os
import time
import csv
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException

# API z Railway (zmienne środowiskowe)
API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')

# Parametry
TRADE_INTERVAL = 60  # sekundy między cyklami
BUY_DROP = -0.5      # % spadku do zakupu
TP = 0.9             # Take Profit w %
SL = 1.0             # Stop Loss w %
EMA_PERIOD = 50
FEE = 0.075 / 100    # opłata taker (0.075%)

# Pary do handlu
PAIRS = ['BTCUSDC', 'ETHUSDC', 'BNBUSDC', 'FLUXUSDC']
positions = {}

# Inicjalizacja klienta Binance
client = Client(API_KEY, API_SECRET)

# Pobieranie filtrów z Binance (step, minQty, minNotional)
def get_pair_filters():
    info = client.get_exchange_info()
    filters = {}
    for symbol in info['symbols']:
        if symbol['symbol'] in PAIRS:
            f = {filt['filterType']: filt for filt in symbol['filters']}
            filters[symbol['symbol']] = {
                'min_qty': float(f['LOT_SIZE']['minQty']),
                'step': float(f['LOT_SIZE']['stepSize']),
                'min_notional': float(f['MIN_NOTIONAL']['minNotional']),
            }
    return filters

PAIR_FILTERS = get_pair_filters()

# Zaokrąglanie ilości do stepSize
def round_step_size(quantity, step):
    return float(np.floor(quantity / step) * step)

# Logowanie transakcji
def log_trade(pair, entry_price, exit_price, profit_percent):
    with open('trade_log.csv', 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), pair, entry_price, exit_price, round(profit_percent, 3)])

# Główna funkcja handlu
def trade(pair, usdc_balance):
    try:
        # Dane historyczne do EMA i ceny
        klines = client.get_klines(symbol=pair, interval=Client.KLINE_INTERVAL_1MINUTE, limit=EMA_PERIOD + 2)
        closes = [float(k[4]) for k in klines]
        close_price = closes[-1]
        price_change = (close_price - closes[-2]) / closes[-2] * 100

        min_qty = PAIR_FILTERS[pair]['min_qty']
        step = PAIR_FILTERS[pair]['step']
        min_notional = PAIR_FILTERS[pair]['min_notional']

        # Jeżeli mamy pozycję
        if pair in positions:
            entry_price = positions[pair]['entry']
            qty = positions[pair]['qty']
            profit = (close_price - entry_price) / entry_price * 100 - 2 * FEE * 100

            if profit >= TP or profit <= -SL:
                if qty >= min_qty:
                    client.order_market_sell(symbol=pair, quantity=qty)
                    log_trade(pair, entry_price, close_price, profit)
                    print(f"[{pair}] ✅ Zakończono: {profit:.2f}% (TP: {TP}%, SL: {-SL}%)")
                    del positions[pair]
                else:
                    print(f"[{pair}] ⚠️ Ilość zbyt mała do sprzedaży: {qty}")
            else:
                print(f"[{pair}] 📈 Pozycja otwarta: {profit:.2f}%")

        # Jeżeli nie mamy pozycji i cena spadła
        else:
            if price_change <= BUY_DROP:
                usdc_part = usdc_balance / len(PAIRS)
                qty = round_step_size(usdc_part / close_price, step)
                notional = qty * close_price

                if qty >= min_qty and notional >= min_notional:
                    client.order_market_buy(symbol=pair, quantity=qty)
                    positions[pair] = {'entry': close_price, 'qty': qty}
                    print(f"[{pair}] 🟢 Kupiono {qty} po {close_price:.4f} USDC")
                else:
                    print(f"[{pair}] ❌ Za niska wartość transakcji ({notional:.2f} USDC), wymagane >= {min_notional}")
            else:
                print(f"[{pair}] ⏸️ Spadek za mały: {price_change:.2f}%")

    except BinanceAPIException as e:
        print(f"[{pair}] ❗ Błąd Binance: {e}")
    except Exception as e:
        print(f"[{pair}] ❗ Błąd ogólny: {e}")

# Pętla główna
while True:
    try:
        usdc_balance = float(client.get_asset_balance(asset='USDC')["free"])
        print(f"\n💰 Saldo USDC: {usdc_balance:.2f}")

        for pair in PAIRS:
            trade(pair, usdc_balance)

        print("⏳ Czekam...")
        time.sleep(TRADE_INTERVAL)

    except KeyboardInterrupt:
        print("⛔ Bot zatrzymany.")
        break
    except Exception as e:
        print(f"❗ Błąd główny: {e}")
        time.sleep(5)
