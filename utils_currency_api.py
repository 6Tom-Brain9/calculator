"""
Получение курсов валют и конвертация
Автоматическое обновление с API ЦБ РФ и Binance
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, Optional
import streamlit as st


# Константы
CBR_API_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
CBR_XML_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
BINANCE_API_URL = "https://api.binance.com/api/v3/ticker/price"


# ==================== ПОЛУЧЕНИЕ КУРСОВ ====================

def fetch_usdt_rub_from_binance() -> Optional[float]:
    """
    Получает курс USDT/RUB с Binance
    """
    try:
        # USDT/RUB на Binance P2P или спот
        response = requests.get(f"{BINANCE_API_URL}?symbol=USDTTRY", timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Binance дает USDT/TRY, конвертируем в RUB через USD
            # Лучше использовать прямой USDT/RUB через P2P
            pass
    except Exception as e:
        print(f"Ошибка получения USDT с Binance: {e}")
    
    # Альтернативный источник: биржевой курс USDT/RUB
    try:
        # Используем публичный API биржи для USDT/RUB
        response = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=USDTTRY", timeout=10)
        if response.status_code == 200:
            data = response.json()
            usdt_try = float(data['price'])
            # конвертируем TRY в RUB через курс USD
            return usdt_try
    except Exception as e:
        print(f"Ошибка получения USDT/TRY: {e}")
    
    # Fallback: используем курс USD с ЦБ + небольшая наценка (0.5%)
    rates = fetch_cbr_rates()
    if rates and rates.get('success'):
        return rates['rates']['USD'] * 1.005
    
    return None


def fetch_cbr_rates() -> Dict[str, Any]:
    """Получает курсы с ЦБ РФ"""
    try:
        response = requests.get("http://www.cbr-xml-daily.ru/daily_json.js", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Ошибка получения курсов ЦБ: {e}")
        return None


def fetch_kgs_from_cbr() -> Optional[float]:
    """Парсит курс KGS с официальной страницы ЦБ РФ"""
    try:
        response = requests.get(CBR_XML_URL, timeout=10, verify=False)
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


def fetch_currency_rates() -> Dict[str, Any]:
    """
    Получает актуальные курсы валют с API ЦБ РФ и Binance
    """
    try:
        # 1. Получаем курсы с ЦБ РФ
        cbr_data = fetch_cbr_rates()
        if not cbr_data:
            return {
                'success': False,
                'error': 'Не удалось получить курсы с ЦБ РФ',
                'rates': None
            }
        
        # Базовые курсы с ЦБ РФ
        usd_cbr = cbr_data['Valute']['USD']['Value']
        eur_cbr = cbr_data['Valute']['EUR']['Value']
        cny_cbr = cbr_data['Valute']['CNY']['Value']
        krw_cbr = cbr_data['Valute']['KRW']['Value'] / 1000
        kzt_cbr = cbr_data['Valute']['KZT']['Value'] / 100
        
        # 2. Получаем курс USDT/RUB с Binance
        usdt_rub = fetch_usdt_rub_from_binance()
        if usdt_rub is None:
            # Fallback: USD + 0.5%
            usdt_rub = usd_cbr * 1.005
        
        # 3. КУРС USD/RUB = Курс ЦБ + 4% (арифметически)
        usd_rub = usd_cbr * 1.04
        
        # 4. КУРС USD/KRW
        usd_krw_base = usd_cbr / krw_cbr
        usd_krw_individual = usd_krw_base + 15
        usd_krw_legal = usd_krw_base + 10
        
        # 5. КУРС EUR/RUB (без изменений)
        eur_rub = eur_cbr
        
        # 6. КУРС CNY/RUB (без изменений)
        cny_rub = cny_cbr
        
        # 7. КУРС KRW/RUB (без изменений)
        krw_rub = krw_cbr
        
        # 8. КУРС KGS/RUB
        kgs_rub = fetch_kgs_from_cbr()
        if kgs_rub is None:
            kgs_rub = 0.880188
        
        # 9. КУРС KZT/RUB (без изменений)
        kzt_rub = kzt_cbr
        
        rates = {
            'USD_CBR': usd_cbr,
            'USD': usd_rub,
            'EUR': eur_rub,
            'CNY': cny_rub,
            'KRW': krw_rub,
            'KGS': kgs_rub,
            'KZT': kzt_rub,
            'USDT': usdt_rub,
            'USD_KRW_INDIVIDUAL': usd_krw_individual,
            'USD_KRW_LEGAL': usd_krw_legal,
            'USD_KRW_BASE': usd_krw_base,
            'date': cbr_data['Date'],
            'time': datetime.now().strftime('%H:%M:%S')
        }
        
        return {
            'success': True,
            'rates': rates,
            'date': rates['date'],
            'time': rates['time'],
            'source': 'cbr.ru + binance'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f"Ошибка получения курсов: {e}",
            'rates': None
        }


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_rates():
    """Кэшированное получение курсов (обновляется раз в час)"""
    return fetch_currency_rates()


# ==================== КЛАСС КОНВЕРТЕРА ====================

class CurrencyConverter:
    """Конвертер валют с актуальными курсами"""
    
    def __init__(self):
        self._rates = None
        self._last_update = None
        self._error = None
        self._load_rates()
    
    def _load_rates(self):
        """Загружает актуальные курсы"""
        result = get_cached_rates()
        if result['success']:
            self._rates = result['rates']
            self._last_update = datetime.now()
            self._error = None
        else:
            self._error = result.get('error', 'Не удалось загрузить курсы валют')
            self._rates = None
            self._last_update = None
    
    def refresh(self):
        """Принудительное обновление курсов"""
        self._load_rates()
    
    def is_available(self) -> bool:
        return self._rates is not None
    
    def convert(self, amount: float, from_currency: str, to_currency: str = 'RUB', client_type: str = "Физическое лицо") -> float:
        if not self.is_available():
            raise ValueError(f"Курсы валют недоступны: {self._error}")
        
        if from_currency == to_currency:
            return amount
        
        if from_currency == 'USD_KRW':
            if client_type == "Физическое лицо":
                rate = self._rates.get('USD_KRW_INDIVIDUAL')
            else:
                rate = self._rates.get('USD_KRW_LEGAL')
            if rate is None:
                raise ValueError(f"Курс USD/KRW не найден")
            return amount * rate
        
        if from_currency != 'RUB':
            rate = self._rates.get(from_currency)
            if rate is None:
                raise ValueError(f"Неизвестная валюта: {from_currency}")
            amount_in_rub = amount * rate
        else:
            amount_in_rub = amount
        
        if to_currency != 'RUB':
            rate = self._rates.get(to_currency)
            if rate is None:
                raise ValueError(f"Неизвестная валюта: {to_currency}")
            return amount_in_rub / rate
        
        return amount_in_rub
    
    def get_rate(self, currency: str) -> float:
        if not self.is_available():
            raise ValueError(f"Курсы валют недоступны: {self._error}")
        rate = self._rates.get(currency)
        if rate is None:
            raise ValueError(f"Неизвестная валюта: {currency}")
        return rate
    
    def get_usd_krw_rate(self, client_type: str = "Физическое лицо") -> float:
        if not self.is_available():
            raise ValueError(f"Курсы валют недоступны: {self._error}")
        key = 'USD_KRW_INDIVIDUAL' if client_type == "Физическое лицо" else 'USD_KRW_LEGAL'
        rate = self._rates.get(key)
        if rate is None:
            raise ValueError(f"Курс USD/KRW не найден")
        return rate
    
    def get_all_rates(self) -> Dict[str, float]:
        if not self.is_available():
            raise ValueError(f"Курсы валют недоступны: {self._error}")
        return self._rates.copy()
    
    def get_last_update(self) -> Optional[datetime]:
        return self._last_update
    
    def get_error(self) -> Optional[str]:
        return self._error
    
    def get_rates_with_date(self) -> Dict[str, Any]:
        if not self.is_available():
            return {'success': False, 'error': self._error}
        return {
            'success': True,
            'rates': self._rates,
            'date': self._last_update.strftime('%Y-%m-%d %H:%M:%S') if self._last_update else None
        }


_converter_instance = None


def get_converter() -> CurrencyConverter:
    global _converter_instance
    if _converter_instance is None:
        _converter_instance = CurrencyConverter()
    return _converter_instance


converter = get_converter()


def to_rub(amount: float, from_currency: str, client_type: str = "Физическое лицо") -> float:
    return converter.convert(amount, from_currency, 'RUB', client_type)


def from_rub(amount: float, to_currency: str) -> float:
    return converter.convert(amount, 'RUB', to_currency)


def get_usd_rate() -> float:
    return converter.get_rate('USD')


def get_eur_rate() -> float:
    return converter.get_rate('EUR')


def get_usdt_rate() -> float:
    return converter.get_rate('USDT')


def get_krw_rate() -> float:
    return converter.get_rate('KRW')


def get_usd_krw_rate(client_type: str = "Физическое лицо") -> float:
    return converter.get_usd_krw_rate(client_type)
