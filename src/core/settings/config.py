from decimal import Decimal

TELEGRAM_BOT_TOKEN = "your_telegram_bot_token"
TELEGRAM_ADMINS = [123456789]  # Список ID администраторов
BOT_ENABLED = True  # Флаг активности основного бота

# Временные интервалы
BOT_SLEEP_INTERVAL = 0.5          # Основной интервал между итерациями (минуты) 5.0
BOT_SLEEP_BUFFER_SEC = 2.0        # Буфер между итерациями (секунды) 5.0
ERROR_RETRY_DELAY = 10.0         # Задержка при ошибках (секунды) 60.0
API_RATE_LIMIT_DELAY = 1.0        # Задержка между API запросами (секунды) 1.0
INIT_SYNC_DELAY = 3.0             # Задержка при стартовой синхронизации (секунды) 3.0

# TradingView
TV_FETCH_DELAY = 2.0              # Задержка между запросами к TradingView (секунды)

# Основные настройки
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "2h", "4h"]
DATA_STALE_MINUTES = 10  # Время устаревания данных в минутах
MIN_SCORE_FOR_EXECUTION = Decimal('0.5')  # Минимальный порог для исполнения

# Настройки логирования
LOGGING_CONFIG = {
    'filename': 'bot.log',
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}

# Тестовые таймфреймы
test_timeframes = [
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "1D", "1W", "1M"
]

# Силы сигналов
RECOMMENDATION_SCORE_MAP = {
    "STRONG_BUY": 2.0,
    "BUY": 1.0,
    "NEUTRAL": 0.0,
    "SELL": -1.0,
    "STRONG_SELL": -2.0
}

# Пороги для классификации
BUY_THRESHOLD = 1
SELL_THRESHOLD = -0.45

# Симулятор
INITIAL_BALANCE = 100000.0
COMMISSION = 0.001
REBALANCE_INTERVAL = "1m"

# Риск-менеджмент
TRAILING_STOP_PERCENT = Decimal('1.5')
MIN_PROFIT_TO_TRAIL = Decimal('2.0')
MIN_ORDER_SIZE = Decimal('0.001')

PROFIT_TAKE_LEVELS = {
    2.0: 0.3,   # 30% at +2%
    5.0: 0.5,   # 50% at +5%
    10.0: 0.7   # 70% at +10%
}

# Allocation Strategy
ALLOCATION_MAX_PERCENT = Decimal("5.0")  # 5% от баланса
ALLOCATION_SCALE_FACTOR = Decimal("1.0")
MIN_ORDER_SIZE = Decimal("10.0")  # Минимум $10 на сделку

# API Binance
BINANCE_API_KEY = "PYhZh79fjkjagiPN1snTsIWU8bDULYh9iSlDCYy9iWlLW5S3gd3psKP9RSJ40iza"
BINANCE_SECRET_KEY = "ohvP3vkPZxJG84B3lXBXPuDJFVrhiDWP8wvPPiSMzNoLrMIevbKvopsQBLQdO6E6"
TESTNET = True
SAFETY_MARGIN = 1.05

# Технические константы
INF = 10**9