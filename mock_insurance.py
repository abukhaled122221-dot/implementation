"""
Mock insurance offer generation functions.
Each function takes a dict of car and driver data and returns a list of 10 offer dicts.
Enforces minimum vehicle price 1000 and minimum driver age 17 (handled upstream, but we can clamp).
"""

import random

def _clamp_value(value, min_val, max_val=None):
    if value < min_val:
        return min_val
    if max_val is not None and value > max_val:
        return max_val
    return value

def _base_premium(vehicle_value, driver_age, company_factor):
    """
    Base premium calculation:
    - Base rate: 2% of vehicle value per year (typical rough estimate)
    - Adjust for driver age: younger drivers pay more, older drivers pay slightly more
    - Company factor: multiplier specific to company (reliability, brand)
    """
    base_rate = 0.02  # 2% of vehicle value
    age_factor = 1.0
    if driver_age < 25:
        age_factor = 1.5  # 50% extra for young drivers
    elif driver_age > 65:
        age_factor = 1.2  # 20% extra for senior drivers
    premium = vehicle_value * base_rate * age_factor * company_factor
    return max(premium, 100)  # ensure at least 100 SAR

def _random_variation(base, percent=0.2):
    """Return a random value within ±percent of base."""
    variation = random.uniform(-percent, percent)
    return base * (1 + variation)

def get_taawuniya_offers(data):
    """Tawuniya: reliable, moderate prices."""
    vehicle_value = _clamp_value(data.get('vehicle_value', 50000), 1000)
    driver_age = _clamp_value(data.get('driver_age', 30), 17)
    company_factor = 1.0  # baseline
    base = _base_premium(vehicle_value, driver_age, company_factor)
    offers = []
    for i in range(10):
        # Vary coverage type: 60% TPL, 40% Comprehensive
        if random.random() < 0.6:
            coverage_type = "TPL"
            # TPL tends to be cheaper
            prem = _random_variation(base * 0.8, 0.15)
            deductible = random.choice([300, 500, 700, 1000])
            add_ons = random.choice([
                [], ["roadside_assistance"], ["roadside_assistance", "windshield_cover"],
                ["agency_repair", "roadside_assistance"]
            ])
        else:
            coverage_type = "Comprehensive"
            prem = _random_variation(base * 1.2, 0.15)
            deductible = random.choice([500, 750, 1000, 1500])
            add_ons = random.choice([
                ["roadside_assistance"],
                ["agency_repair", "roadside_assistance"],
                ["agency_repair", "roadside_assistance", "windshield_cover"],
                ["agency_repair", "roadside_assistance", "windshield_cover", "geographic_extension"]
            ])
        # Ensure premium not too low
        prem = max(prem, 150)
        offers.append({
            "company": "Tawuniya",
            "premium": round(prem, 1),
            "coverage_type": coverage_type,
            "deductible": deductible,
            "add_ons": add_ons,
            "coverage_scope": ["third_party"] if coverage_type == "TPL" else ["collision", "theft", "fire"],
            "provider_reliability": 9.0,
            "availability": True
        })
    return offers

def get_takaful_alrajhi_offers(data):
    """Takaful Al-Rajhi: high reliability, higher prices."""
    vehicle_value = _clamp_value(data.get('vehicle_value', 50000), 1000)
    driver_age = _clamp_value(data.get('driver_age', 30), 17)
    company_factor = 1.2  # slightly higher base
    base = _base_premium(vehicle_value, driver_age, company_factor)
    offers = []
    for i in range(10):
        if random.random() < 0.5:
            coverage_type = "TPL"
            prem = _random_variation(base * 0.9, 0.15)
            deductible = random.choice([400, 600, 800, 1200])
            add_ons = random.choice([
                [], ["roadside_assistance"], ["agency_repair", "roadside_assistance"]
            ])
        else:
            coverage_type = "Comprehensive"
            prem = _random_variation(base * 1.3, 0.15)
            deductible = random.choice([700, 1000, 1500, 2000])
            add_ons = random.choice([
                ["roadside_assistance"],
                ["agency_repair", "roadside_assistance"],
                ["agency_repair", "roadside_assistance", "windshield_cover"],
                ["agency_repair", "roadside_assistance", "windshield_cover", "geographic_extension"]
            ])
        prem = max(prem, 200)
        offers.append({
            "company": "Takaful Al-Rajhi",
            "premium": round(prem, 1),
            "coverage_type": coverage_type,
            "deductible": deductible,
            "add_ons": add_ons,
            "coverage_scope": ["third_party"] if coverage_type == "TPL" else ["collision", "theft", "fire", "natural_events"],
            "provider_reliability": 9.5,
            "availability": True
        })
    return offers

def get_medgulf_offers(data):
    """Medgulf: lower prices, lower reliability."""
    vehicle_value = _clamp_value(data.get('vehicle_value', 50000), 1000)
    driver_age = _clamp_value(data.get('driver_age', 30), 17)
    company_factor = 0.8  # lower base
    base = _base_premium(vehicle_value, driver_age, company_factor)
    offers = []
    for i in range(10):
        if random.random() < 0.7:
            coverage_type = "TPL"
            prem = _random_variation(base * 0.85, 0.15)
            deductible = random.choice([300, 500, 700, 1000])
            add_ons = random.choice([
                [], ["roadside_assistance"], ["windshield_cover"]
            ])
        else:
            coverage_type = "Comprehensive"
            prem = _random_variation(base * 1.1, 0.15)
            deductible = random.choice([500, 750, 1000, 1500])
            add_ons = random.choice([
                ["roadside_assistance"],
                ["agency_repair", "roadside_assistance"],
                ["agency_repair", "roadside_assistance", "windshield_cover"]
            ])
        prem = max(prem, 120)
        offers.append({
            "company": "Medgulf",
            "premium": round(prem, 1),
            "coverage_type": coverage_type,
            "deductible": deductible,
            "add_ons": add_ons,
            "coverage_scope": ["third_party"] if coverage_type == "TPL" else ["collision", "theft", "fire"],
            "provider_reliability": 7.0,
            "availability": True
        })
    return offers

def get_acig_offers(data):
    """ACIG: cheapest, lowest reliability."""
    vehicle_value = _clamp_value(data.get('vehicle_value', 50000), 1000)
    driver_age = _clamp_value(data.get('driver_age', 30), 17)
    company_factor = 0.6  # lowest base
    base = _base_premium(vehicle_value, driver_age, company_factor)
    offers = []
    for i in range(10):
        if random.random() < 0.8:
            coverage_type = "TPL"
            prem = _random_variation(base * 0.8, 0.15)
            deductible = random.choice([400, 600, 800, 1200])
            add_ons = random.choice([
                [], ["roadside_assistance"]
            ])
        else:
            coverage_type = "Comprehensive"
            prem = _random_variation(base * 1.0, 0.15)
            deductible = random.choice([600, 900, 1200, 1500])
            add_ons = random.choice([
                ["roadside_assistance"],
                ["agency_repair", "roadside_assistance"]
            ])
        prem = max(prem, 100)
        offers.append({
            "company": "ACIG",
            "premium": round(prem, 1),
            "coverage_type": coverage_type,
            "deductible": deductible,
            "add_ons": add_ons,
            "coverage_scope": ["third_party"] if coverage_type == "TPL" else ["collision"],
            "provider_reliability": 6.0,
            "availability": True
        })
    return offers