"""
Главный файл Streamlit-приложения
Калькулятор растаможки автомобилей из Китая и Кореи
"""

import streamlit as st
from datetime import datetime
from pathlib import Path
import requests
import urllib3
import yaml

# Отключаем SSL предупреждения
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="Калькулятор растаможки автомобилей",
    page_icon="🚗",
    layout="wide"
)


# ==================== ЗАГРУЗКА КОНФИГУРАЦИЙ ====================

def load_yaml_config(file_path):
    """Загружает YAML конфигурацию"""
    try:
        if Path(file_path).exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
    except Exception as e:
        st.warning(f"Ошибка загрузки {file_path}: {e}")
    return {}


# Загружаем все конфигурации
DATA_DIR = Path(__file__).parent / "data"

CONFIGS = {
    'currencies': load_yaml_config(DATA_DIR / "data_currencies.yaml"),
    'customs_rates': load_yaml_config(DATA_DIR / "data_customs_rates.yaml"),
    'utilization_rates': load_yaml_config(DATA_DIR / "data_utilization_rates.yaml"),
    'excise_rates': load_yaml_config(DATA_DIR / "data_excise_rates.yaml"),
    'delivery_costs': load_yaml_config(DATA_DIR / "data_delivery_costs.yaml"),
    'services': load_yaml_config(DATA_DIR / "data_services.yaml"),
    'coefficients': load_yaml_config(DATA_DIR / "data_coefficients.yaml"),
}


# ==================== КУРСЫ ВАЛЮТ (С АВТООБНОВЛЕНИЕМ) ====================

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_currency_rates():
    """Получает курсы с API ЦБ РФ (кэш на 1 час)"""
    try:
        response = requests.get("http://www.cbr-xml-daily.ru/daily_json.js", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                'USD': data['Valute']['USD']['Value'],
                'EUR': data['Valute']['EUR']['Value'],
                'CNY': data['Valute']['CNY']['Value'],
                'KRW': data['Valute']['KRW']['Value'] / 1000,
                'date': data['Date'],
                'success': True
            }
    except Exception as e:
        print(f"Ошибка получения курсов: {e}")
    
    return {'success': False}


def get_exchange_rates(force_refresh=False):
    """
    Возвращает курсы валют.
    Если force_refresh=True - игнорирует кэш и обновляет.
    """
    if force_refresh:
        st.cache_data.clear()
    
    rates = fetch_currency_rates()
    
    if rates['success']:
        return rates
    else:
        # Fallback из YAML
        currencies = CONFIGS.get('currencies', {})
        rates_data = currencies.get('currencies', {})
        return {
            'success': False,
            'USD': rates_data.get('USD', {}).get('rate', 90.0),
            'EUR': rates_data.get('EUR', {}).get('rate', 98.0),
            'CNY': rates_data.get('CNY', {}).get('rate', 12.5),
            'KRW': rates_data.get('KRW', {}).get('rate', 0.065),
            'date': datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        }


# ==================== ТАМОЖЕННАЯ ПОШЛИНА ====================

def get_customs_rate_by_value(customs_value_eur, rates_config):
    """Получает ставку пошлины по стоимости из YAML"""
    brackets = rates_config.get('individuals', {}).get('by_value', {}).get('brackets', [])
    
    for bracket in brackets:
        max_euro = bracket.get('max_euro')
        if max_euro is None or customs_value_eur <= max_euro:
            return bracket
    
    return brackets[-1] if brackets else {'percent': 48, 'min_per_cm3': 20}


def get_customs_rate_by_volume(engine_cc, age_years, rates_config):
    """Получает ставку пошлины по объему из YAML"""
    categories = rates_config.get('individuals', {}).get('by_volume', {}).get('categories', [])
    
    if 3 <= age_years <= 5:
        rate_key = 'rate_3_5'
    else:
        rate_key = 'rate_5plus'
    
    for cat in categories:
        min_cm3 = cat.get('min_cm3', 0)
        max_cm3 = cat.get('max_cm3')
        
        in_category = False
        if max_cm3 is None:
            if engine_cc >= min_cm3:
                in_category = True
        else:
            if min_cm3 <= engine_cc <= max_cm3:
                in_category = True
        
        if in_category:
            rate = cat.get(rate_key, 0)
            if rate == 0:
                return 3.6 if rate_key == 'rate_3_5' else 5.7
            return rate
    
    return 3.6 if (3 <= age_years <= 5) else 5.7


def calculate_customs_duty_individual(customs_value_rub, engine_cc, age_years, eur_rate):
    """Расчет таможенной пошлины для физических лиц"""
    customs_value_eur = customs_value_rub / eur_rate
    rates_config = CONFIGS.get('customs_rates', {})
    
    if age_years < 3:
        bracket = get_customs_rate_by_value(customs_value_eur, rates_config)
        by_percent = customs_value_eur * bracket['percent'] / 100
        by_volume = engine_cc * bracket['min_per_cm3']
        duty_eur = max(by_percent, by_volume)
        return duty_eur * eur_rate
    else:
        rate = get_customs_rate_by_volume(engine_cc, age_years, rates_config)
        duty_eur = engine_cc * rate
        return duty_eur * eur_rate


# ==================== УТИЛЬСБОР (НОВЫЕ ПРАВИЛА) ====================

def get_legal_coefficient(engine_cc, is_old, is_electric, rates_config):
    """Получает коммерческий коэффициент для юрлиц"""
    legal_config = rates_config.get('legal', {}).get('categories', [])
    current_year = datetime.now().year
    
    for cat in legal_config:
        if is_electric and not cat.get('is_electric'):
            continue
        if not is_electric and cat.get('is_electric'):
            continue
        
        min_eng = cat.get('min_engine', 0)
        max_eng = cat.get('max_engine')
        
        in_category = False
        if max_eng is None:
            if engine_cc >= min_eng:
                in_category = True
        else:
            if min_eng <= engine_cc <= max_eng:
                in_category = True
        
        if in_category:
            years_data = cat.get('years', {})
            for year in sorted(years_data.keys(), reverse=True):
                if year <= current_year:
                    year_data = years_data[year]
                    return year_data.get('old' if is_old else 'new', 1.0)
            return 1.0
    
    return 100.0 if is_old else 80.0


def calculate_utilization_fee(engine_cc, horsepower, age_years, is_electric=False, vehicle_type="Легковой", client_type="Физическое лицо"):
    """Расчет утилизационного сбора с учетом новых правил"""
    rates_config = CONFIGS.get('utilization_rates', {})
    is_old = age_years >= 3
    
    if client_type == "Физическое лицо":
        base_rate = rates_config.get('individuals', {}).get('base_rate', 20000)
        is_eligible = horsepower <= 160
        
        if is_electric:
            if horsepower <= 80:
                coeff = 0.17 if not is_old else 0.26
            else:
                coeff = get_legal_coefficient(engine_cc, is_old, is_electric, rates_config)
        else:
            if is_eligible and engine_cc <= 3000:
                coeff = 0.17 if not is_old else 0.26
            else:
                coeff = get_legal_coefficient(engine_cc, is_old, is_electric, rates_config)
        
        return base_rate * coeff
    else:
        if vehicle_type in ["Грузовой", "Пикап"]:
            base_rate = rates_config.get('truck', {}).get('base_rate', 150000)
        else:
            base_rate = rates_config.get('base_rate', 20000)
        
        coeff = get_legal_coefficient(engine_cc, is_old, is_electric, rates_config)
        return base_rate * coeff


# ==================== АКЦИЗ ====================

def get_excise_rate(horsepower, rates_config):
    """Получает ставку акциза из YAML"""
    rates = rates_config.get('rates', [])
    
    for bracket in rates:
        min_hp = bracket.get('min_hp', 0)
        max_hp = bracket.get('max_hp')
        
        if max_hp is None:
            if horsepower >= min_hp:
                return bracket.get('rate', 0)
        else:
            if min_hp <= horsepower <= max_hp:
                return bracket.get('rate', 0)
    
    return 0


def calculate_excise(horsepower, fuel_type):
    """Расчет акциза"""
    if fuel_type == "Электричка":
        return 0
    rate = get_excise_rate(horsepower, CONFIGS.get('excise_rates', {}))
    return horsepower * rate


# ==================== НДС ====================

def calculate_vat(customs_value, customs_duty, excise, client_type, destination):
    """Расчет НДС"""
    if client_type == "Физическое лицо":
        return 0
    
    base = customs_value + customs_duty + excise
    vat_rates = CONFIGS.get('coefficients', {}).get('taxes', {}).get('vat_import', {})
    
    if destination == "Бишкек":
        rate = vat_rates.get('kyrgyzstan_legal', 0.12)
    else:
        rate = vat_rates.get('legal', 0.20)
    
    return base * rate


# ==================== ДОСТАВКА И УСЛУГИ ====================

def get_delivery_cost(city, vehicle_type, delivery_config):
    """Получает стоимость доставки из YAML"""
    costs = delivery_config.get('delivery_costs', {})
    oversize_coeff = delivery_config.get('oversize_coefficient', 1.2)
    
    cost = costs.get(city, 150000)
    if vehicle_type in ["Грузовой", "Пикап"]:
        cost = cost * oversize_coeff
    
    return cost


def get_service_cost(service_name, vehicle_type="Легковой", country_export="Корея"):
    """Получение стоимости услуги из YAML"""
    services = CONFIGS.get('services', {}).get('services', {})
    
    if service_name == 'broker':
        return services.get('broker', {}).get(vehicle_type, 10000)
    elif service_name == 'epts':
        epts = services.get('epts', 15000)
        if country_export == "Китай":
            sbkts = services.get('sbkts', 20000)
            return max(epts, sbkts)
        return epts
    return 0


# ==================== ОСНОВНОЙ ИНТЕРФЕЙС ====================

def main():
    st.title("🚗 Калькулятор растаможки автомобилей")
    st.markdown("---")
    
    # Получаем курсы
    rates = get_exchange_rates()
    
    # Отображаем дату курсов и кнопку обновления
    col_date, col_btn = st.columns([3, 1])
    with col_date:
        if rates.get('success'):
            date_obj = datetime.fromisoformat(rates['date'].replace('Z', '+00:00'))
            st.caption(f"💱 Курсы валют от {date_obj.strftime('%d.%m.%Y %H:%M')} (источник: ЦБ РФ)")
        else:
            st.caption("⚠️ Курсы валют из резервного источника (ЦБ РФ недоступен)")
    with col_btn:
        if st.button("🔄 Обновить курсы", use_container_width=True):
            rates = get_exchange_rates(force_refresh=True)
            st.rerun()
    
    # Боковая панель с курсами
    with st.sidebar:
        st.header("💱 Текущие курсы")
        st.metric("🇺🇸 USD", f"{rates['USD']:.2f} ₽")
        st.metric("🇪🇺 EUR", f"{rates['EUR']:.2f} ₽")
        st.metric("🇨🇳 CNY", f"{rates['CNY']:.4f} ₽ (за 1 юань)")
        st.metric("🇰🇷 KRW", f"{rates['KRW']:.4f} ₽ (за 1 вону)")
        st.caption(f"*Курс воны: {rates['KRW']*1000:.2f} ₽ за 1000 вон")
        
        st.markdown("---")
        st.markdown("**📌 Новые правила утильсбора:**")
        st.caption("• До 160 л.с. → льготный (0.17)")
        st.caption("• Свыше 160 л.с. → коммерческие")
        st.caption("• Электро до 80 л.с. → льготный")
    
    # Форма ввода
    col1, col2 = st.columns(2)
    
    with col1:
        country_export = st.selectbox("🌏 Страна экспорта", ["Китай", "Корея"])
        city = st.selectbox("📍 Город доставки", [
            "Владивосток", "Москва", "Санкт-Петербург", "Новосибирск",
            "Екатеринбург", "Казань", "Краснодар", "Бишкек", "Алма-Аты"
        ])
        client_type = st.selectbox("👤 Тип клиента", ["Физическое лицо", "Юридическое лицо"])
        vehicle_type = st.selectbox("🚙 Тип транспорта", ["Легковой", "Грузовой", "Пикап", "Электричка"])
        fuel_type = st.selectbox("⛽ Тип топлива", ["Бензин", "Дизель", "Гибрид", "Электричка"])
    
    with col2:
        # Показываем правильную валюту в зависимости от страны
        if country_export == "Китай":
            price_currency = "CNY (юань)"
            price_placeholder = "Введите стоимость в юанях"
            price_rate = rates['CNY']
        else:
            price_currency = "KRW (вона)"
            price_placeholder = "Введите стоимость в вонах"
            price_rate = rates['KRW']
        
        st.metric("💵 Актуальный курс", f"1 {price_currency.split()[0]} = {price_rate:.4f} ₽")
        
        price = st.number_input(
            f"💰 Стоимость авто ({price_currency})",
            min_value=0.0,
            value=50000.0,
            step=5000.0,
            help=price_placeholder
        )
        
        # Показываем примерную цену в рублях
        price_rub_preview = price * price_rate
        st.caption(f"📌 Примерно: {price_rub_preview:,.0f} ₽ по текущему курсу")
        
        engine_cc = st.number_input("🔧 Объем двигателя", min_value=0, value=1997, step=100, help="куб.см")
        horsepower = st.number_input("⚡ Мощность", min_value=0.0, value=150.0, step=10.0, help="л.с.")
        weight = st.number_input("🏋️ Масса", min_value=0, value=1800, step=100, help="кг")
        manufacture_date = st.date_input("📅 Дата выпуска", value=datetime(2023, 1, 1))
    
    st.markdown("---")
    calculate = st.button("🧮 РАССЧИТАТЬ", type="primary", use_container_width=True)
    
    if calculate:
        # Расчет возраста
        age_years = (datetime.now() - datetime(manufacture_date.year, manufacture_date.month, manufacture_date.day)).days / 365.25
        age_years = round(age_years, 2)
        is_electric = fuel_type == "Электричка"
        
        # Конвертация в рубли по актуальному курсу
        if country_export == "Китай":
            price_rub = price * rates['CNY']
            price_currency_short = "CNY"
        else:
            price_rub = price * rates['KRW']
            price_currency_short = "KRW"
        
        # Комиссия дилера
        dealer_commission_coeff = CONFIGS.get('coefficients', {}).get('dealer_commission', {})
        if country_export == "Китай":
            dealer_commission = price_rub * dealer_commission_coeff.get('Китай', {}).get('value', 0.15)
        else:
            dealer_commission_usd = dealer_commission_coeff.get('Корея', {}).get('value', 2500)
            dealer_commission = dealer_commission_usd * rates['USD']
        
        # Доставка до границы
        delivery_to_border = 1500 * rates['USD']
        
        # Таможенная стоимость
        customs_value = price_rub + dealer_commission + delivery_to_border
        
        # Пошлина
        customs_duty = calculate_customs_duty_individual(customs_value, engine_cc, age_years, rates['EUR'])
        
        # Утильсбор
        utilization = calculate_utilization_fee(engine_cc, horsepower, age_years, is_electric, vehicle_type, client_type)
        
        # Акциз
        excise = calculate_excise(horsepower, fuel_type)
        
        # НДС
        vat = calculate_vat(customs_value, customs_duty, excise, client_type, city)
        
        # Доставка и услуги
        delivery_cost = get_delivery_cost(city, vehicle_type, CONFIGS.get('delivery_costs', {}))
        broker_cost = get_service_cost('broker', vehicle_type, country_export)
        epts_cost = get_service_cost('epts', vehicle_type, country_export)
        
        # ИТОГО
        total_cost = (
            customs_value + customs_duty + utilization +
            excise + vat + delivery_cost + broker_cost + epts_cost
        )
        
        # Отображение результатов
        st.markdown("---")
        st.header("📊 РЕЗУЛЬТАТ РАСЧЕТА")
        
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
                        padding: 1.5rem; border-radius: 1rem; text-align: center; margin: 1rem 0;">
                <h2 style="color: white; margin: 0;">СТОИМОСТЬ ПОД КЛЮЧ</h2>
                <p style="color: #ffd700; font-size: 2.5rem; font-weight: bold; margin: 0.5rem 0;">
                    {total_cost:,.0f} ₽
                </p>
                <p style="color: #ccc; margin: 0;">
                    {price:,.0f} {price_currency_short} × {price_rate:.4f} ₽ = {price_rub:,.0f} ₽
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        with st.expander("📋 Детальная разбивка", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**💰 За границей:**")
                st.write(f"• Авто: {price:,.0f} {price_currency_short} → {price_rub:,.0f} ₽")
                st.write(f"• Комиссия дилера: {dealer_commission:,.0f} ₽")
                st.write(f"• Фрахт: {delivery_to_border:,.0f} ₽")
                st.write(f"**• Таможенная стоимость: {customs_value:,.0f} ₽**")
                st.write("")
                st.write("**🛃 Таможня:**")
                st.write(f"• Пошлина: {customs_duty:,.0f} ₽")
                st.write(f"• Утильсбор: {utilization:,.0f} ₽")
                st.write(f"• Акциз: {excise:,.0f} ₽")
                st.write(f"• НДС: {vat:,.0f} ₽")
            with col2:
                st.write("**🚛 В РФ:**")
                st.write(f"• Доставка: {delivery_cost:,.0f} ₽")
                st.write(f"• Брокер: {broker_cost:,.0f} ₽")
                st.write(f"• ЭПТС: {epts_cost:,.0f} ₽")
        
        st.info(f"📅 Возраст: {age_years} лет | 💪 {horsepower} л.с. | ⚙️ {engine_cc} см³")
        
        if client_type == "Физическое лицо" and horsepower <= 160:
            st.success("✅ Льготная ставка утильсбора")
        elif client_type == "Физическое лицо":
            st.warning("⚠️ Коммерческая ставка утильсбора")
        
        st.caption("⚠️ Данный расчет является ознакомительным.")


if __name__ == "__main__":
    main()