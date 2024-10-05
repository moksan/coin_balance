import ccxt
import time
import threading
import pytz
import json
from datetime import datetime, timezone
from telegram import Bot
import asyncio
from telegram.ext import ApplicationBuilder
import requests

# Binance API anahtarlarınızı buraya girin
api_key = 'btsxFPi17RUleIPxWgag6Km0RsIiNnOxDkg3D84GwLVdG9EbisSTzGU1gaXv8xzB'
secret_key = 'VTUuDpKDPNKb6dOft7dpqzodtLXUGTiSObUYvDISiY6tmLmrdHgDAxIf824qbr1l'

# Global değişken olarak binance değişkenini tanımlayın
binance = None  # Başlangıçta None olarak tanımlanır
bought_coins = {}  # Satın alınan coinlerin listesi
sold_coins = {}  # Satılmış coinlerin listesi
unsold_coins = {}  # Satılmamış coinlerin listesi

# Alış ve satış işlemlerini yönetmek için kilitler (locks)+
buy_lock = threading.Lock()
sell_lock = threading.Lock()


# Telegram Bot API token ve chat ID'nizi girin
telegram_api_token = #'7289217723:AAEAjoHDoTuBysblDsefb9aZ5QDsGPZwpv8'
chat_id = #'7503089535'
app = ApplicationBuilder().token(telegram_api_token).build()

# Telegram Bot nesnesini oluşturun
bot = Bot(token=telegram_api_token)

# async  def send_telegram_message(message):
#     """
#     Telegram üzerinden belirli bir kullanıcıya mesaj gönderir.
#     """
#     try:
#         await app.bot.send_message(chat_id=chat_id, text=message)
#     except Exception as e:
#         print_with_timestamp(f"Error sending message to Telegram: {e}")

# def send_telegram_message_sync(message):
#     """
#     send_telegram_message fonksiyonunu senkron olarak çalıştırır.
#     """
#     try:
#         # Eğer mevcut bir olay döngüsü yoksa yeni bir tane oluştur
#         if not asyncio.get_event_loop().is_running():
#             new_loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(new_loop)
#             new_loop.run_until_complete(send_telegram_message(message))
#             # Olay döngüsünü kapatma
#         else:
#             # Eğer mevcut olay döngüsü varsa, mevcut olanı kullan
#             asyncio.run(send_telegram_message(message))
#     except Exception as e:
#         print_with_timestamp(f"Error sending message to Telegram: {e}")

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
            print_with_timestamp(f"Error sending message to Telegram: {response.text}")
    except Exception as e:
        print_with_timestamp(f"Error sending message to Telegram: {e}")

def connect_to_binance():
    """
    Binance API'sine bağlantı kurar ve gerekli kimlik doğrulama bilgilerini kullanarak bağlantıyı yapılandırır.
    """
    return ccxt.binance({
        'apiKey': api_key,
        'secret': secret_key,
        'enableRateLimit': True,
        'timeout': 5000,  # Timeout değeri 5 saniye olarak ayarlandı
    })

def print_with_timestamp(message):
    """
    Belirtilen mesajı tarih ve saat bilgisiyle birlikte yazdırır.
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
    Binance bağlantısı kesildiğinde tekrar bağlantı kurmayı dener.
    """
    global binance
    while True:
        print_with_timestamp("Binance bağlantısı kopmuş. Yeniden bağlanmayı deniyor...")
        try:
            binance = connect_to_binance()
            if check_binance_connection():
                print_with_timestamp("Binance bağlantısı başarıyla kuruldu.")
                return
        except Exception as e:
            print_with_timestamp(f"Yeniden bağlanma denemesi başarısız: {e}")
        time.sleep(10)  # Yeniden bağlanma denemeleri arasında bekleme süresi

def get_active_usdt_pairs():
    """
    Aktif USDT paritelerini getirir.
    """
    try:
        markets = binance.load_markets()
        active_usdt_pairs = [symbol for symbol in markets if symbol.endswith('/USDT') and markets[symbol]['active']]
        return active_usdt_pairs
    except ccxt.BaseError as e:
        print_with_timestamp(f"An error occurred while fetching active USDT pairs: {e}")
        return []

def calculate_amount(price, min_notional):
    """
    Belirli bir fiyata göre alınacak miktarı hesaplar.
    """
    usd_amount = 15
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
        print_with_timestamp(f"An error occurred while fetching notional value for {symbol}: {e}")
        return None
    
def get_volume_threshold(daily_volume):
    """
    Hacim eşiklerini kontrol eder ve belirlenen hacim seviyelerine göre bir eşik döndürür.
    """
    volume_thresholds = [(10000000, 125000)]
    for threshold, minute_volume in volume_thresholds:
        if daily_volume < threshold:
            return minute_volume
    return None


def is_green_candle(symbol, threshold):
    """
    Verilen sembol için son iki mum çubuğunun durumunu kontrol eder ve yeşil mum olup olmadığını kontrol eder.
    """
    try:
        candles = binance.fetch_ohlcv(symbol, timeframe='1m', limit=2)
        if len(candles) < 2:
            print_with_timestamp(f"Not enough candle data for {symbol}")
            return False, None
        prev_candle = candles[-2]
        curr_candle = candles[-1]
        open_price = curr_candle[1]
        close_price = prev_candle[4]
        volume = prev_candle[5] * close_price
        return close_price > prev_candle[1] and volume > threshold, open_price
    except ccxt.RequestTimeout:
        print_with_timestamp(f"Request timeout while fetching candle data for {symbol}")
    except ccxt.BaseError as e:
        print_with_timestamp(f"An error occurred while fetching candle data for {symbol}: {e}")
    return False, None


def buy_coin(symbol, amount):
    """
    Verilen miktarda coin alım işlemi yapar ve bakiyeyi günceller.
    """
    try:
        order = binance.create_market_buy_order(symbol, amount)
        buy_price = order['price']
        buy_time = datetime.now().isoformat()
        message = f"Bought {amount} of {symbol} at {buy_price} on {buy_time}"
        print_with_timestamp(message)
        #asyncio.run(send_telegram_message(message))
        send_telegram_message_sync(message)
        usdt_balance = binance.fetch_balance()['USDT']['free']
        print_with_timestamp(f"Updated USDT balance after buying {symbol}: {usdt_balance}")
        return usdt_balance
    except ccxt.InsufficientFunds:
        print_with_timestamp(f"Insufficient funds to buy {symbol}")
    except ccxt.BaseError as e:
        print_with_timestamp(f"An error occurred while buying {symbol}: {e}")
    return None


#def execute_sell(coin, amount):
def execute_sell(coin, amount,sell_price):

    """
    Verilen miktarda coin satım işlemi yapar ve satım işlemi sonrası USDT bakiyesini döndürür.
    """
    try:
        market = binance.markets[coin]
        precision = market['precision']['amount']
        amount = round(amount, int(precision))
        min_amount = market['limits']['amount']['min']
        
        # Minimum miktar kontrolü
        if amount < min_amount:
            print_with_timestamp(f"Amount {amount} is less than minimum allowed {min_amount} for {coin}. Adjusting amount to minimum.")
            amount = min_amount

        balance = binance.fetch_balance()
        symbol_base = coin.split('/')[0]
        available_amount = balance[symbol_base]['free']
        if amount > available_amount:
            print_with_timestamp(f"Not enough balance to sell {amount} of {coin}. Available: {available_amount}")
            amount = available_amount

        # Satış işlemi
#        sell_result = binance.create_market_sell_order(coin, amount)
        sell_result = binance.create_limit_sell_order(coin, amount, sell_price)
        sell_price = sell_result['price']
        print_with_timestamp(f"Sold {amount} of {coin}")
        sell_time = datetime.now().isoformat()
        message = f"Sold {amount} of {coin} at {sell_price} on {sell_time}"
        #asyncio.run(send_telegram_message(message))
        send_telegram_message_sync(message)
        sell_usdt_balance = binance.fetch_balance()['USDT']['free']
        print_with_timestamp(f"Updated USDT balance after selling {coin}: {sell_usdt_balance}")
        return sell_usdt_balance
    
    except ccxt.InsufficientFunds as e:
        print_with_timestamp(f"Insufficient funds to sell {coin}: {e}")
    except ccxt.NetworkError as e:
        print_with_timestamp(f"Network error while selling {coin}: {e}")
        time.sleep(10)  # Ağ hatası durumunda biraz bekleyip tekrar denemek için
    except ccxt.BaseError as e:
        print_with_timestamp(f"An unexpected error occurred while selling {coin}: {e}")
    except Exception as e:
        print_with_timestamp(f"An unknown error occurred: {e}")
    return None

# def manage_sell(coin, amount, stop_loss_price, take_profit_price):
#     """
#     Coin'in stop-loss veya kâr alım seviyelerine ulaşıp ulaşmadığını kontrol eder ve gerekiyorsa satış yapar.
#     """
#     try:
#         ticker = binance.fetch_ticker(coin)
#         current_price = ticker['last'] if ticker['last'] is not None else ticker['close']
        
#         # Stop-Loss kontrolü
#         if current_price <= stop_loss_price:
#             print_with_timestamp(f"Stop-Loss triggered for {coin}. Current Price: {current_price}, Stop-Loss Price: {stop_loss_price}")
#             #return execute_sell(coin, amount)
#             return execute_sell(coin, amount,stop_loss_price)
#         # Kâr Alım kontrolü
#         elif current_price >= take_profit_price:
#             print_with_timestamp(f"Take-Profit triggered for {coin}. Current Price: {current_price}, Take-Profit Price: {take_profit_price}")
#             #return execute_sell(coin, amount)
#             return execute_sell(coin, amount,take_profit_price)
#         else:
#             print_with_timestamp(f"Holding {coin}. Current Price: {current_price}, Stop-Loss Price: {stop_loss_price}, Take-Profit Price: {take_profit_price}")

#     except ccxt.RequestTimeout:
#         print_with_timestamp(f"Request timeout while managing sell for {coin}. Retrying...")
#     except ccxt.BaseError as e:
#         print_with_timestamp(f"An error occurred while managing sell for {coin}: {e}")
#     except Exception as e:
#         print_with_timestamp(f"An unknown error occurred: {e}")
    
#     return None
def create_take_profit_order(symbol, amount, take_profit_price):
    """
    Take-Profit limiti ile satış emri oluşturur.
    """
    try:
        order = binance.create_limit_sell_order(symbol, amount, take_profit_price)
        print_with_timestamp(f"Take-Profit emri oluşturuldu: {order}")
        return order
    except ccxt.BaseError as e:
        print_with_timestamp(f"Take-Profit emri oluşturulurken hata oluştu: {e}")
        return None

def create_stop_loss_order(symbol, amount, stop_loss_price, stop_loss_limit_price):
    """
    Stop-Loss limiti ile satış emri oluşturur.
    """
    try:
        order = binance.create_order(symbol, 'limit', 'sell', amount, stop_loss_limit_price, {
            'stopPrice': stop_loss_price  # Stop-Loss tetikleyici fiyat
        })
        print_with_timestamp(f"Stop-Loss emri oluşturuldu: {order}")
        return order
    except ccxt.BaseError as e:
        print_with_timestamp(f"Stop-Loss emri oluşturulurken hata oluştu: {e}")
        return None


def get_coin_info(symbol):
    """
    Belirli bir coin için piyasa bilgisini ve günlük değişim yüzdesini getirir.
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
        print_with_timestamp(f"An error occurred while fetching coin info for {symbol}: {e}")
        return None

def check_pending_orders():
    """
    Binance üzerinde bekleyen (open) limit emirleri kontrol eder.
    Eğer bekleyen emir varsa, o coini tekrar işlem yapmadan beklemeye alır.
    """
    try:
        open_orders = binance.fetch_open_orders()
        pending_coins = {order['symbol'] for order in open_orders if order['status'] == 'open'}
        return pending_coins
    except ccxt.BaseError as e:
        print_with_timestamp(f"An error occurred while fetching open orders: {e}")
        return set()
    
# def filter_coins_by_percentage(tickers, threshold_percentage=5.0):
#     """
#     Belirli bir değişim yüzdesi eşiğine göre coinleri filtreler.
#     """
#     significant_coins = []  # Eşik değeri aşan coinleri saklayacak liste
    
#     for ticker in tickers:
#         symbol = ticker['symbol']
#         price_change_percent = float(ticker['info']['priceChangePercent'])
        
#         # Eğer günlük değişim yüzdesi eşik değerden büyük ve pozitifse listeye ekle
#         if price_change_percent >= threshold_percentage:
#             print_with_timestamp(f"Significant change detected for {symbol}: {price_change_percent:.2f}%")
#             significant_coins.append(symbol)
#         #else:
#             #print_with_timestamp(f"No significant change for {symbol}. Current Change: {price_change_percent:.2f}%")

#     return significant_coins  # Eşik değeri aşan coinlerin listesini döndür
def monitor_orders(take_profit_order, stop_loss_order, coin, stop_event):
    """
    Satış emirlerini izler ve biri tetiklendiğinde diğerini iptal eder.
    Bu fonksiyon bağımsız bir thread içinde çalışır, ana işlemleri bloklamaz.
    """
    try:
        while not stop_event.is_set():  # stop_event tetiklenmedikçe döngü devam eder
            open_orders = binance.fetch_open_orders(symbol=coin)

            # Eğer Take-Profit emri tetiklendiyse Stop-Loss'u iptal et
            if not any(order['id'] == take_profit_order['id'] for order in open_orders):
                print_with_timestamp(f"Take-Profit emri tetiklendi, Stop-Loss emri iptal ediliyor.")
                binance.cancel_order(stop_loss_order['id'], coin)
                sell_time = datetime.now().isoformat()
                message = f"Sold {coin} at {sell_time}"
                send_telegram_message_sync(message)
                sell_usdt_balance = binance.fetch_balance()['USDT']['free']
                print_with_timestamp(f"Updated USDT balance after selling {coin}: {sell_usdt_balance}")
                stop_event.set()  # Döngüden çıkılır
                #break
                return sell_usdt_balance

            # Eğer Stop-Loss emri tetiklendiyse Take-Profit'i iptal et
            if not any(order['id'] == stop_loss_order['id'] for order in open_orders):
                print_with_timestamp(f"Stop-Loss emri tetiklendi, Take-Profit emri iptal ediliyor.")
                binance.cancel_order(take_profit_order['id'], coin)
                sell_time = datetime.now().isoformat()
                message = f"Sold {coin} at {sell_time}"
                send_telegram_message_sync(message)
                sell_usdt_balance = binance.fetch_balance()['USDT']['free']
                print_with_timestamp(f"Updated USDT balance after selling {coin}: {sell_usdt_balance}")
                stop_event.set()  # Döngüden çıkılır
                #break
                return sell_usdt_balance

            time.sleep(2)  # 2 saniye bekleyip durumu tekrar kontrol et
    except ccxt.BaseError as e:
        print_with_timestamp(f"An error occurred while monitoring orders for {coin}: {e}")
        stop_event.set()  # Hata olursa döngü sonlanır
    except Exception as e:
        print_with_timestamp(f"An unknown error occurred: {e}")
        stop_event.set()  # Genel hata olursa da döngü sonlanır

def manage_sell(coin, amount, stop_loss_price, take_profit_price):
    """
    Coin'in stop-loss veya take-profit seviyelerine ulaşıp ulaşmadığını kontrol eder ve iki ayrı emir verir.
    Emirlerden biri tetiklenirse diğerini iptal eder.
    """
    stop_event = threading.Event()  # Döngüyü durdurmak için Event

    try:
        # Öncelikle, bu coin için zaten aktif bir emir olup olmadığını kontrol edin
        open_orders = binance.fetch_open_orders(symbol=coin)
        if open_orders:
            print_with_timestamp(f"{coin} için zaten açık emirler var, yeni emir oluşturulmayacak.")
            return None
        market = binance.markets[coin]
        precision = market['precision']['amount']
        amount = round(amount, int(precision))
        min_amount = market['limits']['amount']['min']
        
        # Minimum miktar kontrolü
        if amount < min_amount:
            print_with_timestamp(f"Amount {amount} is less than minimum allowed {min_amount} for {coin}. Adjusting amount to minimum.")
            amount = min_amount

        balance = binance.fetch_balance()
        symbol_base = coin.split('/')[0]
        available_amount = balance[symbol_base]['free']
        if amount > available_amount:
            print_with_timestamp(f"Not enough balance to sell {amount} of {coin}. Available: {available_amount}")
            amount = available_amount
        # Eğer açık emir yoksa yeni emirler oluşturulacak
        stop_loss_limit_price = stop_loss_price * 0.995  # Stop-Loss tetiklendiğinde limit fiyat

        # Take-Profit ve Stop-Loss emirlerini oluştur
        take_profit_order = create_take_profit_order(coin, amount, take_profit_price)
        stop_loss_order = create_stop_loss_order(coin, amount, stop_loss_price, stop_loss_limit_price)

        if take_profit_order and stop_loss_order:
            print_with_timestamp("Hem Take-Profit hem de Stop-Loss emirleri başarıyla oluşturuldu.")
            
            # Satış emirlerini izlemeye başla, ancak ana thread'i bloklama
            monitor_thread = threading.Thread(target=monitor_orders, args=(take_profit_order, stop_loss_order, coin, stop_event))
            monitor_thread.start()  # monitor_orders bağımsız bir thread olarak başlatılır
        else:
            print_with_timestamp("Emirlerden biri oluşturulamadı.")

    
    except ccxt.InsufficientFunds as e:
        print_with_timestamp(f"Insufficient funds to sell {coin}: {e}")
    except ccxt.RequestTimeout:
        print_with_timestamp(f"Request timeout while managing sell for {coin}. Retrying...")
        stop_event.set()  # Hata durumunda Event tetiklenir
    except ccxt.BaseError as e:
        print_with_timestamp(f"An error occurred while managing sell for {coin}: {e}")
        stop_event.set()  # Hata durumunda Event tetiklenir
    except Exception as e:
        print_with_timestamp(f"An unknown error occurred: {e}")
        stop_event.set()  # Hata durumunda Event tetiklenir
    
    return None

def filter_coins_by_percentage_and_volume(tickers, threshold_percentage=5.0, min_volume=125000, max_volume=10000000):
    """
    Belirli bir değişim yüzdesi ve hacim aralığına göre coinleri filtreler.
    """
    significant_coins = []  # Eşik değeri aşan ve hacim aralığında olan coinleri saklayacak liste
    
    for ticker in tickers:
        symbol = ticker['symbol']
        price_change_percent = float(ticker['info']['priceChangePercent'])
        volume = float(ticker['quoteVolume'])

        # Eğer günlük değişim yüzdesi eşik değerden büyük ve hacim belirli aralıkta ise listeye ekle
        if price_change_percent >= threshold_percentage and min_volume <= volume <= max_volume:
            print_with_timestamp(f"Significant change detected for {symbol}: {price_change_percent:.2f}% with volume: {volume}")
            significant_coins.append(symbol)
        #else:
            #print_with_timestamp(f"No significant change for {symbol}. Current Change: {price_change_percent:.2f}%, Volume: {volume}")

    return significant_coins  # Eşik değeri aşan ve belirli hacimdeki coinlerin listesini döndür

def monitor_price_change_percentage(tickers, threshold_percentage=5.0):
    """
    Coinlerin günlük değişim bilgilerini ve hacimlerini kontrol eder ve belirtilen eşiği geçenleri listeler.
    """
    filtered_coins = filter_coins_by_percentage_and_volume(tickers, threshold_percentage)
    return filtered_coins

def get_filtered_coins(active_usdt_pairs, threshold_percentage=5.0):
    """
    Aktif USDT paritelerinin listesini alır ve belirli hacim ve değişim yüzdesi eşiklerini karşılayanları filtreler.
    """
    filtered_coins = []
    tickers = []  # Eklenen: ticker bilgilerini saklayacak bir liste

    for market in active_usdt_pairs:
        try:
            ticker = binance.fetch_ticker(market)
            tickers.append(ticker)
        except ccxt.RequestTimeout:
            print_with_timestamp(f"Request timeout for {market}")
        except ccxt.BaseError as e:
            print_with_timestamp(f"An error occurred for {market}: {e}")

    # Değişim yüzdesine göre filtrelenen coinleri al
    significant_coins = monitor_price_change_percentage(tickers, threshold_percentage)

    # Sadece belirli hacim eşiklerini karşılayan ve değişim yüzdesi uygun olan coinleri ekle
    for coin in significant_coins:
        ticker = binance.fetch_ticker(coin)
        volume = ticker['quoteVolume']
        threshold = get_volume_threshold(volume)
        if threshold:
            filtered_coins.append((coin, threshold))
    
    return filtered_coins

def monitor_buy_conditions(threshold_percentage=5.0):
    """
    Alım işlemlerini sürekli kontrol eder ve uygun koşullar sağlandığında alım yapar.
    """
    global bought_coins, unsold_coins
    active_usdt_pairs = get_active_usdt_pairs()
    while True:
        filtered_coins = get_filtered_coins(active_usdt_pairs, threshold_percentage)
        #pending_coins = check_pending_orders()  # Bekleyen emirleri kontrol et

        for coin, threshold in filtered_coins:
            #if coin not in bought_coins and coin not in sold_coins and coin not in pending_coins:  # Satılan ve alınan coinler tekrar alınmaz
            if coin not in bought_coins and coin not in sold_coins:  # Satılan ve alınan coinler tekrar alınmaz
                is_green, open_price = is_green_candle(coin, threshold)
                if is_green:
                    # Alım koşulları sağlanırsa alım yap
                    with buy_lock:
                        usdt_balance = binance.fetch_balance()['USDT']['free']
                        min_notional = get_min_notional(coin)
                        amount = calculate_amount(open_price, min_notional)  # Minimum işlem miktarı kontrolü
                        if usdt_balance >= amount * open_price:
                            new_balance = buy_coin(coin, amount)
                            if new_balance is not None:
                                bought_coins[coin] = {
                                    'buy_price': open_price,
                                    'buy_time': datetime.now(timezone.utc).isoformat(),
                                    'amount': amount
                                }
                                unsold_coins[coin] = bought_coins[coin]  # Satılmamış coinleri de takip etmek için ekleyin
                                save_bought_coins(bought_coins)
                                usdt_balance = new_balance  # Bakiye güncellemesi
        time.sleep(2)  # Daha kısa bir bekleme süresi kullanarak işlem fırsatlarını kaçırmaktan kaçının

def monitor_sell_conditions():
    """
    Satım işlemlerini sürekli kontrol eder ve uygun koşullar sağlandığında satım yapar.
    """
    global sold_coins, unsold_coins
    while True:
        with sell_lock:
            # Satılmamış coinleri kontrol edin.
            for coin, info in list(unsold_coins.items()):
                stop_loss_price = info['buy_price'] * 0.90  # %5 zarar stop-loss
                take_profit_price = info['buy_price'] * 1.05  # %5 kar take-profit
                sell_result = manage_sell(coin, info['amount'], stop_loss_price, take_profit_price)
                
                if sell_result is not None:
                    # Satış gerçekleştirildi, sold_coins listesine ekle ve unsold_coins'ten çıkar
                    sold_coins[coin] = True  
                    save_sold_coins(sold_coins)
                    del unsold_coins[coin]  # Satılan coini unsold_coins listesinden çıkar
                    #del bought_coins[coin]  # Satılan coini bought_coins listesinden de çıkar
                    #save_bought_coins(bought_coins)  # Satış sonrasında bought_coins listesini kaydet
                else:
                    # Satılmamış coinler `unsold_coins` listesinde kalmaya devam eder
                    print_with_timestamp(f"No sale yet for {coin}. It will be checked again.")
                    
        time.sleep(2)  # Daha kısa bir bekleme süresi kullanarak işlem fırsatlarını kaçırmaktan kaçının

def main():
    """
    Ana işlem döngüsü, Binance bağlantısını kurar ve kontrol eder.
    """
    global binance
    try:
        binance = connect_to_binance()
        if not check_binance_connection():
            reconnect_to_binance()
    except Exception as e:
        print_with_timestamp(f"Başlangıçta bağlantı hatası: {e}")
        reconnect_to_binance()

    # Satın alınan ve satılan coinlerin listesini temizle
    clear_bought_coins()
    clear_sold_coins()

    global bought_coins, sold_coins, unsold_coins
    bought_coins = load_bought_coins()
    sold_coins = load_sold_coins()
    unsold_coins = {coin: info for coin, info in bought_coins.items() if coin not in sold_coins}  # Satılmamış coinleri yükleyin

    # Alım ve Satım kontrol thread'lerini başlat
    buy_thread = threading.Thread(target=monitor_buy_conditions)
    sell_thread = threading.Thread(target=monitor_sell_conditions)

    buy_thread.start()
    sell_thread.start()

    buy_thread.join()
    sell_thread.join()

if __name__ == "__main__":
    main()
