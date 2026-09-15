from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/get_offers', methods=['POST'])
def get_offers():
    data = request.get_json()
    vehicle_value = data.get('vehicle_value', 50000) if data else 50000
    driver_age = data.get('driver_age', 30) if data else 30

    # ACIG: cheapest but lowest reliability and limited add-ons
    if vehicle_value > 100000:
        coverage_type = "Comprehensive"
        premium = 600
        deductible = 900
        add_ons = []
    else:
        coverage_type = "TPL"
        premium = 428  # from example
        deductible = 700
        add_ons = []

    if driver_age < 25:
        premium += 100
    elif driver_age > 65:
        premium += 50

    offer = {
        "company": "ACIG",
        "premium": premium,
        "coverage_type": coverage_type,
        "deductible": deductible,
        "add_ons": add_ons,
        "coverage_scope": ["collision"] if coverage_type == "Comprehensive" else ["third_party"],
        "provider_reliability": 6.0,  # lowest reliability
        "availability": True
    }
    return jsonify([offer])

if __name__ == '__main__':
    app.run(port=5004, debug=True)