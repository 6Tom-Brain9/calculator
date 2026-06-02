"""
Валидаторы входных данных
"""

from datetime import datetime
from typing import Tuple, Optional


def validate_engine_cc(engine_cc: float) -> Tuple[bool, str]:
    """Проверка объема двигателя"""
    if engine_cc <= 0:
        return False, "Объем двигателя должен быть больше 0"
    if engine_cc > 20000:
        return False, "Объем двигателя не может превышать 20000 куб.см"
    return True, "OK"


def validate_horsepower(hp: float) -> Tuple[bool, str]:
    """Проверка мощности"""
    if hp <= 0:
        return False, "Мощность должна быть больше 0"
    if hp > 2000:
        return False, "Мощность не может превышать 2000 л.с."
    return True, "OK"


def validate_weight(weight: float) -> Tuple[bool, str]:
    """Проверка массы"""
    if weight <= 0:
        return False, "Масса должна быть больше 0"
    if weight > 50000:
        return False, "Масса не может превышать 50000 кг"
    return True, "OK"


def validate_price(price: float) -> Tuple[bool, str]:
    """Проверка стоимости"""
    if price <= 0:
        return False, "Стоимость должна быть больше 0"
    if price > 10000000:
        return False, "Стоимость не может превышать 10 млн (слишком дорого)"
    return True, "OK"


def validate_manufacture_date(date_str) -> Tuple[bool, Optional[datetime], str]:
    """Проверка даты выпуска (принимает строку или datetime/date объект)"""
    try:
        # Если пришел datetime или date объект
        if hasattr(date_str, 'strftime'):
            date = date_str
        else:
            # Если пришла строка
            date = datetime.strptime(str(date_str), '%Y-%m-%d')
        
        # Сравниваем с текущей датой
        if date > datetime.now().date() if hasattr(date, 'date') else date > datetime.now():
            return False, None, "Дата выпуска не может быть в будущем"
        
        if date.year < 2000:
            return False, None, "Автомобиль не может быть старше 2000 года"
        
        return True, date, "OK"
        
    except Exception as e:
        return False, None, f"Неверный формат даты. Ошибка: {e}"


def calculate_age(manufacture_date) -> float:
    """Расчет возраста автомобиля в годах (работает с datetime и date)"""
    today = datetime.now()
    
    # Если manufacture_date - date объект, конвертируем в datetime
    if hasattr(manufacture_date, 'strftime') and not hasattr(manufacture_date, 'hour'):
        manufacture_datetime = datetime(manufacture_date.year, manufacture_date.month, manufacture_date.day)
    else:
        manufacture_datetime = manufacture_date
    
    age_years = (today - manufacture_datetime).days / 365.25
    return round(age_years, 2)


def validate_all_inputs(data: dict) -> dict:
    """
    Валидация всех входных данных
    
    Args:
        data: словарь с полями:
            - engine_cc: float
            - horsepower: float
            - weight: float
            - price: float
            - manufacture_date: str или date/datetime
    
    Returns:
        dict с полями:
            - valid: bool
            - errors: list of str
            - age: float (если валидно)
    """
    errors = []
    
    # Проверка объема
    if 'engine_cc' in data:
        valid, msg = validate_engine_cc(data['engine_cc'])
        if not valid:
            errors.append(msg)
    
    # Проверка мощности
    if 'horsepower' in data:
        valid, msg = validate_horsepower(data['horsepower'])
        if not valid:
            errors.append(msg)
    
    # Проверка массы
    if 'weight' in data:
        valid, msg = validate_weight(data['weight'])
        if not valid:
            errors.append(msg)
    
    # Проверка стоимости
    if 'price' in data:
        valid, msg = validate_price(data['price'])
        if not valid:
            errors.append(msg)
    
    # Проверка даты выпуска
    manufacture_date = data.get('manufacture_date')
    if manufacture_date:
        valid, date, msg = validate_manufacture_date(manufacture_date)
        if not valid:
            errors.append(msg)
    else:
        errors.append("Дата выпуска не указана")
        date = None
    
    if errors:
        return {
            'valid': False,
            'errors': errors,
            'age': None
        }
    
    return {
        'valid': True,
        'errors': [],
        'age': calculate_age(date) if date else None
    }