Core:
    --API
        tradingview_client - собирает и кэширует данные с tradingview
            analysis_collector - читает данные из хранилища
            analysis_fetcher.py - загружает данные с api + ретраи при ошибках
            analysis_saver.py - сохраняет данные в хранилище + сжатие

        binance_client - отправляет запросы на binance
            info_fetcher - собирает информацию о ценах и портфеле + синхронизирует с локальной
            trading_history_fetcher - собирает историю транзакций + экспорт в csv
            transactions_executor - исполняет торговые операции + трейлинг-стопы

    --Telegram Bot
        --handlers - обработчики команд и сообщений
            config_handlers.py - работа с конфигурацией
            control_handlers.py - управление ботом (старт/стоп)
            trade_handlers.py - ручные торговые операции
            info_handlers.py - запрос информации
            forecast_handlers.py - вывод аналитики
            error_handlers.py - обработка ошибок

        --keyboards - клавиатуры и кнопки
            main_menu.py - главное меню
            config_menu.py - меню настроек
            trade_menu.py - меню торговли
            inline.py - инлайн-кнопки

        --services - сервисные компоненты
            config_manager.py - работа с конфигурацией
            auth.py - аутентификация пользователей
            binance_api.py - обертка для API Binance
            formatters.py - форматирование сообщений
            notifications.py - система уведомлений

        bot.py - основной модуль бота
        states.py - FSM состояния

    --Collected Data
        tw_analysis - анализ с tradingview
        binance_prices - текущие цены на binance
        telegram_cache - кэш данных для быстрого доступа
        
    --Data Logic
        timeframe_weights_calculator - считает распределение весов для переданных временных промежутков
        score_processor - рассчет score пл tw_analysis

        --Decision Processor - принятие решение по score
            position_manager.py - создание, редактирование и просмотр записей об открытых позициях + синхронизация с биржей
            risk_engine.py - управление стоп-лоссами и тейк-профитами с помощью position manager
            allocation_strategy.py - рассчет объема сделки в зависимости от score
            decision_maker.py - получает валюту и score, вызывает функции из остальных файлов,
                                отправляет решения в transactions_executor, проверяет, что сделка выполнилась (или ретрай)

    --Settings
        config - настройки основного бота
        telegram_config.py - настройки телеграм бота

    --Utils
        analysis_print - анализ по последним данным из tw_analysis
        trading_history - последние операции
        telegram_utils.py - вспомогательные функции для работы с Telegram API

    --Logs
        bot_log - логи основного бота
        telegram_logs - логи телеграм бота

    --Tests
        тесты для каждой функции
        --telegram_tests
            test_handlers.py
            test_services.py
            test_keyboards.py

logs:
    все лог файлы

tests:
    тесты для всех локальных функций
    --telegram_bot
        тесты компонентов телеграм бота

utils:
    вспомогательные утилиты
    analysis_printer.py
    telegram_debug.py - инструменты отладки телеграм бота