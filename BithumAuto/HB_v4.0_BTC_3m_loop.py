import datetime
import time
import pytz
import pandas as pd
import ccxt
import ende_key  #암복호화키
import my_key    #업비트 시크릿 액세스키

from cryptography.fernet import Fernet

#암호화 복호화 클래스
class SimpleEnDecrypt:
    def __init__(self, key=None):
        if key is None: # 키가 없다면
            key = Fernet.generate_key() # 키를 생성한다
        self.key = key
        self.f   = Fernet(self.key)
    
    def encrypt(self, data, is_out_string=True):
        if isinstance(data, bytes):
            ou = self.f.encrypt(data) # 바이트형태이면 바로 암호화
        else:
            ou = self.f.encrypt(data.encode('utf-8')) # 인코딩 후 암호화
        if is_out_string is True:
            return ou.decode('utf-8') # 출력이 문자열이면 디코딩 후 반환
        else:
            return ou
        
    def decrypt(self, data, is_out_string=True):
        if isinstance(data, bytes):
            ou = self.f.decrypt(data) # 바이트형태이면 바로 복호화
        else:
            ou = self.f.decrypt(data.encode('utf-8')) # 인코딩 후 복호화
        if is_out_string is True:
            return ou.decode('utf-8') # 출력이 문자열이면 디코딩 후 반환
        else:
            return ou

#암복호화 클래스 객체를 미리 생성한 키를 받아 생성한다.
simpleEnDecrypt = SimpleEnDecrypt(ende_key.ende_key)

#암호화된 액세스키와 시크릿키를 읽어 복호화 한다.
Bithumb_ApiKey = simpleEnDecrypt.decrypt(my_key.bithumb_apikey)
Bithumb_Secret = simpleEnDecrypt.decrypt(my_key.bithumb_secret)

# Bithumb API 연결 설정
bithumb = ccxt.bithumb({
    'apiKey': Bithumb_ApiKey,
    'secret': Bithumb_Secret,
})


# 종목, 차트기간 설정
ticker = 'BTC/KRW'                                                                       ###########################
timeframe = '3m'                                                                         ###########################
since = bithumb.parse8601('2022-01-01T00:00:00Z')
limit = 50000

# 시간 데이터를 한국 시간대로 변환하는 함수
def convert_to_kst(time):
    kst = pytz.timezone('Asia/Seoul')
    return time.astimezone(kst)
  
current_time = convert_to_kst(datetime.datetime.now())


# 지표값 입력
signal_window = 9
best_short_window = 12
best_long_window = 26
best_rsi_window = 14

# 이동평균선 계산함수 : (분봉/일봉 정보, 기간, 날짜)
def get_ma(btc_data,period,st):
    close = btc_data["close"]
    ma = close.rolling(period).mean()
    return float(ma.iloc[st])

        
# MACD 계산 함수
def calculate_macd(btc_data, best_short_window, best_long_window, signal_window):
    short_ema = btc_data['close'].ewm(span=best_short_window, adjust=False).mean()
    long_ema = btc_data['close'].ewm(span=best_long_window, adjust=False).mean()
    macd = short_ema - long_ema
    signal = macd.ewm(span=signal_window, adjust=False).mean()
    return macd, signal

# RSI 계산 함수
def calculate_rsi(btc_data, best_rsi_window):
    delta = btc_data['close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=best_rsi_window-1, adjust=False).mean()
    ema_down = down.ewm(com=best_rsi_window-1, adjust=False).mean()
    rs = ema_up / ema_down
    rsi = 100 - (100 / (1 + rs))
    return rsi

# 스토캐스틱 계산 함수
def calculate_stochastic(btc_data, k_window=14, d_window=3):
    low_min = btc_data['low'].rolling(window=k_window).min()
    high_max = btc_data['high'].rolling(window=k_window).max()
    k_line = ((btc_data['close'] - low_min) / (high_max - low_min)) * 100
    d_line = k_line.rolling(window=d_window).mean()
    return k_line, d_line

# OHLCV 데이터를 가져오는 함수
def fetch_ohlcv(ticker, timeframe, since, limit):
    ohlcv = bithumb.fetch_ohlcv(ticker, timeframe, since, limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

# 데이터 준비하기
btc_data = fetch_ohlcv(ticker, timeframe, since, limit)

# 최신 시장 데이터 가져오기
def update_market_data_and_signals(best_short_window, best_long_window, best_rsi_window, signal_window):
    btc_data = fetch_ohlcv(ticker, timeframe, since, limit)
    macd, macd_signal = calculate_macd(btc_data, best_short_window, best_long_window, signal_window)
    rsi = calculate_rsi(btc_data, best_rsi_window)
    k_line, d_line = calculate_stochastic(btc_data)
    btc_data['macd'] = macd
    btc_data['macd_signal'] = macd_signal
    btc_data['rsi'] = rsi
    btc_data['k_line'] = k_line
    btc_data['d_line'] = d_line
    trading_signals = generate_trading_signals(btc_data, best_short_window, best_long_window, best_rsi_window,signal_window )
    latest_data = btc_data.iloc[-1]
    latest_signal = trading_signals.iloc[-1]
    return latest_data, latest_signal


# 매매신호 계산
def generate_trading_signals(latest_data, best_short_window, best_long_window, best_rsi_window, signal_window):
    macd, signal = calculate_macd(latest_data, best_short_window, best_long_window,signal_window)
    rsi = calculate_rsi(latest_data, best_rsi_window)
    k_line, d_line = calculate_stochastic(latest_data)
    latest_data['macd'] = macd
    latest_data['macd_signal'] = signal
    latest_data['rsi'] = rsi
    latest_data['k_line'] = k_line
    latest_data['d_line'] = d_line
    signals = pd.DataFrame(index=latest_data.index)
    signals['signal'] = 0.0
    signals.loc[(ma5_now < ma20) & (ma5_before3 > ma5_before2) & (ma5_before2 < ma5_now) 
                 & (latest_data['k_line'] < 30) & (latest_data['rsi'] < 50), 'signal'] = 1.0  # 매수 신호     #####################
    signals.loc[(ma5_now > ma20) & (ma5_before3 < ma5_before2) & (ma5_before2 > ma5_now) 
                 & (latest_data['d_line'] > 70) & (latest_data['rsi'] > 50), 'signal'] = -1.0  # 매도 신호    #####################
    signals['positions'] = signals['signal'].diff()
    return signals

# 실제 거래를 위한 함수
def execute_real_trade(latest_data, latest_signal):
    global buy_count, average_buy_price, total_buy_quantity  # 전역 변수 사용 
    current_time = datetime.datetime.now(pytz.timezone('Asia/Seoul'))

    order_price = latest_data['close']

    if latest_signal['signal'] == 1 and buy_count < 6:  # 매수 신호가 있고, 매수 횟수가 6회 미만인 경우
            # 잔고 확인 로직 추가
            balance = bithumb.fetch_balance()
            quote_currency = ticker.split('/')[1]  # 예: BTC/KRW에서 KRW를 얻음
            if quote_currency in balance and 'free' in balance[quote_currency]:
                quote_currency_balance = balance[quote_currency]['free']
                if quote_currency_balance > order_price * 0.005:  # 매수 가능한 잔고가 있는지 확인
                    print(f"매수 신호 (KST): 시간 {current_time}, 가격 {order_price}")
                    # 매수 주문 로직
                    bithumb.create_market_buy_order(ticker, 0.005)     #########################
                    buy_count += 1  # 매수 횟수 증가
                    buy_quantity = 0.005  # 매수 수량 (예시 값)
                    total_cost = average_buy_price * total_buy_quantity
                    total_cost += buy_quantity * order_price
                    total_buy_quantity += buy_quantity
                    average_buy_price = total_cost / total_buy_quantity
                else:
                    print("매수 가능한 잔고가 부족합니다.")
            else:
                print("잔고 정보를 가져오는 데 실패했습니다.")
        


    elif latest_signal['signal'] == -1:  # 매도 신호가 있는 경우
            if order_price >= average_buy_price * 1.01:
                print(f"매도 신호 (KST): 시간 {current_time}, 가격 {order_price}")
            # 매도 주문 로직
                balance = bithumb.fetch_balance()
                base_currency = ticker.split('/')[0]  # 예: BTC/KRW에서 BTC를 얻음
                if base_currency in balance and 'free' in balance[base_currency]:
                    base_currency_balance = balance[base_currency]['free']
                    if base_currency_balance > 0:
                    # 주문량 계산 (전량 매도 또는 0.006 BTC 중 작은 값)
                        order_quantity = min(base_currency_balance, 0.005)      ###############################
                    # 매도 주문 실행
                        bithumb.create_market_sell_order(ticker, order_quantity)
                        buy_count -= 1  # 매수 횟수 감소
                    else:
                        print("매도할 잔액이 없습니다.")
            else:
                print("잔고 정보를 가져오는 데 실패했습니다.")

    return current_time

import json

def load_data():
    try:
        with open('trade_data.json', 'r') as file:
            data = json.load(file)
        # 파일에서 키가 누락된 경우 기본값 설정
        data.setdefault('buy_count', 0)
        data.setdefault('average_buy_price', 0)
        data.setdefault('total_buy_quantity', 0)
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"buy_count": 0, "average_buy_price": 0, "total_buy_quantity": 0}

def save_data(data):
    with open('trade_data.json', 'w') as file:
        json.dump(data, file)


while True:
    # 전역 변수 선언
    global buy_count, average_buy_price, total_buy_quantity

    # 스크립트 시작 시 데이터 로드
    data = load_data()
    buy_count = data['buy_count']
    average_buy_price = data['average_buy_price']
    total_buy_quantity = data['total_buy_quantity']
    
    # 분봉 기준 5일선 계산
    ma5_before3 = get_ma(btc_data,5,-4)
    ma5_before2 = get_ma(btc_data,5,-3)
    ma5_now = get_ma(btc_data,5,-2)

    # 분봉 기준 20일선 계산
    ma20 = get_ma(btc_data,20,-2)
    
    print("ma20 :", ma20)
    print("ma5 :", ma5_before3, "->", ma5_before2, "->", ma5_now)

    # 최신 시장 데이터와 신호를 가져옵니다
    latest_data, latest_signal = update_market_data_and_signals(best_short_window, best_long_window, best_rsi_window, signal_window)

    print(f"시간 (KST): {current_time}, 종가: {latest_data['close']:.0f}, MACD: {latest_data['macd']:.0f}, MACD 신호: {latest_data['macd_signal']:.0f}, k_line: {latest_data['k_line']:.0f}, d_line: {latest_data['d_line']:.0f}, RSI: {latest_data['rsi']:.0f}")
    
    execute_real_trade(latest_data, latest_signal)

    # 스크립트 종료 시 데이터 저장
    save_data({"buy_count": buy_count,"average_buy_price": average_buy_price, "total_buy_quantity": total_buy_quantity})
    
    time.sleep(180)