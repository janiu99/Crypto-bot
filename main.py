            if profit >= adjusted_tp or profit <= -1.5:
                if balance >= min_qty:
                    qty = round_step_size(balance, step)
                    client.order_market_sell(symbol=pair, quantity=qty)
                    print(f"[{pair}] {'✅ Zysk' if profit >= adjusted_tp else '🚩 STOP-LOSS'}: {profit:.2f}% (TP: {adjusted_tp:.2f}%)")
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
                    print(f"[{pair}] \U0001f7e2 Kupno {qty} po {close_price:.2f}")
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
