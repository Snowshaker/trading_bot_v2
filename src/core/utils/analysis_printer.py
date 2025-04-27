from pathlib import Path
import json
from datetime import datetime, UTC, timedelta
from typing import Dict, Optional
from rich.console import Console
from rich.table import Table
from rich import box
from src.core.settings.config import SYMBOLS, TIMEFRAMES


class AnalysisPrinter:
    def __init__(self, data_dir: Path = Path("collected_data/tradingview_analysis")):
        self.data_dir = data_dir
        self.console = Console(force_terminal=True)
        self.data = self._load_data()
        self.now = datetime.now(UTC)

    def _get_score_style(self, score: int) -> str:
        """Возвращает строку с тегами стиля для score"""
        if score == 2:
          return "[bright_cyan]"
        elif score == 1:
            return "[bold green]"
        elif score == 0:
            return "[bold yellow]"
        elif score == -1:
          return "[bold red]"
        elif score == -2:
          return "[rgb(128,0,128)]"

    def _get_age_style(self, timestamp: datetime) -> str:
        """Возвращает строку с тегами стиля для времени"""
        delta = self.now - timestamp
        if delta > timedelta(minutes=10):
            return "[bold red on white]"
        elif delta > timedelta(minutes=5):
            return "[bold yellow]"
        return "[bold green]"

    def _load_symbol_data(self, symbol: str) -> Optional[Dict]:
        file_path = self.data_dir / f"{symbol}.jsonl"
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()
                return json.loads(lines[-1]) if lines else None
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _load_data(self) -> Dict[str, Dict]:
        return {symbol: self._load_symbol_data(symbol) for symbol in SYMBOLS}

    def _get_oldest_timestamp(self) -> Optional[datetime]:
        timestamps = [
            datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
            for data in self.data.values() if data
        ]
        return min(timestamps) if timestamps else None

    def print_analysis(self):
      """Выводит форматированную таблицу с анализом"""
      oldest = self._get_oldest_timestamp()

      # Формируем строку с датой последнего обновления данных
      last_updated = (
        f"[yellow]{oldest.strftime('%Y-%m-%d %H:%M:%S')}[/yellow]"
        if oldest
        else "[red]N/A[/red]"
      )

      table = Table(
        title="[bold cyan]TradingView Analysis Dashboard[/bold cyan]",
        box=box.ROUNDED,
        header_style="bold rgb(0,0,0) on rgb(255,255,255)",
        caption=f"Last updated: {last_updated}",  # Используем oldest вместо текущего времени
        caption_style="italic grey50"
      )

      # Настройка колонок
      table.add_column("Symbol", style="rgb(50,0,255)", width=12)
      for tf in TIMEFRAMES:
        table.add_column(tf, justify="right", width=8)

      # Заполнение данных
      for symbol, data in self.data.items():
        if not data:
          continue

        row = [f"[bold]{symbol}[/bold]"]
        for tf in TIMEFRAMES:
          if tf in data["timeframes"]:
            score = data["timeframes"][tf]["score"]
            style = self._get_score_style(score)
            row.append(f"{style}{score}[/]")
          else:
            row.append("[grey58]N/A[/grey58]")

        table.add_row(*row)

      self.console.print(table)


if __name__ == "__main__":
    printer = AnalysisPrinter()
    printer.print_analysis()