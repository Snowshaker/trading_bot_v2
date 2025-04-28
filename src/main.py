"""
Главный исполняемый модуль торгового бота
"""

import sys
import os
import time
import logging
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
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
from src.core.data_logic.decision_processor.risk_engine import RiskEngine
from src.core.data_logic.decision_processor.position_manager import PositionManager
from src.core.settings.config import (
    SYMBOLS,
    TIMEFRAMES,
    BOT_SLEEP_INTERVAL,
    LOGGING_CONFIG,
    MIN_SCORE_FOR_EXECUTION,
    DATA_STALE_MINUTES
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
        self.last_data_update: Optional[datetime] = None

        # Инициализация компонентов данных
        self.analysis_fetcher = TradingViewFetcher()
        self.analysis_saver = AnalysisSaver()
        self.analysis_collector = AnalysisCollector()

        # Инициализация клиентов Binance
        self.info_fetcher = BinanceInfoFetcher()

        # Инициализация системы управления позициями
        self.position_managers = {
            symbol: PositionManager(
                symbol=symbol,
                info_fetcher=self.info_fetcher
            )
            for symbol in SYMBOLS
        }

        # Инициализация компонентов принятия решений
        self.decision_makers = {
            symbol: DecisionMaker(
                symbol=symbol,
                info_fetcher=self.info_fetcher,
                position_manager=self.position_managers[symbol]
            )
            for symbol in SYMBOLS
        }

        self.risk_engines = {
            symbol: RiskEngine(
                symbol=symbol,
                info_fetcher=self.info_fetcher,
                position_manager=self.position_managers[symbol]
            )
            for symbol in SYMBOLS
        }

        self.score_processor: Optional[ScoreProcessor] = None

        # Синхронизация позиций при старте
        for symbol in SYMBOLS:
            self.position_managers[symbol].sync_with_exchange()

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
            # Получение данных с TradingView
            raw_data = self.analysis_fetcher.fetch_all_data()
            if not raw_data:
                logging.warning("No data from TradingView")
                return None

            # Сохранение и чтение данных
            self.analysis_saver.batch_save(raw_data)
            processed_data = self.analysis_collector.get_all_latest()
            self.last_data_update = datetime.now()

            return processed_data

        except Exception as e:
            logging.error(f"Data processing error: {str(e)}", exc_info=True)
            return None

    def _process_symbol(self, symbol: str, processed_data: Dict):
        """Обработка одного символа"""
        try:
            # Синхронизация позиций
            self.position_managers[symbol].sync_with_exchange()

            # Извлечение данных
            symbol_data = processed_data.get(symbol)
            if not symbol_data:
                logging.debug(f"No data for {symbol}")
                return

            # Расчет сигнала
            result = self.score_processor.process(symbol_data['timeframes'])
            logging.info(f"{symbol} | Score: {result['score']:.2f} | Signal: {result['signal']}")

            # Проверка порога
            if result['signal'] == 'NEUTRAL' or \
               abs(result['score']) < MIN_SCORE_FOR_EXECUTION:
                return

            # Исполнение ордера
            decision_maker = self.decision_makers[symbol]
            if decision_maker.process_signal(
                score=Decimal(result['score']),
                signal=result['signal']
            ):
                logging.info(f"Executed {result['signal']} for {symbol}")

        except Exception as e:
            logging.error(f"Error processing {symbol}: {str(e)}", exc_info=True)

    def run(self):
        """Основной рабочий цикл"""
        logging.info("Starting trading bot")
        try:
            while True:
                start_time = datetime.now()

                # Обработка данных
                processed_data = self._fetch_and_process_data()
                if not processed_data:
                    logging.warning("Skipping iteration - no data")
                    time.sleep(5)
                    continue

                # Инициализация процессора
                timeframes = list(processed_data[next(iter(SYMBOLS))]['timeframes'].keys())
                self.score_processor = ScoreProcessor(
                    calculate_timeframe_weights(timeframes)
                )

                # Обработка символов
                for symbol in SYMBOLS:
                    self._process_symbol(symbol, processed_data)

                # Управление временем
                self._sleep_until_next_iteration(start_time)

        except KeyboardInterrupt:
            logging.info("Bot stopped by user")
        except Exception as e:
            logging.critical(f"Critical error: {str(e)}", exc_info=True)
        finally:
            logging.info("Trading bot stopped")

    def _sleep_until_next_iteration(self, start_time: datetime):
        """Контроль временных интервалов"""
        elapsed = (datetime.now() - start_time).total_seconds()
        sleep_time = max(0, BOT_SLEEP_INTERVAL * 60 - elapsed - 5)
        logging.info(f"Sleeping for {sleep_time:.1f} seconds")
        time.sleep(sleep_time)

if __name__ == "__main__":
    setup_logging()
    try:
        bot = TradingBot()
        bot.run()
    except Exception as e:
        logging.critical(f"Startup failed: {str(e)}", exc_info=True)
        raise