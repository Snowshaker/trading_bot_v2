## 🛠️ Установка и Запуск

Следуйте этим шагам для установки, настройки и запуска бота.

### 1. Предварительные требования

*   **Python 3.8+**: Убедитесь, что у вас установлен Python. Вы можете скачать его с [python.org](https://www.python.org/downloads/).
*   **Git**: Необходим для клонирования репозитория. Инструкции по установке можно найти на [git-scm.com](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git).
*   **pip**: Менеджер пакетов Python (обычно устанавливается вместе с Python).

### 2. Клонирование репозитория

Откройте терминал или командную строку и выполните:

```bash
git clone git@github.com:Snowshaker/trading_bot_v2.git
cd trading_bot_v2
```

### 3. Создание и активация виртуального окружения (рекомендуется)

Это поможет изолировать зависимости проекта:

```bash
# Для Windows
python -m venv venv
venv\Scripts\activate

# Для macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Установка зависимостей

Установите все необходимые библиотеки, указанные в requirements.txt:

```bash
pip install -r requirements.txt
```

### 5. Конфигурация

Перед первым запуском необходимо настроить два основных конфигурационных файла:

а) Настройки основного бота (src/core/settings/config.py)

Откройте файл src/core/settings/config.py и заполните следующие обязательные поля:

    BINANCE_API_KEY: Ваш API ключ от биржи Binance.

    BINANCE_SECRET_KEY: Ваш секретный API ключ от биржи Binance.

Пример:

```python
# ... другие настройки ...

# API Binance
BINANCE_API_KEY = "ВАШ_BINANCE_API_KEY"     # ВАЖНО: замените на свой открытый Binance ключ
BINANCE_SECRET_KEY = "ВАШ_BINANCE_SECRET_KEY"  # ВАЖНО: замените на свой закрытый Binance ключ
TESTNET = True # Установите False для реальной торговли, True для тестовой сети
# ... другие настройки ...
```

ВАЖНО: Для реальной торговли установите TESTNET = False. Настоятельно рекомендуется начать тестирование с TESTNET = True.
б) Настройки Telegram-бота (src/core/settings/telegram_config.py)

Откройте файл src/core/settings/telegram_config.py и заполните следующие обязательные поля:

    TELEGRAM_BOT_TOKEN: Токен вашего Telegram-бота.

        Чтобы получить токен, создайте нового бота через @BotFather в Telegram.

    TELEGRAM_ADMINS: Список числовых ID администраторов бота в Telegram.

        Чтобы узнать свой Telegram ID, напишите боту @userinfobot и он пришлет вам ваш ID.

Пример:

```python
# ... другие настройки ...

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "ВАШ_TELEGRAM_BOT_TOKEN")

TELEGRAM_ADMINS: list[int] = [123456789] # Замените на ваш реальный Telegram ID

# ... другие настройки ...
```

Если вы не заполните эти значения, бот выведет предупреждение при запуске, но для полноценной работы Telegram-интерфейса они необходимы.

# 6. Запуск Бота

Существует два основных сценария запуска:

#### Вариант 1: Запуск только Telegram-бота (без основной торговой логики)

Этот режим позволяет вам использовать команды Telegram для ручной торговли, просмотра информации и т.д., но автоматический анализ и торговля по сигналам TradingView (логика из main.py) не будут активны.

В терминале, находясь в корневой директории проекта (trading_bot_v2), выполните:

```bash
python src/telegram_bot/bot.py
```

#### Вариант 2: Запуск полного функционала (Основной бот + Telegram-бот)

Этот режим активирует как автоматическую торговую логику на основе анализа TradingView (main.py), так и интерфейс управления через Telegram (telegram_bot/bot.py). Вам потребуется запустить два процесса в двух разных терминалах.

1. В первом терминале (основная торговая логика):
    Находясь в корневой директории проекта (trading_bot_v2), выполните:

```bash
python src/main.py
```

Этот процесс будет заниматься сбором данных, анализом и автоматическим исполнением сделок.

2. Во втором терминале (Telegram-интерфейс):
Находясь в корневой директории проекта (trading_bot_v2), выполните:

```bash
python src/telegram_bot/bot.py
```

Этот процесс обеспечит взаимодействие с ботом через команды Telegram.

### 7. Глубокая Настройка (Опционально)

Файл src/core/settings/config.py содержит множество параметров, которые позволяют тонко настроить поведение торгового бота:

    SYMBOLS, TIMEFRAMES: Списки торговых пар и таймфреймов для анализа.

    BOT_SLEEP_INTERVAL, TV_FETCH_DELAY: Интервалы опроса и задержки.

    MIN_SCORE_FOR_EXECUTION, BUY_THRESHOLD, SELL_THRESHOLD: Пороги для принятия решений.

    Параметры риск-менеджмента: TRAILING_STOP_PERCENT, PROFIT_TAKE_LEVELS, ALLOCATION_MAX_PERCENT, MIN_ORDER_SIZE.

    И многое другое.

Изучите этот файл, чтобы адаптировать бота под вашу индивидуальную торговую стратегию и предпочтения по управлению рисками.

**Примечание**: Лог-файлы операций основного бота сохраняются в src/bot.log (или как указано в LOGGING_CONFIG в src/core/settings/config.py), а лог-файлы Telegram-бота в src/telegram_bot/bot.log (или как указано в LOGGING_CONFIG_TG в src/core/settings/telegram_config.py).