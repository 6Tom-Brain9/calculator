"""
Компоненты пользовательского ввода
"""

import streamlit as st
from datetime import datetime
from config import (
    COUNTRIES, ALL_CITIES, VEHICLE_TYPES, FUEL_TYPES, 
    CLIENT_TYPES, CONDITIONS
)


def render_main_inputs() -> dict:
    """
    Отрисовывает основные поля ввода
    
    Returns:
        dict с введенными значениями
    """
    st.header("🚗 Основные параметры")
    
    col1, col2 = st.columns(2)
    
    with col1:
        country_export = st.selectbox(
            "Страна экспорта",
            options=COUNTRIES,
            help="Откуда ввозится автомобиль"
        )
        
        city = st.selectbox(
            "Город доставки",
            options=ALL_CITIES,
            help="Куда доставить автомобиль"
        )
        
        client_type = st.selectbox(
            "Тип клиента",
            options=CLIENT_TYPES,
            help="Физическое или юридическое лицо"
        )
    
    with col2:
        vehicle_type = st.selectbox(
            "Тип транспорта",
            options=VEHICLE_TYPES,
            help="Легковой, грузовой, пикап, мотоцикл или электромобиль"
        )
        
        fuel_type = st.selectbox(
            "Тип топлива",
            options=FUEL_TYPES,
            help="Бензин, дизель, гибрид, электричка"
        )
        
        condition = st.selectbox(
            "Состояние",
            options=CONDITIONS,
            help="Новый или с пробегом"
        )
    
    return {
        'country_export': country_export,
        'city': city,
        'client_type': client_type,
        'vehicle_type': vehicle_type,
        'fuel_type': fuel_type,
        'condition': condition
    }


def render_vehicle_specs(country_export: str) -> dict:
    """
    Отрисовывает характеристики автомобиля
    
    Args:
        country_export: страна экспорта (для определения валюты)
    
    Returns:
        dict с характеристиками
    """
    st.header("📊 Характеристики автомобиля")
    
    # Валюта в зависимости от страны
    if country_export == "Китай":
        currency = "CNY (юань)"
        currency_code = "CNY"
    else:  # Корея
        currency = "KRW (вон, тыс.)"
        currency_code = "KRW"
    
    col1, col2 = st.columns(2)
    
    with col1:
        price = st.number_input(
            f"Стоимость авто ({currency})",
            min_value=0.0,
            max_value=10000000.0,
            value=50000.0 if country_export == "Китай" else 25000.0,
            step=1000.0,
            help="Цена автомобиля в валюте страны экспорта"
        )
        
        engine_cc = st.number_input(
            "Объем двигателя (куб.см)",
            min_value=0,
            max_value=20000,
            value=1997,
            step=100,
            help="Рабочий объем двигателя в кубических сантиметрах"
        )
        
        horsepower = st.number_input(
            "Мощность (л.с.)",
            min_value=0.0,
            max_value=2000.0,
            value=150.0,
            step=10.0,
            help="Мощность двигателя в лошадиных силах"
        )
    
    with col2:
        weight = st.number_input(
            "Масса (кг)",
            min_value=0,
            max_value=50000,
            value=1800,
            step=100,
            help="Снаряженная масса автомобиля"
        )
        
        manufacture_date = st.date_input(
            "Дата выпуска",
            value=datetime(2023, 1, 1),
            min_value=datetime(2000, 1, 1),
            max_value=datetime.today(),
            help="Дата первого выпуска автомобиля"
        )
        
        st.info(f"📅 Возраст авто: {(datetime.today() - manufacture_date).days / 365.25:.1f} лет")
    
    return {
        'price': price,
        'price_currency': currency_code,
        'engine_cc': engine_cc,
        'horsepower': horsepower,
        'weight': weight,
        'manufacture_date': manufacture_date.strftime('%Y-%m-%d')
    }


def render_calculator_form() -> dict:
    """
    Полная форма калькулятора
    
    Returns:
        dict со всеми введенными данными
    """
    st.title("🚗 Калькулятор растаможки автомобилей")
    st.markdown("---")
    
    # Основные параметры
    main_params = render_main_inputs()
    
    st.markdown("---")
    
    # Характеристики авто
    vehicle_specs = render_vehicle_specs(main_params['country_export'])
    
    st.markdown("---")
    
    # Кнопка расчета
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        calculate = st.button(
            "🧮 РАССЧИТАТЬ СТОИМОСТЬ",
            type="primary",
            use_container_width=True
        )
    
    # Объединяем все данные
    input_data = {**main_params, **vehicle_specs}
    
    return {
        'input_data': input_data,
        'calculate': calculate
    }