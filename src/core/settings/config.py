SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "2h", "4h"]

# Веса таймфреймов (сумма = 1.0)


# Силы сигналов
RECOMMENDATION_SCORE_MAP = {
  "STRONG_SELL": -2,
  "SELL": -1,
  "NEUTRAL": 0,
  "BUY": 1,
  "STRONG_BUY": 2
}

# Пороги для классификации
BUY_THRESHOLD = 1    # STRONG_BUY: score >= 1.6 (2 * 0.8)
SELL_THRESHOLD = -0.45  # STRONG_SELL: score <= -1.2 (2 * -0.6)

# Симулятор
INITIAL_BALANCE = 100000.0
COMMISSION = 0.001
REBALANCE_INTERVAL = "1m"

# Механизм трейлинг-стопа
TRAILING_STOP_PERCENT = 1.5  # 1.5% отката для активации стопа
MIN_PROFIT_TO_TRAIL = 2.0     # Минимальная прибыль 2% для включения трейлинга

# Уровни фиксации прибыли
PROFIT_TAKE_LEVELS = {
    2.0: 0.3,   # Продать 30% при +2%
    5.0: 0.5,   # Продать 50% при +5%
    10.0: 0.7   # Продать 70% при +10%
}

# Доли продажи в зависимости от силы сигнала
SELL_ALLOCATION = {
    "STRONG_SELL": 1.0,  # 100% позиции
    "SELL": 0.5          # 50% позиции
}

BINANCE_API_KEY = "Ig7xOto8PtTseG2IFdNqPl6mmf9BQhBAVTV92wvOJhxqTpwhc1em4pBVwiXx4kA9"
BINANCE_SECRET_KEY = "AJz1VzTY5TJkqpRFyzBmEYV8ozd04g2vbO8gStfoQF05pNU97BYLls4wevzQOl8Y"
TESTNET = True  # Режим тестовой сети

# Безопасный запас для минимального номинала (5%)
SAFETY_MARGIN = 1.05

# Проверка весов
assert sum(TIMEFRAME_WEIGHTS.values()) == 1.0, "Сумма весов должна быть равна 1!"
