from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/get_offers', methods=['POST'])
def get_offers():
    data = request.get_json()
    vehicle_value = data.get('vehicle_value', 50000) if data else 50000
    driver_age = data.get('driver_age', 30) if data else 30

    # Takaful Al-Rajhi tends to be more expensive but reliable
    if vehicle_value > 150000:
        coverage_type = "Comprehensive"
        premium = 900
        deductible = 750
        add_ons = ["agency_repair", "roadside_assistance", "windshield_cover", "geographic_extension"]
    else:
        coverage_type = "TPL"
        premium = 507  # from example
        deductible = 600
        add_ons = ["roadside_assistance"]

    if driver_age < 25:
        premium += 250
    elif driver_age > 65:
        premium += 150

    offer = {
        "company": "Takaful Al-Rajhi",
        "premium": premium,
        "coverage_type": coverage_type,
        "deductible": deductible,
        "add_ons": add_ons,
        "coverage_scope": ["collision", "theft", "fire", "natural_events"] if coverage_type == "Comprehensive" else ["third_party"],
        "provider_reliability": 9.5,  # highest reliability
        "availability": True
    }
    return jsonify([offer])

if __name__ == '__main__':
    app.run(port=5002, debug=True)