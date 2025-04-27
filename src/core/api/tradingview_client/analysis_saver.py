from datetime import datetime
from pathlib import Path
from typing import Dict
import json


class AnalysisSaver:
  def __init__(self, storage_path: Path = Path("collected_data/tradingview_analysis")):
    self.storage = storage_path
    self.storage.mkdir(parents=True, exist_ok=True)

  def _transform_data(self, raw_data: Dict) -> Dict:
    """Единый формат для всех компонентов"""
    return {
      "timestamp": datetime.utcnow().isoformat() + "Z",
      "symbol": raw_data["symbol"],
      "timeframes": {
        tf: {
          "score": data["score"],
          "recommendation": data["recommendation"]
        }
        for tf, data in raw_data["timeframes"].items()
      }
    }

  def save(self, symbol: str, fetched_data: Dict):
    """Сохраняет данные для одного символа"""
    transformed = self._transform_data({
      "symbol": symbol,
      "timeframes": fetched_data
    })

    file_path = self.storage / f"{symbol}.jsonl"
    try:
      with open(file_path, "a") as f:
        f.write(json.dumps(transformed) + "\n")
    except IOError as e:
      print(f"Save error for {symbol}: {str(e)}")

  def batch_save(self, all_data: Dict[str, Dict]):
    """Пакетное сохранение"""
    for symbol, data in all_data.items():
      self.save(symbol, data)