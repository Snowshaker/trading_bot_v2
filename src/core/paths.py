# src/core/paths.py
from pathlib import Path

# Базовый путь до директории src (предполагая, что файл находится в src/core/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Основная директория для хранения данных
COLLECTED_DATA = BASE_DIR / "collected_data"

# Пути к поддиректориям
TW_ANALYSIS = COLLECTED_DATA / "tradingview_analysis"
POSITIONS = COLLECTED_DATA / "positions"
TELEGRAM_CACHE = COLLECTED_DATA / "telegram_cache"

# Автоматическое создание директорий при первом импорте
COLLECTED_DATA.mkdir(parents=True, exist_ok=True)
TW_ANALYSIS.mkdir(exist_ok=True)
POSITIONS.mkdir(exist_ok=True)
TELEGRAM_CACHE.mkdir(exist_ok=True)

# Пример структуры после создания:
# src/
# └── collected_data/
#     ├── tradingview_analysis/
#     ├── positions/
#     └── telegram_cache/