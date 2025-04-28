from src.core.api.tradingview_client.analysis_collector import AnalysisCollector
from src.core.api.tradingview_client.analysis_fetcher import TradingViewFetcher
from src.core.api.tradingview_client.analysis_saver import AnalysisSaver
from src.core.utils.analysis_printer import AnalysisPrinter
from pathlib import Path
import json

from rich.console import Console
console = Console(force_terminal=True, color_system="truecolor")

def test_full_flow():
    print("=== ТЕСТ ПОЛНОГО ЦИКЛА ===")

    # Инициализация
    test_storage = Path("test_data")
    fetcher = TradingViewFetcher(rate_limit_delay=1.0)
    saver = AnalysisSaver(test_storage)
    collector = AnalysisCollector(test_storage)
    printer = AnalysisPrinter(test_storage)  # Добавляем принтер

    # 1. Сбор данных
    print("\n[1] Сбор данных...")
    raw_data = fetcher.fetch_all_data()

    # 2. Сохранение
    print("\n[2] Сохранение...")
    saver.batch_save(raw_data)

    # 3. Проверка
    print("\n[3] Проверка целостности:")
    for symbol in raw_data.keys():
        saved = collector.get_latest(symbol)
        if saved:
            print(f"  {symbol}: OK ({len(saved['timeframes'])} таймфреймов)")
        else:
            print(f"  {symbol}: FAILED")

    # 4. Пример данных
    sample_symbol = next(iter(raw_data.keys()), None)
    if sample_symbol:
        print("\n[4] Пример данных:")
        print(json.dumps(collector.get_latest(sample_symbol), indent=2))

    # 5. Вывод через printer
    print("\n[5] Форматированный вывод:")
    printer.print_analysis()  # Добавляем вывод через printer

if __name__ == "__main__":
    test_full_flow()
    print("\nДля очистки выполните: rm -rf test_data/")