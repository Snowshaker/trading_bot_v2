Core:

    --API
        tradingview_client - собирает данные с tradingview
            analysis_collector - читает данные из хранилища
            analysis_fetcher.py - загружает данные с api
            analysis_saver.py - сохраняет данные в хранилище

        binance_client - отправляет запросы на binance
            info_fetcher - собирает информацию о ценах и портфеле
            trading_history_fetcher - собирает историю транзакций
            transactions_executor - исполняет торговые операции

    --Collected Data
        tw_analysis - анализ с tradingview
        binance_prices - текущие цены на binance
        
    --Data Logic
        timeframe_weights_calculator - считает распределение весов для переданных временных промежутков
        score_processor - рассчет score пл tw_analysis
        decision_processor - принятие решение по score

    --Settings
        config

    --Utils
        analysis_print - анализ по последним данным из tw_analysis
        trading_history - последние операции

    --Logs
        пока что не проработано

    --Tests
        тесты для каждой функции

logs:
    все лог файлы

tests:
    тесты для всех локальных функций

utils:
    вспомогательные утилиты
    analysis_printer.py