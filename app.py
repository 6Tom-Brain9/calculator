import streamlit as st
from datetime import datetime
from pathlib import Path
import requests
import urllib3
import yaml

# Отключаем SSL предупреждения
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="🚗 Калькулятор растаможки автомобилей",
    page_icon="🚗",
    layout="wide"
)

# ==================== ИНИЦИАЛИЗАЦИЯ ====================
if 'hp_kw' not in st.session_state:
    st.session_state.hp_kw = 0.0
if 'hp_hp' not in st.session_state:
    st.session_state.hp_hp = 0.0

# ==================== ЗАГРУЗКА YAML ====================

def load_yaml_config(file_path):
    try:
        if Path(file_path).exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                return data
        else:
            return {}
    except Exception as e:
        st.warning(f"Ошибка загрузки {file_path}: {e}")
        return {}

def load_all_configs():
    DATA_DIR = Path(__file__).parent / "data"
    return {
        'utilization_rates': load_yaml_config(DATA_DIR / "data_utilization_rates.yaml"),
        'currencies': load_yaml_config(DATA_DIR / "data_currencies.yaml"),
        'customs_rates': load_yaml_config(DATA_DIR / "data_customs_rates.yaml"),
        'excise_rates': load_yaml_config(DATA_DIR / "data_excise_rates.yaml"),
        'delivery_costs': load_yaml_config(DATA_DIR / "data_delivery_costs.yaml"),
        'services': load_yaml_config(DATA_DIR / "data_services.yaml"),
        'coefficients': load_yaml_config(DATA_DIR / "data_coefficients.yaml"),
    }

# Загружаем конфигурации
if 'configs' not in st.session_state:
    st.session_state.configs = load_all_configs()

CONFIGS = st.session_state.configs

# ==================== ИМПОРТ КОНВЕРТЕРА ====================
from utils_currency_api import converter

# ==================== КУРСЫ ВАЛЮТ (обертка) ====================

def get_exchange_rates(force_refresh=False):
    if force_refresh:
        st.cache_data.clear()
        converter.refresh()
    
    if converter.is_available():
        rates = converter.get_all_rates()
        return {
            'success': True,
            'USD': rates.get('USD'),
            'EUR': rates.get('EUR'),
            'CNY': rates.get('CNY'),
            'KRW': rates.get('KRW'),
            'USDT': rates.get('USDT'),
            'KGS': rates.get('KGS'),
            'KZT': rates.get('KZT'),
            'USD_CBR': rates.get('USD_CBR'),
            'USD_KRW_INDIVIDUAL': rates.get('USD_KRW_INDIVIDUAL'),
            'USD_KRW_LEGAL': rates.get('USD_KRW_LEGAL'),
            'date': rates.get('date'),
            'time': rates.get('time')
        }
    else:
        return {
            'success': False,
            'error': converter.get_error() or 'Не удалось получить курсы валют'
        }

# ==================== ФУНКЦИИ РАСЧЕТА ====================

def calculate_customs_fee(customs_value_rub):
    if customs_value_rub <= 200000:
        return 1231
    elif customs_value_rub <= 450000:
        return 2462
    elif customs_value_rub <= 1200000:
        return 4924
    elif customs_value_rub <= 2700000:
        return 13541
    elif customs_value_rub <= 4200000:
        return 18465
    elif customs_value_rub <= 5500000:
        return 21344
    elif customs_value_rub <= 7000000:
        return 49240
    else:
        return 73860


def get_customs_rate_by_value(customs_value_eur, rates_config):
    brackets = rates_config.get('individuals', {}).get('by_value', {}).get('brackets', [])
    for bracket in brackets:
        max_euro = bracket.get('max_euro')
        if max_euro is None or customs_value_eur <= max_euro:
            return bracket
    return brackets[-1] if brackets else {'percent': 48, 'min_per_cm3': 20}


def get_customs_rate_by_volume(engine_cc, age_years, rates_config):
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


def calculate_utilization_fee(engine_cc, horsepower_hp, age_years, is_electric=False, vehicle_type="Легковой", client_type="Физическое лицо"):
    rates_config = CONFIGS.get('utilization_rates', {})
    is_old = age_years >= 3
    power_kw = horsepower_hp / 1.3596
    base_rate = rates_config.get('base_rate', 20000)

    if client_type == "Физическое лицо":
        if horsepower_hp <= 160 and engine_cc <= 3000:
            coeff = 0.17 if not is_old else 0.26
            return base_rate * coeff

        if is_electric:
            electric_rates = rates_config.get('individuals', {}).get('electric', [])
            for bracket in electric_rates:
                power_max_kw = bracket.get('power_max_kw')
                if power_max_kw is None:
                    continue
                if power_kw <= power_max_kw:
                    coeff = bracket.get('old' if is_old else 'new', 1.0)
                    return base_rate * coeff
            if electric_rates:
                last = electric_rates[-1]
                coeff = last.get('old' if is_old else 'new', 1.0)
                return base_rate * coeff
            return base_rate * 100.0

        if 1000 < engine_cc <= 2000:
            rates_list = rates_config.get('individuals', {}).get('engine_1000_2000', [])
            if not rates_list:
                if 160 < horsepower_hp <= 190:
                    coeff = 37.5 if not is_old else 74.64
                    return base_rate * coeff
                elif 190 < horsepower_hp <= 220:
                    coeff = 39.7 if not is_old else 79.20
                elif 220 < horsepower_hp <= 250:
                    coeff = 42.1 if not is_old else 83.88
                elif 250 < horsepower_hp <= 280:
                    coeff = 47.6 if not is_old else 91.92
                elif 280 < horsepower_hp <= 310:
                    coeff = 53.8 if not is_old else 100.56
                elif 310 < horsepower_hp <= 340:
                    coeff = 60.8 if not is_old else 110.16
                elif 340 < horsepower_hp <= 370:
                    coeff = 69.3 if not is_old else 120.60
                elif 370 < horsepower_hp <= 400:
                    coeff = 79.0 if not is_old else 132.00
                elif 400 < horsepower_hp <= 430:
                    coeff = 90.0 if not is_old else 144.60
                elif 430 < horsepower_hp <= 460:
                    coeff = 102.7 if not is_old else 158.40
                elif 460 < horsepower_hp <= 500:
                    coeff = 117.0 if not is_old else 173.40
                else:
                    coeff = 133.4 if not is_old else 189.84
                return base_rate * coeff
            
            for bracket in rates_list:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        elif 2000 < engine_cc <= 3000:
            rates_list = rates_config.get('individuals', {}).get('engine_2000_3000', [])
            if not rates_list:
                if 160 < horsepower_hp <= 190:
                    coeff = 96.11 if not is_old else 144.0
                elif 190 < horsepower_hp <= 220:
                    coeff = 98.5 if not is_old else 145.9
                elif 220 < horsepower_hp <= 250:
                    coeff = 100.1 if not is_old else 148.0
                elif 250 < horsepower_hp <= 280:
                    coeff = 105.0 if not is_old else 152.5
                elif 280 < horsepower_hp <= 310:
                    coeff = 109.2 if not is_old else 157.1
                elif 310 < horsepower_hp <= 340:
                    coeff = 113.6 if not is_old else 161.4
                elif 340 < horsepower_hp <= 370:
                    coeff = 118.1 if not is_old else 165.9
                elif 370 < horsepower_hp <= 400:
                    coeff = 122.9 if not is_old else 170.6
                elif 400 < horsepower_hp <= 430:
                    coeff = 127.8 if not is_old else 175.4
                elif 430 < horsepower_hp <= 460:
                    coeff = 132.9 if not is_old else 180.3
                elif 460 < horsepower_hp <= 500:
                    coeff = 138.2 if not is_old else 185.3
                else:
                    coeff = 143.7 if not is_old else 190.5
                return base_rate * coeff
            
            for bracket in rates_list:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        elif 3000 < engine_cc <= 3500:
            rates = rates_config.get('individuals', {}).get('engine_3000_3500', {})
            coeff = rates.get('old' if is_old else 'new', 100.0)
            return base_rate * coeff

        elif engine_cc > 3500:
            rates = rates_config.get('individuals', {}).get('engine_over_3500', {})
            coeff = rates.get('old' if is_old else 'new', 100.0)
            return base_rate * coeff

        return base_rate * 100.0

    else:
        if vehicle_type in ["Грузовой", "Пикап"]:
            return rates_config.get('truck_base_rate', 150000) * 1.0

        if is_electric:
            electric_rates = rates_config.get('legal', {}).get('electric', [])
            for bracket in electric_rates:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        if 1000 < engine_cc <= 2000:
            rates_list = rates_config.get('legal', {}).get('engine_1000_2000', [])
            for bracket in rates_list:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        elif 2000 < engine_cc <= 3000:
            rates_list = rates_config.get('legal', {}).get('engine_2000_3000', [])
            for bracket in rates_list:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        elif 3000 < engine_cc <= 3500:
            rates_list = rates_config.get('legal', {}).get('engine_3000_3500', [])
            for bracket in rates_list:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        elif engine_cc > 3500:
            rates_list = rates_config.get('legal', {}).get('engine_over_3500', [])
            for bracket in rates_list:
                p_min = bracket.get('power_min_kw', 0)
                p_max = bracket.get('power_max_kw')
                if p_max is None:
                    if power_kw >= p_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if p_min <= power_kw <= p_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            return base_rate * 100.0

        return base_rate * 100.0


def get_excise_rate(horsepower, rates_config):
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


def calculate_excise(horsepower_hp, fuel_type):
    if fuel_type == "Электричка":
        return 0
    rate = get_excise_rate(horsepower_hp, CONFIGS.get('excise_rates', {}))
    return horsepower_hp * rate


def calculate_vat(customs_value, customs_duty, excise, client_type, destination):
    if client_type == "Физическое лицо":
        return 0
    base = customs_value + customs_duty + excise
    vat_rates = CONFIGS.get('coefficients', {}).get('taxes', {}).get('vat_import', {})
    if destination == "Бишкек":
        rate = vat_rates.get('kyrgyzstan_legal', 0.12)
    else:
        rate = vat_rates.get('legal', 0.20)
    return base * rate


def get_delivery_cost(city, vehicle_type, delivery_config):
    costs = delivery_config.get('delivery_costs', {})
    oversize_coeff = delivery_config.get('oversize_coefficient', 1.2)
    cost = costs.get(city, 150000)
    if vehicle_type in ["Грузовой", "Пикап"]:
        cost = cost * oversize_coeff
    return cost


def get_service_cost(service_name, vehicle_type="Легковой", country_export="Корея"):
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


# ==================== КОЛБЭКИ ====================

def update_hp_from_kw():
    st.session_state.hp_hp = st.session_state.hp_kw * 1.3596

def update_kw_from_hp():
    st.session_state.hp_kw = st.session_state.hp_hp / 1.3596


# ==================== ФОРМАТИРОВАНИЕ ====================

def format_number(num):
    return f"{num:,.0f}".replace(',', ' ')

def format_money(num, currency="₽"):
    return f"{format_number(num)} {currency}"


# ==================== ГЛАВНАЯ ФУНКЦИЯ ====================

def main():
    st.title("🚗 Калькулятор растаможки автомобилей")
    st.markdown("---")

    rates = get_exchange_rates()

    if not rates.get('success'):
        st.error(f"❌ Ошибка получения курсов: {rates.get('error', 'Неизвестная ошибка')}")
        st.info("Проверьте интернет-соединение и обновите страницу.")
        return

    # Отображение даты курсов и кнопки обновления
    col_date, col_btn = st.columns([3, 1])
    with col_date:
        st.caption(f"💱 Курсы валют от {rates.get('date', '')} {rates.get('time', '')} (источник: ЦБ РФ + Binance)")
    with col_btn:
        if st.button("🔄 Обновить курсы", use_container_width=True):
            rates = get_exchange_rates(force_refresh=True)
            st.rerun()

    # ==================== БОКОВАЯ ПАНЕЛЬ ====================
    with st.sidebar:
        st.header("💱 Текущие курсы")
        
        st.metric("🇺🇸 USD (ЦБ +4%)", f"{rates.get('USD', 0):.2f} ₽")
        st.metric("💵 USDT (Binance)", f"{rates.get('USDT', 0):.2f} ₽")
        st.metric("🇪🇺 EUR", f"{rates.get('EUR', 0):.2f} ₽")
        st.metric("🇨🇳 CNY", f"{rates.get('CNY', 0):.4f} ₽")
        st.metric("🇰🇷 KRW (1000)", f"{rates.get('KRW', 0):.2f} ₽")
        st.divider()
        st.caption("**📌 USD/KRW:**")
        st.metric("Физ.лица", f"{rates.get('USD_KRW_INDIVIDUAL', 0):.2f} вон")
        st.metric("Юр.лица", f"{rates.get('USD_KRW_LEGAL', 0):.2f} вон")
        
        st.divider()
        st.markdown("**📌 Коэффициенты утильсбора:**")
        st.caption("• До 160 л.с. → 0.17 / 0.26")
        st.caption("• Свыше 160 л.с. → коммерческие")
        st.caption("• Основание: ПП РФ № 1713")

    # ==================== ОСНОВНАЯ ФОРМА ====================
    col1, col2 = st.columns(2)
    with col1:
        country_export = st.selectbox("🌏 Страна экспорта", ["Китай", "Корея"])
        city = st.selectbox("📍 Город доставки", [
            "Владивосток", "Уссурийск", "Москва", "Санкт-Петербург", "Новосибирск",
            "Екатеринбург", "Казань", "Краснодар", "Бишкек", "Алма-Аты"
        ])
        client_type = st.selectbox("👤 Тип клиента", ["Физическое лицо", "Юридическое лицо"])
        vehicle_type = st.selectbox("🚙 Тип транспорта", ["Легковой", "Грузовой", "Пикап", "Электричка"])
        fuel_type = st.selectbox("⛽ Тип топлива", ["Бензин", "Дизель", "Гибрид", "Электричка"])

    with col2:
        if country_export == "Китай":
            price_currency = "CNY (юань)"
            price_rate = rates.get('CNY', 0)
        else:
            price_currency = "KRW (вона)"
            price_rate = rates.get('KRW', 0)
        
        st.metric("💵 Актуальный курс", f"1 {price_currency.split()[0]} = {price_rate:.4f} ₽")
        
        price = st.number_input(
            f"💰 Стоимость авто ({price_currency})",
            min_value=0.0,
            value=138000000.0 if country_export == "Корея" else 50000.0,
            step=1000000.0 if country_export == "Корея" else 5000.0
        )
        
        price_rub_preview = price * price_rate
        st.caption(f"📌 Примерно: {format_number(price_rub_preview)} ₽ по текущему курсу")

        engine_cc = st.number_input("🔧 Объем двигателя", min_value=0, value=2999, step=100, help="куб.см")

        col_hp1, col_hp2 = st.columns(2)
        with col_hp1:
            st.number_input(
                "⚡ Мощность (кВт)",
                min_value=0.0,
                step=1.0,
                key='hp_kw',
                on_change=update_hp_from_kw,
                help="Мощность в киловаттах"
            )
        with col_hp2:
            st.number_input(
                "⚡ Мощность (л.с.)",
                min_value=0.0,
                step=1.0,
                key='hp_hp',
                on_change=update_kw_from_hp,
                help="Мощность в лошадиных силах"
            )

        horsepower_kw = st.session_state.hp_kw
        horsepower_hp = st.session_state.hp_hp

        weight = st.number_input("🏋️ Масса", min_value=0, value=1800, step=100, help="кг")
        manufacture_date = st.date_input("📅 Дата выпуска", value=datetime(2022, 1, 1))

    st.markdown("---")
    calculate = st.button("🧮 РАССЧИТАТЬ", type="primary", use_container_width=True)

    if calculate:
        age_years = (datetime.now() - datetime(manufacture_date.year, manufacture_date.month, manufacture_date.day)).days / 365.25
        age_years = round(age_years, 2)
        is_electric = fuel_type == "Электричка"

        # ============================================================
        # 1. КОНВЕРТАЦИЯ СТОИМОСТИ
        # ============================================================
        if country_export == "Китай":
            price_rub = price * rates.get('CNY', 0)
            price_currency_short = "CNY"
        else:
            price_rub = price * rates.get('KRW', 0)
            price_currency_short = "KRW"

        # ============================================================
        # 2. КОМИССИЯ ДИЛЕРА
        # ============================================================
        dealer_commission_coeff = CONFIGS.get('coefficients', {}).get('dealer_commission', {})
        if country_export == "Китай":
            dealer_commission_original = price * dealer_commission_coeff.get('Китай', {}).get('value', 0.15)
            dealer_commission_currency = "CNY"
            dealer_commission = dealer_commission_original * rates.get('CNY', 0)
        else:
            dealer_commission_original = dealer_commission_coeff.get('Корея', {}).get('value', 2500)
            dealer_commission_currency = "USD"
            dealer_commission = dealer_commission_original * rates.get('USD', 0)

        # ============================================================
        # 3. ФРАХТ
        # ============================================================
        delivery_to_border = 1500 * rates.get('USD', 0)

        # ============================================================
        # 4. ТАМОЖЕННАЯ СТОИМОСТЬ (без комиссии дилера)
        # ============================================================
        customs_value = price_rub + delivery_to_border

        # ============================================================
        # 5. ТАМОЖЕННЫЕ ПЛАТЕЖИ
        # ============================================================
        customs_fee = calculate_customs_fee(customs_value)
        customs_duty = calculate_customs_duty_individual(customs_value, engine_cc, age_years, rates.get('EUR', 0))
        utilization = calculate_utilization_fee(engine_cc, horsepower_hp, age_years, is_electric, vehicle_type, client_type)
        excise = calculate_excise(horsepower_hp, fuel_type)
        vat = calculate_vat(customs_value, customs_duty, excise, client_type, city)

        # ============================================================
        # 6. РАСХОДЫ В РФ
        # ============================================================
        delivery_cost = get_delivery_cost(city, vehicle_type, CONFIGS.get('delivery_costs', {}))
        broker_cost = get_service_cost('broker', vehicle_type, country_export)
        epts_cost = get_service_cost('epts', vehicle_type, country_export)

        # ============================================================
        # 7. ИТОГИ
        # ============================================================
        total_customs = customs_fee + customs_duty + utilization + excise + vat
        total_services = dealer_commission + broker_cost + epts_cost + delivery_cost
        total_cost = price_rub + total_customs + total_services

        # ==================== ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ ====================
        st.markdown("---")
        st.header("📊 РЕЗУЛЬТАТ РАСЧЕТА")

        # ----- БЛОК 1: ИТОГО ПОД КЛЮЧ (основной, не разворачивается) -----
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
                        padding: 1.5rem; border-radius: 1rem; text-align: center; margin: 1rem 0;">
                <h2 style="color: white; margin: 0;">🏁 ИТОГО ПОД КЛЮЧ</h2>
                <p style="color: #ffd700; font-size: 2.5rem; font-weight: bold; margin: 0.5rem 0;">
                    {format_money(total_cost)}
                </p>
                <p style="color: #ccc; margin: 0;">
                    {format_number(price)} {price_currency_short} × {price_rate:.4f} ₽ = {format_number(price_rub)} ₽
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # ----- БЛОК 2: ИТОГО ЗА ГРАНИЦЕЙ (разворачивается) -----
        with st.expander(f"💰 ИТОГО ЗА ГРАНИЦЕЙ: {format_money(price_rub + delivery_to_border)}", expanded=True):
            st.write("**Расходы за границей до границы РФ:**")
            st.write(f"• Стоимость авто: {format_number(price)} {price_currency_short} → {format_number(price_rub)} ₽")
            st.write(f"• Фрахт (доставка до границы): 1 500 USD × {rates.get('USD', 0):.2f} ₽ = {format_number(delivery_to_border)} ₽")
            st.write(f"**• Итого: {format_number(price_rub + delivery_to_border)} ₽**")

        # ----- БЛОК 3: ИТОГО НА ТАМОЖНЕ (разворачивается) -----
        with st.expander(f"🛃 ИТОГО НА ТАМОЖНЕ: {format_money(total_customs)}", expanded=True):
            st.write("**Таможенные платежи:**")
            st.write(f"• Таможенный сбор (оформление): {format_number(customs_fee)} ₽")
            st.write(f"• Таможенная пошлина: {format_number(customs_duty)} ₽")
            st.write(f"• Утилизационный сбор: {format_number(utilization)} ₽")
            st.write(f"• Акциз: {format_number(excise)} ₽")
            st.write(f"• НДС: {format_number(vat)} ₽")
            st.write("")
            st.write("**📌 Детали расчета утильсбора:**")
            st.write(f"• Базовая ставка: 20 000 ₽")
            coeff_display = utilization / 20000
            st.write(f"• Коэффициент: {coeff_display:.2f}")
            st.write(f"• Итого: 20 000 × {coeff_display:.2f} = {format_number(utilization)} ₽")

        # ----- БЛОК 4: ДОСТАВКА + КОМИССИИ + БРОКЕР (разворачивается) -----
        with st.expander(f"🚛 ДОСТАВКА + КОМИССИИ + БРОКЕР: {format_money(total_services)}", expanded=True):
            st.write("**🔧 Комиссии и услуги:**")
            st.write(f"• Комиссия дилера: {format_number(dealer_commission_original)} {dealer_commission_currency} → {format_number(dealer_commission)} ₽")
            st.write(f"• Услуги брокера: {format_number(broker_cost)} ₽")
            st.write(f"• ЭПТС/СБКТС: {format_number(epts_cost)} ₽")
            st.write("")
            st.write("**🚛 Доставка:**")
            st.write(f"• Доставка по РФ: {format_number(delivery_cost)} ₽")

        # ----- БЛОК 5: ИТОГО ПОД КЛЮЧ (структура, разворачивается) -----
        with st.expander(f"🏁 ИТОГО ПОД КЛЮЧ (структура): {format_money(total_cost)}", expanded=False):
            st.write("**Структура итоговой стоимости:**")
            st.write(f"• Стоимость авто за границей: {format_number(price_rub)} ₽")
            st.write(f"• Таможенные платежи: {format_number(total_customs)} ₽")
            st.write(f"• Услуги и доставка: {format_number(total_services)} ₽")
            st.write("")
            st.write(f"**• ИТОГО: {format_number(total_cost)} ₽**")
            st.write("")
            st.write("**💱 Курсы, использованные в расчете:**")
            st.write(f"• USD/RUB: {rates.get('USD', 0):.4f} ₽ (ЦБ +4%)")
            st.write(f"• EUR/RUB: {rates.get('EUR', 0):.4f} ₽")
            st.write(f"• {price_currency_short}/RUB: {price_rate:.4f} ₽")
            st.write(f"• USDT/RUB: {rates.get('USDT', 0):.4f} ₽")

        # Информация о ставке утильсбора
        if client_type == "Физическое лицо":
            if horsepower_hp <= 160 and engine_cc <= 3000 and not is_electric:
                st.success(f"✅ Применена **льготная ставка** утильсбора (до 160 л.с., {horsepower_hp:.1f} л.с.)")
            elif is_electric and horsepower_hp <= 80:
                st.success(f"✅ Применена **льготная ставка** утильсбора (электро до 80 л.с., {horsepower_hp:.1f} л.с.)")
            else:
                st.warning(f"⚠️ Применена **коммерческая ставка** утильсбора (свыше 160 л.с., {horsepower_hp:.1f} л.с.)")

        st.info(
            f"📅 Возраст: **{age_years} лет** | "
            f"💪 Мощность: **{horsepower_hp:.1f} л.с.** ({horsepower_kw:.1f} кВт) | "
            f"⚙️ Объем: **{engine_cc} см³**"
        )

        st.caption("⚠️ **Важно:** Данный расчет является ознакомительным. Для проверки используйте калькулятор на tks.ru")

if __name__ == "__main__":
    main()
