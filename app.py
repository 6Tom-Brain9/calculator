def calculate_utilization_fee(engine_cc, horsepower, age_years, is_electric=False, vehicle_type="Легковой", client_type="Физическое лицо"):
    """
    Расчет утилизационного сбора по Постановлению Правительства РФ № 1713 от 01.11.2025
    Действует с 1 декабря 2025 года
    
    Аргументы:
        engine_cc: объем двигателя в куб.см
        horsepower: мощность в л.с.
        age_years: возраст в годах
        is_electric: True для электромобилей и последовательных гибридов
        vehicle_type: тип авто (Легковой, Грузовой, Пикап)
        client_type: тип клиента (Физическое лицо, Юридическое лицо)
    
    Возвращает:
        сумма утильсбора в рублях
    """
    rates_config = CONFIGS.get('utilization_rates', {})
    is_old = age_years >= 3
    
    # Преобразуем л.с. в кВт (1 кВт = 1.3596 л.с.)
    power_kw = horsepower / 1.3596
    
    # Для грузовых и пикапов
    if vehicle_type in ["Грузовой", "Пикап"]:
        base_rate = rates_config.get('truck_base_rate', 150000)
        return base_rate * 1.0  # временно, потом добавим грузовые коэффициенты
    
    # Базовая ставка для легковых
    base_rate = rates_config.get('base_rate', 20000)
    
    # ---------------------------
    # ФИЗИЧЕСКИЕ ЛИЦА
    # ---------------------------
    if client_type == "Физическое лицо":
        # --- ЛЬГОТНЫЕ УСЛОВИЯ ---
        # Условие 1: мощность <= 160 л.с. (117.68 кВт)
        # Условие 2: объем <= 3000 куб.см
        # Условие 3: не электромобиль (у электро свои льготы)
        is_low_power = horsepower <= 160
        is_small_engine = engine_cc <= 3000
        
        # Для электромобилей: льгота до 80 л.с. (58.84 кВт)
        if is_electric:
            electric_rates = rates_config.get('individuals', {}).get('electric', [])
            for bracket in electric_rates:
                power_max_kw = bracket.get('power_max_kw')
                if power_max_kw is None:
                    continue
                if power_kw <= power_max_kw:
                    coeff = bracket.get('old' if is_old else 'new', 1.0)
                    return base_rate * coeff
            # Если не попали в льготный диапазон - коммерческие ставки для электро
            # Используем последний диапазон
            if electric_rates:
                last = electric_rates[-1]
                coeff = last.get('old' if is_old else 'new', 1.0)
                return base_rate * coeff
        
        # Для ДВС
        if is_low_power and is_small_engine:
            # Льготный коэффициент
            coeff = 0.17 if not is_old else 0.26
            return base_rate * coeff
        
        # --- КОММЕРЧЕСКИЕ СТАВКИ ДЛЯ ФИЗЛИЦ ---
        # Определяем группу по объему
        if engine_cc <= 1000:
            # Для объема до 1000 - всегда льгота (по постановлению)
            coeff = 0.17 if not is_old else 0.26
            return base_rate * coeff
        
        elif engine_cc <= 2000:
            rates_list = rates_config.get('individuals', {}).get('объем_1000_2000', [])
            for bracket in rates_list:
                power_min = bracket.get('power_min_kw', 0)
                power_max = bracket.get('power_max_kw')
                
                if power_max is None:
                    if power_kw >= power_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if power_min <= power_kw <= power_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            # fallback
            return base_rate * 100.0
        
        elif engine_cc <= 3000:
            rates_list = rates_config.get('individuals', {}).get('объем_2000_3000', [])
            for bracket in rates_list:
                power_min = bracket.get('power_min_kw', 0)
                power_max = bracket.get('power_max_kw')
                
                if power_max is None:
                    if power_kw >= power_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if power_min <= power_kw <= power_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            # fallback
            return base_rate * 100.0
        
        elif engine_cc <= 3500:
            rates = rates_config.get('individuals', {}).get('объем_3000_3500', {})
            coeff = rates.get('old' if is_old else 'new', 100.0)
            return base_rate * coeff
        
        else:  # свыше 3500
            rates = rates_config.get('individuals', {}).get('объем_свыше_3500', {})
            coeff = rates.get('old' if is_old else 'new', 100.0)
            return base_rate * coeff
    
    # ---------------------------
    # ЮРИДИЧЕСКИЕ ЛИЦА
    # ---------------------------
    else:
        # Электромобили для юрлиц
        if is_electric:
            electric_rates = rates_config.get('legal', {}).get('electric', [])
            for bracket in electric_rates:
                power_min = bracket.get('power_min_kw', 0)
                power_max = bracket.get('power_max_kw')
                
                if power_max is None:
                    if power_kw >= power_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if power_min <= power_kw <= power_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            # fallback
            return base_rate * 100.0
        
        # ДВС для юрлиц
        if engine_cc <= 2000:
            rates_list = rates_config.get('legal', {}).get('объем_1000_2000', [])
            for bracket in rates_list:
                power_min = bracket.get('power_min_kw', 0)
                power_max = bracket.get('power_max_kw')
                
                if power_max is None:
                    if power_kw >= power_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if power_min <= power_kw <= power_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            # fallback
            return base_rate * 100.0
        
        elif engine_cc <= 3000:
            rates_list = rates_config.get('legal', {}).get('объем_2000_3000', [])
            for bracket in rates_list:
                power_min = bracket.get('power_min_kw', 0)
                power_max = bracket.get('power_max_kw')
                
                if power_max is None:
                    if power_kw >= power_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if power_min <= power_kw <= power_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            # fallback
            return base_rate * 100.0
        
        elif engine_cc <= 3500:
            rates_list = rates_config.get('legal', {}).get('объем_3000_3500', [])
            for bracket in rates_list:
                power_min = bracket.get('power_min_kw', 0)
                power_max = bracket.get('power_max_kw')
                
                if power_max is None:
                    if power_kw >= power_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if power_min <= power_kw <= power_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            # fallback
            return base_rate * 100.0
        
        else:  # свыше 3500
            rates_list = rates_config.get('legal', {}).get('объем_свыше_3500', [])
            for bracket in rates_list:
                power_min = bracket.get('power_min_kw', 0)
                power_max = bracket.get('power_max_kw')
                
                if power_max is None:
                    if power_kw >= power_min:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
                else:
                    if power_min <= power_kw <= power_max:
                        coeff = bracket.get('old' if is_old else 'new', 1.0)
                        return base_rate * coeff
            # fallback
            return base_rate * 100.0
