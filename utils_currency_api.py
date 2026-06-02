"""
Получение курсов валют и конвертация
Автоматическое обновление с API ЦБ РФ
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, Optional
import streamlit as st
import urllib3

# Отключаем предупреждения о небезопасном SSL (для ЦБ РФ)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Константы
CBR_API_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
CBR_XML_URL = "https://www.cbr.ru/scripts/XML_daily.asp"


# ==================== ПОЛУЧЕНИЕ КУРСОВ ====================

def fetch_kgs_from_cbr() -> Optional[float]:
    """Парсит курс KGS с официальной страницы ЦБ РФ"""
    try:
        # Добавляем verify=False для обхода SSL проблем
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
    Получает актуальные курсы валют с API ЦБ РФ
    """
    try:
        # Добавляем verify=False для обхода SSL проблем
        response = requests.get(CBR_API_URL, timeout=10, verify=False)
        response.raise_for_status()
        data = response.json()
        
        rates = {
            'USD': data['Valute']['USD']['Value'],
            'EUR': data['Valute']['EUR']['Value'],
            'CNY': data['Valute']['CNY']['Value'],
            'KRW': data['Valute']['KRW']['Value'] / 1000,
            'KZT': data['Valute']['KZT']['Value'] / 100,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S')
        }
        
        # Получаем курс KGS отдельно
        kgs_rate = fetch_kgs_from_cbr()
        if kgs_rate:
            rates['KGS'] = kgs_rate
        else:
            rates['KGS'] = None
        
        return {
            'success': True,
            'rates': rates,
            'date': rates['date'],
            'time': rates['time'],
            'source': 'cbr.ru'
        }
        
    except requests.exceptions.SSLError as e:
        # Пробуем альтернативный источник
        return fetch_currency_rates_alternative()
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': f"Ошибка соединения с ЦБ РФ: {e}",
            'rates': None
        }
    except KeyError as e:
        return {
            'success': False,
            'error': f"Неожиданный формат ответа от ЦБ РФ: {e}",
            'rates': None
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Неизвестная ошибка: {e}",
            'rates': None
        }


def fetch_currency_rates_alternative() -> Dict[str, Any]:
    """
    Альтернативный источник курсов (без SSL проблем)
    Использует тот же API но через другой порт/протокол
    """
    try:
        # Пробуем http вместо https
        url_http = "http://www.cbr-xml-daily.ru/daily_json.js"
        response = requests.get(url_http, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        rates = {
            'USD': data['Valute']['USD']['Value'],
            'EUR': data['Valute']['EUR']['Value'],
            'CNY': data['Valute']['CNY']['Value'],
            'KRW': data['Valute']['KRW']['Value'] / 1000,
            'KZT': data['Valute']['KZT']['Value'] / 100,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S')
        }
        
        # Пробуем получить KGS
        try:
            response_xml = requests.get(CBR_XML_URL, timeout=10, verify=False)
            response_xml.encoding = 'windows-1251'
            root = ET.fromstring(response_xml.text)
            for valute in root.findall('Valute'):
                char_code = valute.find('CharCode')
                if char_code is not None and char_code.text == 'KGS':
                    value = valute.find('Value')
                    if value is not None:
                        rates['KGS'] = float(value.text.replace(',', '.'))
                        break
        except:
            rates['KGS'] = None
        
        return {
            'success': True,
            'rates': rates,
            'date': rates['date'],
            'time': rates['time'],
            'source': 'cbr.ru (http)'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f"Ошибка соединения с ЦБ РФ (http): {e}",
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
            # Проверяем, что все нужные курсы получены
            required = ['USD', 'EUR', 'CNY', 'KRW', 'KZT']
            missing = [c for c in required if result['rates'].get(c) is None]
            
            if missing:
                self._error = f"Не удалось получить курсы для: {', '.join(missing)}"
                self._rates = None
                self._last_update = None
            else:
                self._rates = result['rates']
                self._last_update = datetime.now()
                self._error = None
                
                # Если KGS не получен, это не критично
                if self._rates.get('KGS') is None:
                    self._rates['KGS'] = 0.880188  # Временный курс для KGS
                    
        else:
            self._error = result.get('error', 'Не удалось загрузить курсы валют')
            self._rates = None
            self._last_update = None
    
    def refresh(self):
        """Принудительное обновление курсов"""
        self._load_rates()
    
    def is_available(self) -> bool:
        """Проверяет, доступны ли курсы валют"""
        return self._rates is not None
    
    def convert(self, amount: float, from_currency: str, to_currency: str = 'RUB') -> float:
        """
        Конвертирует сумму из одной валюты в другую
        """
        if not self.is_available():
            raise ValueError(f"Курсы валют недоступны: {self._error}")
        
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
        if not self.is_available():
            raise ValueError(f"Курсы валют недоступны: {self._error}")
        rate = self._rates.get(currency)
        if rate is None:
            raise ValueError(f"Неизвестная валюта: {currency}")
        return rate
    
    def get_all_rates(self) -> Dict[str, float]:
        """Возвращает все текущие курсы"""
        if not self.is_available():
            raise ValueError(f"Курсы валют недоступны: {self._error}")
        return self._rates.copy()
    
    def get_last_update(self) -> Optional[datetime]:
        """Возвращает дату последнего обновления курсов"""
        return self._last_update
    
    def get_error(self) -> Optional[str]:
        """Возвращает ошибку, если курсы недоступны"""
        return self._error
    
    def get_rates_with_date(self) -> Dict[str, Any]:
        """Возвращает курсы с датой обновления"""
        if not self.is_available():
            return {'success': False, 'error': self._error}
        return {
            'success': True,
            'rates': self._rates,
            'date': self._last_update.strftime('%Y-%m-%d %H:%M:%S') if self._last_update else None
        }


# Создаем глобальный экземпляр
_converter_instance = None


def get_converter() -> CurrencyConverter:
    """Возвращает глобальный экземпляр конвертера"""
    global _converter_instance
    if _converter_instance is None:
        _converter_instance = CurrencyConverter()
    return _converter_instance


# Для удобного импорта
converter = get_converter()


# ==================== УДОБНЫЕ ФУНКЦИИ ====================

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