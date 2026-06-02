"""
Загрузчики YAML-файлов
"""

import yaml
from pathlib import Path
from typing import Dict, Any


def load_yaml(file_path: Path) -> Dict[str, Any]:
    """Загружает YAML-файл и возвращает словарь"""
    if not file_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_yaml(file_path: Path, data: Dict[str, Any]):
    """Сохраняет словарь в YAML-файл"""
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)