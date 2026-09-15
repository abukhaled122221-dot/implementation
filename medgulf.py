from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/get_offers', methods=['POST'])
def get_offers():
    data = request.get_json()
    vehicle_value = data.get('vehicle_value', 50000) if data else 50000
    driver_age = data.get('driver_age', 30) if data else 30

    # Medgulf: cheaper but lower reliability
    if vehicle_value > 120000:
        coverage_type = "Comprehensive"
        premium = 700
        deductible = 800
        add_ons = ["roadside_assistance"]
    else:
        coverage_type = "TPL"
        premium = 469  # from example
        deductible = 550
        add_ons = []

    if driver_age < 25:
        premium += 150
    elif driver_age > 65:
        premium += 80

    offer = {
        "company": "Medgulf",
        "premium": premium,
        "coverage_type": coverage_type,
        "deductible": deductible,
        "add_ons": add_ons,
        "coverage_scope": ["collision", "theft"] if coverage_type == "Comprehensive" else ["third_party"],
        "provider_reliability": 7.0,  # lower reliability
        "availability": True
    }
    return jsonify([offer])

if __name__ == '__main__':
    app.run(port=5003, debug=True)