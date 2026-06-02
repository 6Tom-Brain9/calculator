"""
Конфигурация калькулятора
"""

import os
from pathlib import Path

# Базовые пути
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"

# Создаем папки, если их нет
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Файлы данных (имена без слешей)
CURRENCIES_FILE = DATA_DIR / "currencies.yaml"
CUSTOMS_RATES_FILE = DATA_DIR / "customs_rates.yaml"
UTILIZATION_RATES_FILE = DATA_DIR / "utilization_rates.yaml"
EXCISE_RATES_FILE = DATA_DIR / "excise_rates.yaml"
DELIVERY_COSTS_FILE = DATA_DIR / "delivery_costs.yaml"
SERVICES_FILE = DATA_DIR / "services.yaml"
COEFFICIENTS_FILE = DATA_DIR / "coefficients.yaml"

# API ЦБ РФ
CBR_API_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
CBR_XML_URL = "https://www.cbr.ru/scripts/XML_daily.asp"  # для KGS

# Wise API (fallback)
WISE_API_URL = "https://wise.com/rates/api/v2/rates"

# Настройки приложения
APP_TITLE = "🚗 Калькулятор растаможки автомобилей"
APP_ICON = "🚗"
APP_LAYOUT = "wide"

# Варианты для выпадающих списков
COUNTRIES = ["Китай", "Корея"]

CITIES_RF = [
    "Владивосток", "Уссурийск", "Чита", "Улан-Удэ", "Иркутск", "Красноярск",
    "Кемерово", "Новосибирск", "Омск", "Тюмень", "Екатеринбург", "Челябинск",
    "Пермь", "Уфа", "Набережные Челны", "Ижевск", "Казань", "Чебоксары",
    "Нижний Новгород", "Самара", "Тольятти", "Пенза", "Саратов", "Москва",
    "Владимир", "Рязань", "Санкт-Петербург", "Краснодар", "Волгоград",
    "Ростов-на-Дону"
]

CITIES_ABROAD = ["Бишкек", "Алма-Аты", "Минск"]

ALL_CITIES = CITIES_RF + CITIES_ABROAD

VEHICLE_TYPES = ["Легковой", "Грузовой", "Пикап", "Мотоцикл", "Электричка"]
FUEL_TYPES = ["Бензин", "Дизель", "Гибрид", "Гибрид послед.", "Электричка"]
CLIENT_TYPES = ["Физическое лицо", "Юридическое лицо"]
CONDITIONS = ["Новый", "С пробегом"]