import ccxt
import time
import threading
import pytz
import json
from datetime import datetime, timezone
from telegram import Bot
import requests

# Binance API anahtarları
api_key = ''
secret_key = ''

# Global değişkenler
binance = None  # Başlangıçta None olarak tanımlanır
bought_coins = {}  # Satın alınan coinlerin listesi
sold_coins = {}  # Satılan coinlerin listesi
unsold_coins = {}  # Satılmamış coinlerin listesi

# Alım ve satım işlemleri için kilitler
buy_lock = threading.Lock()
sell_lock = threading.Lock()

# Telegram Bot API token ve chat ID
telegram_api_token = ''
chat_id = ''


# Telegram Bot nesnesi
bot = Bot(token=telegram_api_token)

def send_telegram_message_sync(message):
    """
    Telegram üzerinden belirli bir kullanıcıya mesaj gönderir.
    """
    try:
        url = f'https://api.telegram.org/bot{telegram_api_token}/sendMessage'
        payload = {
            'chat_id': chat_id,
            'text': message
        }
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print_with_timestamp(f"Telegram mesajı gönderilirken hata: {response.text}")
    except Exception as e:
        print_with_timestamp(f"Telegram mesajı gönderilirken hata: {e}")

def connect_to_binance():
    """
    Sağlanan API anahtarları ile Binance API'sine bağlanır.
    """
    return ccxt.binance({
        'apiKey': api_key,
        'secret': secret_key,
        'enableRateLimit': True,
        'timeout': 5000,  # Timeout 5 saniye olarak ayarlandı
    })

def print_with_timestamp(message):
    """
    Verilen mesajı tarih ve saat bilgisiyle birlikte yazdırır.
    """
    turkey_tz = pytz.timezone('Europe/Istanbul')
    now = datetime.now(turkey_tz)
    print(f"{now.isoformat()}: {message}")

def check_binance_connection():
    """
    Binance bağlantısının sağlıklı olup olmadığını kontrol eder.
    """
    try:
        binance.fetch_time()
        print_with_timestamp("Binance bağlantısı sağlıklı.")
        return True
    except (ccxt.NetworkError, ccxt.ExchangeError) as e:
        print_with_timestamp(f"Bağlantı hatası: {e}")
        return False

def reconnect_to_binance():
    """
    Binance bağlantısı kesildiğinde yeniden bağlanmayı dener.
    """
    global binance
    while True:
        print_with_timestamp("Binance bağlantısı kesildi. Yeniden bağlanmayı deniyor...")
        try:
            binance = connect_to_binance()
            if check_binance_connection():
                print_with_timestamp("Binance bağlantısı yeniden kuruldu.")
                return
        except Exception as e:
            print_with_timestamp(f"Yeniden bağlanma denemesi başarısız: {e}")
        time.sleep(10)  # Tekrar denemeden önce bekleme

def get_active_usdt_pairs():
    """
    Aktif USDT paritelerini alır.
    """
    try:
        markets = binance.load_markets()
        active_usdt_pairs = [symbol for symbol in markets if symbol.endswith('/USDT') and markets[symbol]['active']]
        return active_usdt_pairs
    except ccxt.BaseError as e:
        print_with_timestamp(f"Aktif USDT pariteleri alınırken hata oluştu: {e}")
        return []

def calculate_amount(price, min_notional):
    """
    Belirli bir fiyata göre alınacak miktarı hesaplar.
    """
    usd_amount = 10
    amount = usd_amount / price
    if amount * price < min_notional:
        amount = min_notional / price
    return amount

def save_bought_coins(bought_coins):
    """
    Satın alınan coinlerin listesini bir dosyaya kaydeder.
    """
    with open('bought_coins.json', 'w') as file:
        json.dump(bought_coins, file, indent=4, ensure_ascii=False, sort_keys=True)

def load_bought_coins():
    """
    Satın alınan coinlerin listesini bir dosyadan yükler.
    """
    try:
        with open('bought_coins.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def clear_bought_coins():
    """
    Satın alınan coinlerin listesini sıfırlar.
    """
    empty_data = {}
    with open('bought_coins.json', 'w') as file:
        json.dump(empty_data, file)

def clear_sold_coins():
    """
    Satılan coinlerin listesini sıfırlar.
    """
    empty_data = {}
    with open('sold_coins.json', 'w') as file:
        json.dump(empty_data, file)

def save_sold_coins(sold_coins):
    """
    Satılan coinlerin listesini bir dosyaya kaydeder.
    """
    with open('sold_coins.json', 'w') as file:
        json.dump(sold_coins, file, indent=4, ensure_ascii=False, sort_keys=True)

def load_sold_coins():
    """
    Satılan coinlerin listesini bir dosyadan yükler.
    """
    try:
        with open('sold_coins.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def get_min_notional(symbol):
    """
    Belirli bir sembol için minimum işlem değerini döndürür.
    """
    try:
        exchange_info = binance.load_markets()
        return exchange_info[symbol]['limits']['cost']['min']
    except ccxt.BaseError as e:
        print_with_timestamp(f"{symbol} için minimum işlem değeri alınırken hata oluştu: {e}")
        return None

def get_volume_threshold(daily_volume):
    """
    Hacim eşiklerini kontrol eder ve önceden tanımlanmış hacim seviyelerine göre bir eşik döndürür.
    """
    volume_thresholds = [(10000000, 115000)]
    for threshold, minute_volume in volume_thresholds:
        if daily_volume < threshold:
            return minute_volume
    return None

def is_green_candle(symbol, threshold):
    """
    Verilen sembol için son iki mumun yeşil olup olmadığını kontrol eder.
    """
    try:
        candles = binance.fetch_ohlcv(symbol, timeframe='1m', limit=2)
        if len(candles) < 2:
            print_with_timestamp(f"{symbol} için yeterli mum verisi yok")
            return False, None
        prev_candle = candles[-2]
        curr_candle = candles[-1]
        open_price = curr_candle[1]
        close_price = prev_candle[4]
        volume = prev_candle[5] * close_price
        return close_price > prev_candle[1] and volume > threshold, open_price
    except ccxt.RequestTimeout:
        print_with_timestamp(f"{symbol} için mum verileri alınırken zaman aşımı")
    except ccxt.BaseError as e:
        print_with_timestamp(f"{symbol} için mum verileri alınırken hata oluştu: {e}")
    return False, None

def buy_coin(symbol, amount):
    """
    Belirli bir miktarda coin almak için alım emri verir ve bakiyeyi günceller.
    """
    try:
        order = binance.create_market_buy_order(symbol, amount)
        buy_price = order['price']
        buy_time = datetime.now().isoformat()
        message = f"{symbol} için {amount} miktarda alım yapıldı. Fiyat: {buy_price}, Zaman: {buy_time}"
        print_with_timestamp(message)
        send_telegram_message_sync(message)
        usdt_balance = binance.fetch_balance()['USDT']['free']
        print_with_timestamp(f"{symbol} alımından sonra güncel USDT bakiyesi: {usdt_balance}")
        return usdt_balance
    except ccxt.InsufficientFunds:
        print_with_timestamp(f"{symbol} almak için yetersiz bakiye")
    except ccxt.BaseError as e:
        print_with_timestamp(f"{symbol} alımı sırasında hata oluştu: {e}")
    return None

def get_coin_info(symbol):
    """
    Belirli bir coin için piyasa bilgilerini ve günlük değişim yüzdesini alır.
    """
    try:
        ticker = binance.fetch_ticker(symbol)
        price_change_percent = float(ticker['info']['priceChangePercent'])
        last_price = float(ticker['last'])
        volume = float(ticker['quoteVolume'])
        print_with_timestamp(f"Coin: {symbol} | Son Fiyat: {last_price:.2f} | Günlük Değişim: {price_change_percent:.2f}% | Günlük Hacim: {volume}")
        return {
            'symbol': symbol,
            'last_price': last_price,
            'price_change_percent': price_change_percent,
            'volume': volume
        }
    except ccxt.BaseError as e:
        print_with_timestamp(f"{symbol} için coin bilgisi alınırken hata oluştu: {e}")
        return None

def check_pending_orders():
    """
    Binance'daki açık limit emirlerini kontrol eder.
    """
    try:
        open_orders = binance.fetch_open_orders()
        pending_coins = {order['symbol'] for order in open_orders if order['status'] == 'open'}
        return pending_coins
    except ccxt.BaseError as e:
        print_with_timestamp(f"Açık emirler alınırken hata oluştu: {e}")
        return set()

def filter_coins_by_percentage_and_volume(tickers, threshold_percentage=1.0, min_volume=125000, max_volume=10000000):
    """
    Belirli bir değişim yüzdesi ve hacim aralığına göre coinleri filtreler.
    """
    significant_coins = []
    for symbol, ticker in tickers.items():
        price_change_percent = float(ticker['info']['priceChangePercent'])
        volume = float(ticker['quoteVolume'])
        if price_change_percent >= threshold_percentage and min_volume <= volume <= max_volume:
            print_with_timestamp(f"{symbol} için önemli değişim tespit edildi: {price_change_percent:.2f}% | Hacim: {volume}")
            significant_coins.append(symbol)
    return significant_coins

def monitor_price_change_percentage(tickers, threshold_percentage=1.0):
    """
    Coinlerin günlük değişim bilgilerini ve hacimlerini kontrol eder ve belirtilen eşiği geçenleri listeler.
    """
    filtered_coins = filter_coins_by_percentage_and_volume(tickers, threshold_percentage)
    return filtered_coins

def get_filtered_coins(active_usdt_pairs, threshold_percentage=1.0):
    """
    Aktif USDT paritelerini alır ve belirli hacim ve değişim yüzdesi eşiklerini karşılayanları filtreler.
    """
    filtered_coins = []
    try:
        tickers = binance.fetch_tickers(active_usdt_pairs)
        significant_coins = monitor_price_change_percentage(tickers, threshold_percentage)
        for coin in significant_coins:
            ticker = tickers[coin]
            volume = ticker['quoteVolume']
            threshold = get_volume_threshold(volume)
            if threshold:
                filtered_coins.append((coin, threshold))
    except ccxt.BaseError as e:
        print_with_timestamp(f"get_filtered_coins fonksiyonunda hata: {e}")
    return filtered_coins

def monitor_buy_conditions(threshold_percentage=1.0):
    """
    Alım koşullarını sürekli kontrol eder ve uygun olduğunda alım yapar.
    """
    global bought_coins, unsold_coins
    active_usdt_pairs = get_active_usdt_pairs()
    while True:
        try:
            filtered_coins = get_filtered_coins(active_usdt_pairs, threshold_percentage)
            for coin, threshold in filtered_coins:
                if coin not in bought_coins and coin not in sold_coins:
                    is_green, open_price = is_green_candle(coin, threshold)
                    if is_green:
                        with buy_lock:
                            usdt_balance = binance.fetch_balance()['USDT']['free']
                            min_notional = get_min_notional(coin)
                            amount = calculate_amount(open_price, min_notional)
                            if usdt_balance >= amount * open_price:
                                new_balance = buy_coin(coin, amount)
                                if new_balance is not None:
                                    bought_coins[coin] = {
                                        'buy_price': open_price,
                                        'buy_time': datetime.now(timezone.utc).isoformat(),
                                        'amount': amount
                                    }
                                    unsold_coins[coin] = bought_coins[coin]
                                    save_bought_coins(bought_coins)
                                    usdt_balance = new_balance
                                    
                                    # Alımdan sonra take-profit emri oluştur
                                    take_profit_price = open_price * 1.025  # %2.5 kar hedefi
                                    stop_loss_price = open_price * 0.95    # %5 zarar durdurma
                                    
                                    # Satış işlemini yönet
                                    manage_sell(coin, amount, stop_loss_price, take_profit_price)
        except Exception as e:
            print_with_timestamp(f"monitor_buy_conditions fonksiyonunda hata: {e}")
        time.sleep(2)

def manage_sell(coin, amount, stop_loss_price, take_profit_price):
    """
    Coin için take-profit limit satış emri oluşturur ve gerekli bilgileri kaydeder.
    """
    try:
        with sell_lock:
            open_orders = binance.fetch_open_orders(symbol=coin)
            # Coin için zaten satış emri varsa yeni emir oluşturma
            if any(order['symbol'] == coin and order['side'] == 'sell' for order in open_orders):
                print_with_timestamp(f"{coin} için zaten satış emri var, yeni emir oluşturulmayacak.")
                return None
    
            market = binance.markets[coin]
             # Miktarın hassasiyetini al
            amount_precision = market['precision']['amount']
            # Miktarı piyasanın hassasiyetine göre ayarla
            amount = float(binance.amount_to_precision(coin, amount))
            min_amount = market['limits']['amount']['min']
            min_notional = market['limits']['cost']['min']
    
            # Mevcut bakiyeyi al
            balance = binance.fetch_balance()
            symbol_base = coin.split('/')[0]
            available_amount = balance[symbol_base]['free']
    
            # Miktarı mevcut bakiyeye göre ayarla
            amount = min(amount, available_amount)
            amount = float(binance.amount_to_precision(coin, amount))
    
            # Miktarın minimum miktardan az olup olmadığını kontrol et
            if amount < min_amount:
                print_with_timestamp(f"Miktar {amount}, {coin} için minimum miktar {min_amount}'dan az.")
                print_with_timestamp(f"{coin} için satış işlemi yapılamıyor.")
                return None
    
            # Toplam işlem değerini hesapla
            total = amount * take_profit_price
    
            # Minimum notional kontrolü
            if total < min_notional:
                print_with_timestamp(f"İşlem tutarı {total}, {coin} için minimum notional değeri {min_notional}'dan az.")
                print_with_timestamp(f"{coin} için satış işlemi yapılamıyor.")
                return None
    
            # Take-profit limit satış emri oluştur
            take_profit_order = binance.create_limit_sell_order(coin, amount, take_profit_price)
            print_with_timestamp(f"{coin} için take-profit emri oluşturuldu: {take_profit_order}")
            
            # Telegram'a mesaj gönder
            message = f"{coin} için Take-Profit emri oluşturuldu. Fiyat: {take_profit_price}"
            send_telegram_message_sync(message)
    
            # unsold_coins listesine ek bilgileri kaydet
            if coin not in unsold_coins:
                unsold_coins[coin] = {}
            unsold_coins[coin]['take_profit_order_id'] = take_profit_order['id']
            unsold_coins[coin]['stop_loss_price'] = stop_loss_price
            unsold_coins[coin]['take_profit_price'] = take_profit_price
            unsold_coins[coin]['amount'] = amount  # Eksikse ekleyelim
            save_bought_coins(bought_coins)
    
    except Exception as e:
        print_with_timestamp(f"{coin} için manage_sell fonksiyonunda hata: {e}")
    return None

def handle_order_filled(order_id, coin, order_type):
    """
    Bir emrin tetiklenmesi durumunda yapılacak işlemleri gerçekleştirir.
    """
    try:
        order_info = binance.fetch_order(order_id, symbol=coin)
        sell_amount = order_info['filled']
        sell_price = order_info['average']
        sell_time = datetime.now().isoformat()
        message = f"{coin} için {order_type} satışı gerçekleşti. Miktar: {sell_amount}, Fiyat: {sell_price}, Zaman: {sell_time}"
        send_telegram_message_sync(message)
        print_with_timestamp(f"{coin} için {order_type} emri tetiklendi.")
        
        # Satılan coinleri güncelle
        sold_coins[coin] = {
            'sell_price': sell_price,
            'sell_time': sell_time,
            'amount': sell_amount
        }
        save_sold_coins(sold_coins)
        
        # unsold_coins ve bought_coins listesinden çıkar
        if coin in unsold_coins:
            del unsold_coins[coin]
        if coin in bought_coins:
            del bought_coins[coin]
            save_bought_coins(bought_coins)
    except Exception as e:
        print_with_timestamp(f"{coin} için handle_order_filled fonksiyonunda hata: {e}")

def monitor_all_orders():
    """
    Tüm coinlerin fiyatlarını ve emir durumlarını izler.
    """
    global unsold_coins, sold_coins
    while True:
        try:
            # unsold_coins listesi boşsa devam etme
            if not unsold_coins:
                time.sleep(2)
                continue
            
            # İzlenen coinlerin sembollerini al
            symbols_to_monitor = list(unsold_coins.keys())
            
            # Tüm coinlerin fiyatlarını tek bir sorguyla al
            tickers = binance.fetch_tickers(symbols_to_monitor)
            
            for coin in symbols_to_monitor:
                # Coin'in mevcut fiyatını al
                if coin in tickers:
                    current_price = tickers[coin]['last']
                else:
                    print_with_timestamp(f"{coin} için fiyat bilgisi alınamadı.")
                    continue
                
                # Coin için açık emirleri sembol belirterek al
                coin_open_orders = []
                try:
                    coin_open_orders = binance.fetch_open_orders(symbol=coin)
                    # API oran sınırlamalarına dikkat etmek için kısa bir bekleme ekleyelim
                    time.sleep(0.2)
                except ccxt.BaseError as e:
                    print_with_timestamp(f"{coin} için açık emirler alınırken hata oluştu: {e}")
                    continue
                
                # Take-profit emrini kontrol et
                take_profit_order_id = unsold_coins[coin].get('take_profit_order_id')
                take_profit_order_exists = any(order['id'] == take_profit_order_id for order in coin_open_orders)
                
                # Eğer take-profit emri tetiklenmişse
                if not take_profit_order_exists and take_profit_order_id:
                    # Satış işlemini gerçekleştir
                    handle_order_filled(take_profit_order_id, coin, 'Take-Profit')
                    continue  # Bu coin için sonraki döngüye geç
                
                # Fiyat stop-loss seviyesine düştüyse
                stop_loss_price = unsold_coins[coin].get('stop_loss_price')
                if stop_loss_price is None:
                    print_with_timestamp(f"{coin} için 'stop_loss_price' değeri bulunamadı.")
                    # unsold_coins listesinden coin'i çıkarın çünkü gerekli veriler yok
                    unsold_coins.pop(coin, None)
                    continue  # Veya gerekli işlemi yapabilirsiniz
                
                if current_price <= stop_loss_price and take_profit_order_exists:
                    print_with_timestamp(f"{coin} için fiyat stop-loss seviyesine ulaştı ({current_price} <= {stop_loss_price}).")
                    # Take-profit emrini iptal et
                    binance.cancel_order(take_profit_order_id, symbol=coin)
                    print_with_timestamp(f"{coin} için take-profit emri iptal edildi.")
                    
                    # Stop-loss emri oluştur
                    amount = unsold_coins[coin]['amount']
                    amount = float(binance.amount_to_precision(coin, amount))
                    stop_loss_order = binance.create_limit_sell_order(coin, amount, stop_loss_price)
                    print_with_timestamp(f"{coin} için stop-loss emri oluşturuldu.")
                    
                    # Stop-loss emrinin ID'sini kaydet
                    unsold_coins[coin]['stop_loss_order_id'] = stop_loss_order['id']
                    save_bought_coins(bought_coins)
                    
                    # Stop-loss emrini izlemeye başla
                    monitor_stop_loss_order(coin)
                    continue  # Bu coin için sonraki döngüye geç
                
                # Stop-loss emrini kontrol et
                stop_loss_order_id = unsold_coins[coin].get('stop_loss_order_id')
                if stop_loss_order_id:
                    stop_loss_order_exists = any(order['id'] == stop_loss_order_id for order in coin_open_orders)
                    
                    if not stop_loss_order_exists:
                        # Stop-loss emri tetiklenmiş
                        handle_order_filled(stop_loss_order_id, coin, 'Stop-Loss')
                        continue  # Bu coin için sonraki döngüye geç
                
                # Her coin için API çağrıları arasında bekleme ekleyerek oran sınırlamalarına dikkat edin
                time.sleep(0.1)
        except Exception as e:
            print_with_timestamp(f"monitor_all_orders fonksiyonunda hata: {e}")
        
        time.sleep(2)  # Döngü sonunda bekleme süresi


def monitor_stop_loss_order(coin):
    """
    Stop-loss limit satış emrini izler ve tetiklendiğinde coin'in durumunu günceller.
    """
    try:
        stop_loss_order_id = unsold_coins[coin].get('stop_loss_order_id')
        if not stop_loss_order_id:
            return
        while True:
            try:
                # Coin için açık emirleri sembol belirterek al
                coin_open_orders = binance.fetch_open_orders(symbol=coin)
                # API oran sınırlamalarına dikkat etmek için kısa bir bekleme ekleyelim
                time.sleep(0.2)
            except ccxt.BaseError as e:
                print_with_timestamp(f"{coin} için açık emirler alınırken hata oluştu: {e}")
                continue

            stop_loss_order_exists = any(order['id'] == stop_loss_order_id for order in coin_open_orders)
    
            # Stop-loss emri tetiklendiyse
            if not stop_loss_order_exists:
                # Stop-loss emri tetiklenmiş
                handle_order_filled(stop_loss_order_id, coin, 'Stop-Loss')
                break  # Döngüden çık

            # Her kontrol arasında bekleme ekleyerek oran sınırlamalarına dikkat edin
            time.sleep(2)
    except Exception as e:
        print_with_timestamp(f"{coin} için monitor_stop_loss_order fonksiyonunda hata: {e}")

def main():
    """
    Ana işlem döngüsü, Binance bağlantısını kurar ve izleme thread'lerini başlatır.
    """
    global binance
    try:
        binance = connect_to_binance()
        if not check_binance_connection():
            reconnect_to_binance()
    except Exception as e:
        print_with_timestamp(f"Başlangıçta bağlantı hatası: {e}")
        reconnect_to_binance()
    clear_bought_coins()
    clear_sold_coins()
    global bought_coins, sold_coins, unsold_coins
    bought_coins = load_bought_coins()
    sold_coins = load_sold_coins()
    unsold_coins = {coin: info for coin, info in bought_coins.items() if coin not in sold_coins}
    
    # Alım işlemleri için thread başlat
    buy_thread = threading.Thread(target=monitor_buy_conditions)
    buy_thread.start()
    
    # Tüm coinlerin izlenmesi için thread başlat
    monitor_thread = threading.Thread(target=monitor_all_orders)
    monitor_thread.start()
    
    buy_thread.join()
    monitor_thread.join()

if __name__ == "__main__":
    main()
