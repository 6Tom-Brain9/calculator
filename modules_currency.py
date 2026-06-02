"""
Получение курсов валют и конвертация
Единый модуль для работы с валютами
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, Optional
import streamlit as st


# Константы
CBR_API_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
CBR_XML_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
WISE_API_URL = "https://wise.com/rates/api/v2/rates"

# Fallback-курсы (из вашего файла)
FALLBACK_RATES = {
    'USD': 76.9724,
    'EUR': 90.012,
    'CNY': 11.2521,
    'KRW': 51.9698,
    'KGS': 0.880188,
    'KZT': 16.0419
}


# ==================== ПОЛУЧЕНИЕ КУРСОВ ====================

def fetch_kgs_from_cbr() -> Optional[float]:
    """Парсит курс KGS с официальной страницы ЦБ РФ"""
    try:
        response = requests.get(CBR_XML_URL, timeout=10)
        response.encoding = 'windows-1251'
        root = ET.fromstring(response.text)
        
        for valute in root.findall('Valute'):
            char_code = valute.find('CharCode')
            if char_code is not None and char_code.text == 'KGS':
                value = valute.find('Value')
                if value is not None:
                    return float(value.text.replace(',', '.'))
        return None
    except Exception as e:
        print(f"Ошибка получения KGS с ЦБ: {e}")
        return None


def fetch_kgs_from_wise() -> Optional[float]:
    """Fallback: получает курс KGS с Wise API"""
    try:
        params = {'source': 'KGS', 'target': 'RUB', 'amount': 100}
        response = requests.get(WISE_API_URL, params=params, timeout=10)
        data = response.json()
        return data.get('rate')
    except Exception as e:
        print(f"Ошибка получения KGS с Wise: {e}")
        return FALLBACK_RATES['KGS']  # fallback


def fetch_currency_rates() -> Dict[str, Any]:
    """Получает актуальные курсы валют с API ЦБ РФ"""
    try:
        response = requests.get(CBR_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        rates = {
            'USD': data['Valute']['USD']['Value'],
            'EUR': data['Valute']['EUR']['Value'],
            'CNY': data['Valute']['CNY']['Value'],
            'KRW': data['Valute']['KRW']['Value'] / 1000,
            'KZT': data['Valute']['KZT']['Value'] / 100,
            'KGS': None,
            'date': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Получаем курс KGS
        kgs_rate = fetch_kgs_from_cbr()
        rates['KGS'] = kgs_rate if kgs_rate else fetch_kgs_from_wise()
        
        return {'success': True, 'rates': rates, 'date': rates['date'], 'source': 'cbr.ru'}
        
    except Exception as e:
        return {'success': False, 'error': str(e), 'rates': FALLBACK_RATES, 'date': None, 'source': 'fallback'}


@st.cache_data(ttl=3600)
def get_cached_rates():
    """Кэшированное получение курсов (обновляется раз в час)"""
    return fetch_currency_rates()


# ==================== КОНВЕРТАЦИЯ ====================

class CurrencyConverter:
    """
    Конвертер валют (использует актуальные курсы с кэшированием)
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_converter()
        return cls._instance
    
    def _init_converter(self):
        self._rates = None
        self._last_update = None
        self._load_rates()
    
    def _load_rates(self):
        """Загружает актуальные курсы"""
        result = get_cached_rates()
        if result['success']:
            self._rates = result['rates']
        else:
            self._rates = FALLBACK_RATES.copy()
        self._last_update = datetime.now()
    
    def refresh(self):
        """Принудительное обновление курсов"""
        self._load_rates()
    
    def convert(self, amount: float, from_currency: str, to_currency: str = 'RUB') -> float:
        """
        Конвертирует сумму из одной валюты в другую
        
        Примеры:
            converter.convert(50000, 'USD', 'RUB')  # 50000 USD → RUB
            converter.convert(1000000, 'RUB', 'USD')  # 1 млн RUB → USD
            converter.convert(2500, 'KRW', 'RUB')  # 2500 вон → RUB
        """
        if from_currency == to_currency:
            return amount
        
        # Переводим в RUB
        if from_currency != 'RUB':
            rate = self._rates.get(from_currency)
            if rate is None:
                raise ValueError(f"Неизвестная валюта: {from_currency}")
            amount_in_rub = amount * rate
        else:
            amount_in_rub = amount
        
        # Переводим из RUB в целевую валюту
        if to_currency != 'RUB':
            rate = self._rates.get(to_currency)
            if rate is None:
                raise ValueError(f"Неизвестная валюта: {to_currency}")
            return amount_in_rub / rate
        
        return amount_in_rub
    
    def get_rate(self, currency: str) -> float:
        """Возвращает курс валюты к RUB"""
        return self._rates.get(currency, 0)
    
    def get_all_rates(self) -> Dict[str, float]:
        """Возвращает все текущие курсы"""
        return self._rates.copy()
    
    def get_last_update(self) -> Optional[datetime]:
        """Возвращает дату последнего обновления курсов"""
        return self._last_update


# Создаем глобальный экземпляр (синглтон)
converter = CurrencyConverter()


# ==================== УДОБНЫЕ ФУНКЦИИ ДЛЯ БЫСТРОГО ДОСТУПА ====================

def to_rub(amount: float, from_currency: str) -> float:
    """Быстрая конвертация в рубли"""
    return converter.convert(amount, from_currency, 'RUB')


def from_rub(amount: float, to_currency: str) -> float:
    """Быстрая конвертация из рублей"""
    return converter.convert(amount, 'RUB', to_currency)


def get_usd_rate() -> float:
    """Курс USD/RUB"""
    return converter.get_rate('USD')


def get_eur_rate() -> float:
    """Курс EUR/RUB"""
    return converter.get_rate('EUR')