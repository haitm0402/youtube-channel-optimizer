import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fixture(name):
    return json.loads((ROOT / 'services' / 'mock_data' / f'{name}.json').read_text(encoding='utf-8'))


def example(name):
    return json.loads((ROOT / 'examples' / f'{name}.json').read_text(encoding='utf-8'))
