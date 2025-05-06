# tests/core/api/tradingview_client/test_analysis_collector.py
import pytest
from pathlib import Path
import json
from src.core.api.tradingview_client.analysis_collector import AnalysisCollector


@pytest.fixture
def collector(tmp_path):
  return AnalysisCollector(storage_path=tmp_path)


@pytest.fixture
def mock_symbols(monkeypatch):
    # Исправляем путь для мока на тот, где SYMBOLS импортированы в analysis_collector
    monkeypatch.setattr(
        'src.core.api.tradingview_client.analysis_collector.SYMBOLS',
        ['TEST1', 'TEST2', 'TEST3']
    )


def test_get_latest_for_symbol_exists(collector, tmp_path):
  symbol = 'TEST1'
  data = {'key': 'value'}
  file_path = tmp_path / f"{symbol}.jsonl"
  with open(file_path, 'w') as f:
    f.write(json.dumps({'key': 'old'}) + '\n')
    f.write(json.dumps(data) + '\n')

  result = collector.get_latest_for_symbol(symbol)
  assert result == data


def test_get_latest_for_symbol_empty_file(collector, tmp_path):
  symbol = 'TEST2'
  file_path = tmp_path / f"{symbol}.jsonl"
  file_path.touch()

  result = collector.get_latest_for_symbol(symbol)
  assert result is None


def test_get_latest_for_symbol_no_file(collector):
  symbol = 'NONEXISTENT'
  result = collector.get_latest_for_symbol(symbol)
  assert result is None


def test_get_latest_for_symbol_invalid_json(collector, tmp_path):
  symbol = 'TEST3'
  file_path = tmp_path / f"{symbol}.jsonl"
  with open(file_path, 'w') as f:
    f.write('invalid_json')

  result = collector.get_latest_for_symbol(symbol)
  assert result is None


def test_get_all_latest(collector, tmp_path, mock_symbols):
  # Подготовка данных
  data1 = {'test': 'data1'}
  data2 = {'test': 'data2'}
  (tmp_path / 'TEST1.jsonl').write_text(json.dumps(data1) + '\n')
  (tmp_path / 'TEST2.jsonl').write_text(json.dumps({'old': 'data'}) + '\n' + json.dumps(data2) + '\n')

  result = collector.get_all_latest()
  assert 'TEST1' in result
  assert result['TEST1'] == data1
  assert 'TEST2' in result
  assert result['TEST2'] == data2
  assert 'TEST3' not in result


def test_get_history(collector, tmp_path):
  symbol = 'TEST1'
  history = [{'id': i} for i in range(150)]
  file_path = tmp_path / f"{symbol}.jsonl"
  with open(file_path, 'w') as f:
    for item in history:
      f.write(json.dumps(item) + '\n')

  result = collector.get_history(symbol, limit=100)
  assert len(result) == 100
  assert result == history[-100:]


def test_get_history_limit_exceeds(collector, tmp_path):
  symbol = 'TEST2'
  history = [{'id': i} for i in range(50)]
  file_path = tmp_path / f"{symbol}.jsonl"
  with open(file_path, 'w') as f:
    for item in history:
      f.write(json.dumps(item) + '\n')

  result = collector.get_history(symbol, limit=100)
  assert len(result) == 50
  assert result == history


def test_get_history_file_not_found(collector):
  symbol = 'NONEXISTENT'
  result = collector.get_history(symbol)
  assert result == []


def test_get_history_invalid_json_raises_error(collector, tmp_path):
  symbol = 'TEST3'
  file_path = tmp_path / f"{symbol}.jsonl"
  with open(file_path, 'w') as f:
    f.write('invalid_json\n')
    f.write(json.dumps({'valid': True}) + '\n')

  # Проверяем, что возникает ошибка JSONDecodeError при чтении невалидной строки
  with pytest.raises(json.JSONDecodeError):
    collector.get_history(symbol)