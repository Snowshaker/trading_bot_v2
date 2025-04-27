from pathlib import Path
import json
from typing import Dict, List, Any

class AnalysisCollector:
    def __init__(self, storage_path: Path = Path("collected_data/tradingview_analysis")):
        self.storage = storage_path

    def get_latest(self, symbol: str) -> Dict:
        """Получает данные в том же формате, что и Saver"""
        file_path = self.storage / f"{symbol}.jsonl"
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()
                return json.loads(lines[-1]) if lines else {}
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Read error for {symbol}: {str(e)}")
            return {}

    def get_history(self, symbol: str, limit: int = 10) -> list:
        """История записей для отладки"""
        file_path = self.storage / f"{symbol}.jsonl"
        try:
            with open(file_path, "r") as f:
                return [json.loads(line) for line in f.readlines()[-limit:]]
        except FileNotFoundError:
            return []