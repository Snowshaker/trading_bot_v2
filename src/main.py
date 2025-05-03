"""
Главный исполняемый модуль торгового бота
"""
import sys
import os
import time
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional

# Добавление корневой директории в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Импорт компонентов
from src.core.api.tradingview_client.analysis_fetcher import TradingViewFetcher
from src.core.api.tradingview_client.analysis_saver import AnalysisSaver
from src.core.api.tradingview_client.analysis_collector import AnalysisCollector
from src.core.api.binance_client.info_fetcher import BinanceInfoFetcher
from src.core.data_logic.timeframe_weights_calculator import calculate_timeframe_weights
from src.core.data_logic.score_processor import ScoreProcessor
from src.core.data_logic.decision_processor.decision_maker import DecisionMaker
from src.core.data_logic.decision_processor.position_manager import PositionManager
from src.core.settings.config import (
    SYMBOLS,
    TIMEFRAMES,
    LOGGING_CONFIG,
    BOT_SLEEP_INTERVAL,
    BOT_SLEEP_BUFFER_SEC,
    ERROR_RETRY_DELAY,
    INIT_SYNC_DELAY,
    MIN_SCORE_FOR_EXECUTION,
    DATA_STALE_MINUTES,
    BINANCE_API_KEY,
    BINANCE_SECRET_KEY,
    TESTNET
)

def setup_logging():
    """Настройка системы логирования"""
    logging.basicConfig(
        filename=LOGGING_CONFIG['filename'],
        level=LOGGING_CONFIG['level'],
        format=LOGGING_CONFIG['format']
    )
    logging.captureWarnings(True)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logging.getLogger().addHandler(console)

class TradingBot:
    """
    Основной класс торгового бота
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)

        self.last_data_update = None
        self.analysis_fetcher = TradingViewFetcher()
        self.analysis_saver = AnalysisSaver()
        self.analysis_collector = AnalysisCollector()
        self.info_fetcher = BinanceInfoFetcher(
            api_key=BINANCE_API_KEY,
            api_secret=BINANCE_SECRET_KEY,
            testnet=TESTNET
        )

        # Инициализация компонентов
        self._init_components()

        # Синхронизация позиций
        self.logger.info("Initial positions sync started")
        time.sleep(INIT_SYNC_DELAY)
        for symbol in SYMBOLS:
            self.position_managers[symbol].sync_with_exchange()

    def _init_components(self):
        """Инициализация менеджеров позиций и механизмов принятия решений"""
        self.position_managers = {
            symbol: PositionManager(symbol, self.info_fetcher)
            for symbol in SYMBOLS
        }

        self.decision_makers = {
            symbol: DecisionMaker(
                symbol=symbol,
                info_fetcher=self.info_fetcher,
                position_manager=self.position_managers[symbol]
            )
            for symbol in SYMBOLS
        }

    def _is_data_stale(self) -> bool:
        """Проверка актуальности данных"""
        if not self.last_data_update:
            return True
        return (datetime.now() - self.last_data_update) > timedelta(
            minutes=DATA_STALE_MINUTES
        )

    def _fetch_and_process_data(self) -> Optional[Dict]:
        """Полный цикл обработки данных"""
        try:
            raw_data = self.analysis_fetcher.fetch_all_data()
            if not raw_data:
                logging.warning("No data from TradingView")
                return None

            self.analysis_saver.batch_save(raw_data)
            processed_data = self.analysis_collector.get_all_latest()
            self.last_data_update = datetime.now()

            return processed_data

        except Exception as e:
            logging.error(f"Data processing error: {str(e)}", exc_info=True)
            return None

    def _process_symbol(self, symbol: str, processed_data: dict) -> None:
        """Обработка одного символа с использованием данных анализа"""
        try:
            # 1. Синхронизация позиций
            self.position_managers[symbol].sync_with_exchange()

            # 2. Получение данных анализа
            symbol_data = processed_data.get(symbol)
            if not symbol_data or 'timeframes' not in symbol_data:
                self.logger.debug(f"No valid data for {symbol}")
                return

            # 3. Расчет скоринга
            result = self.score_processor.process(symbol_data['timeframes'])
            self.logger.info(f"{symbol} | Score: {result['score']:.2f} | Signal: {result['signal']}")

            # 4. Проверка условий для торговли
            if result['signal'] == 'NEUTRAL' or abs(result['score']) < MIN_SCORE_FOR_EXECUTION:
                return

            # 5. Исполнение сигнала
            decision_maker = self.decision_makers[symbol]
            if decision_maker.process_signal(
                score=Decimal(str(result['score'])),
                signal=result['signal']
            ):
                self.logger.info(f"Executed {result['signal']} for {symbol}")

        except Exception as e:
            self.logger.error(f"Error processing {symbol}: {str(e)}", exc_info=True)

    def run(self):
        """Основной рабочий цикл"""
        logging.info("Starting trading bot")
        try:
            while True:
                start_time = datetime.now()
                processed_data = self._fetch_and_process_data()

                if not processed_data:
                    logging.warning("Skipping iteration - no data")
                    time.sleep(ERROR_RETRY_DELAY)
                    continue

                # Получаем список актуальных таймфреймов из данных
                timeframes = list(processed_data[next(iter(SYMBOLS))]['timeframes'].keys())
                self.score_processor = ScoreProcessor(
                    calculate_timeframe_weights(timeframes)
                )

                for symbol in SYMBOLS:
                    self._process_symbol(symbol, processed_data)

                # Контроль временных интервалов
                elapsed = (datetime.now() - start_time).total_seconds()
                sleep_time = max(0, BOT_SLEEP_INTERVAL * 60 - elapsed - BOT_SLEEP_BUFFER_SEC)
                logging.info(f"Sleeping for {sleep_time:.1f} seconds")
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logging.info("Bot stopped by user")
        except Exception as e:
            logging.critical(f"Critical error: {str(e)}", exc_info=True)
            time.sleep(ERROR_RETRY_DELAY)
        finally:
            logging.info("Trading bot stopped")

if __name__ == "__main__":
    setup_logging()
    try:
        bot = TradingBot()
        bot.run()
    except Exception as e:
        logging.critical(f"Startup failed: {str(e)}", exc_info=True)
        raise