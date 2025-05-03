#src/telegram_bot/services/notifications.py
from pathlib import Path

# Путь до src/ (если paths.py находится в src/core/)
BASE_DIR = Path(__file__).resolve().parent.parent  # src/
COLLECTED_DATA = BASE_DIR / "collected_data"

TW_ANALYSIS = COLLECTED_DATA / "tradingview_analysis"
TELEGRAM_CACHE = COLLECTED_DATA / "telegram_cache"
POSITIONS = COLLECTED_DATA / "positions"

# Создаем директории
COLLECTED_DATA.mkdir(exist_ok=True)
TW_ANALYSIS.mkdir(exist_ok=True)
TELEGRAM_CACHE.mkdir(exist_ok=True)
POSITIONS.mkdir(exist_ok=True)