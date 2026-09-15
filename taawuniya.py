from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/get_offers', methods=['POST'])
def get_offers():
    # Get car and driver data from request (optional, for mocking we can use it to vary response)
    data = request.get_json()
    # For simplicity, we return a fixed offer, but we can vary based on data
    # Example: if vehicle value > 100000, offer comprehensive, else TPL
    vehicle_value = data.get('vehicle_value', 50000) if data else 50000
    driver_age = data.get('driver_age', 30) if data else 30

    # Determine offer based on simple logic
    if vehicle_value > 100000:
        coverage_type = "Comprehensive"
        premium = 800
        deductible = 1000
        add_ons = ["agency_repair", "roadside_assistance", "windshield_cover"]
    else:
        coverage_type = "TPL"
        premium = 483  # base premium
        deductible = 500
        add_ons = ["roadside_assistance"]

    # Adjust premium based on driver age (younger drivers pay more)
    if driver_age < 25:
        premium += 200
    elif driver_age > 65:
        premium += 100

    offer = {
        "company": "Tawuniya",
        "premium": premium,
        "coverage_type": coverage_type,
        "deductible": deductible,
        "add_ons": add_ons,
        # Additional fields for scoring criteria
        "coverage_scope": ["collision", "theft", "fire"] if coverage_type == "Comprehensive" else ["third_party"],
        "provider_reliability": 9.0,  # out of 10
        "availability": True
    }
    return jsonify([offer])

if __name__ == '__main__':
    app.run(port=5001, debug=True)