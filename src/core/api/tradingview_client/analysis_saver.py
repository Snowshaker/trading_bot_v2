# src/core/api/tradingview_client/analysis_saver.py
from decimal import Decimal
import json
from datetime import datetime
from pathlib import Path
from typing import Dict

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)

class AnalysisSaver:
    def __init__(self, storage_path: Path = Path("collected_data/tradingview_analysis")):
        self.storage = storage_path
        self.storage.mkdir(parents=True, exist_ok=True)

    def _transform_entry(self, symbol: str, data: Dict) -> Dict:
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "symbol": symbol,
            "timeframes": {
                tf: {
                    "score": float(item["score"]),
                    "recommendation": item["recommendation"]
                }
                for tf, item in data.items()
            }
        }

    def save_symbol_data(self, symbol: str, data: Dict):
        transformed = self._transform_entry(symbol, data)
        file_path = self.storage / f"{symbol}.jsonl"
        try:
            with open(file_path, "a") as f:
                f.write(json.dumps(transformed, cls=DecimalEncoder) + "\n")
        except IOError as e:
            print(f"Save error for {symbol}: {str(e)}")

    # Добавляем отсутствующий метод
    def batch_save(self, all_data: Dict[str, Dict]):
        """Пакетное сохранение данных для всех символов"""
        for symbol, data in all_data.items():
            self.save_symbol_data(symbol, data)