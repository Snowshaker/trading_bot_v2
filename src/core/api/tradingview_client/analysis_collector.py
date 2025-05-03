# src/core/api/tradingview_client/analysis_collector.py
from pathlib import Path
import json
from typing import Dict, Optional, List
from src.core.settings.config import SYMBOLS
from src.core.paths import TW_ANALYSIS

class AnalysisCollector:
    def __init__(self, storage_path: Path = TW_ANALYSIS):
        self.storage = storage_path

    def get_latest_for_symbol(self, symbol: str) -> Optional[Dict]:
        """Получение последней записи для конкретного символа"""
        file_path = self.storage / f"{symbol}.jsonl"
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()
                return json.loads(lines[-1]) if lines else None
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def get_all_latest(self) -> Dict[str, Dict]:
        """Получение последних данных для всех символов"""
        processed_data = {}
        for symbol in SYMBOLS:
            data = self.get_latest_for_symbol(symbol)
            if data:
                processed_data[symbol] = data
        return processed_data

    def get_history(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Получение истории записей для символа"""
        file_path = self.storage / f"{symbol}.jsonl"
        try:
            with open(file_path, "r") as f:
                return [json.loads(line) for line in f.readlines()[-limit:]]
        except FileNotFoundError:
            return []