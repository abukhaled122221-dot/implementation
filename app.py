from flask import Flask, render_template, request, redirect, url_for, jsonify
import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our agent classes
from agent1 import DataReceiverRetrievalAgent
from agent2 import RecommendationAgent
from agent3 import ExplainerAgent

# Import mock insurance functions (we'll use them to create API endpoints)
from mock_insurance import (
    get_taawuniya_offers,
    get_takaful_alrajhi_offers,
    get_medgulf_offers,
    get_acig_offers
)

app = Flask(__name__)

# ========== Mock Insurance API Endpoints ==========
# These simulate the external insurance company APIs that Agent 1 will call.

@app.route('/api/taawuniya/get_offers', methods=['POST'])
def taawuniya_api():
    data = request.get_json()
    offers = get_taawuniya_offers(data)
    return jsonify(offers)

@app.route('/api/takaful_alrajhi/get_offers', methods=['POST'])
def takaful_alrajhi_api():
    data = request.get_json()
    offers = get_takaful_alrajhi_offers(data)
    return jsonify(offers)

@app.route('/api/medgulf/get_offers', methods=['POST'])
def medgulf_api():
    data = request.get_json()
    offers = get_medgulf_offers(data)
    return jsonify(offers)

@app.route('/api/acig/get_offers', methods=['POST'])
def acig_api():
    data = request.get_json()
    offers = get_acig_offers(data)
    return jsonify(offers)

# ========== Web Page Routes ==========

@app.route('/')
def landing():
    return render_template('landing.html', year=datetime.now().year)

@app.route('/entry')
def entry():
    error = request.args.get('error')
    return render_template('entry.html', year=datetime.now().year, error=error)

@app.route('/recommend', methods=['POST'])
def recommend():
    # Get form data
    form_data = request.form.to_dict()
    # Convert numeric fields
    try:
        vehicle_value = float(form_data.get('vehicle_value', 0))
        driver_age = int(form_data.get('driver_age', 0))
        purpose = form_data.get('purpose')
        vehicle_age = int(form_data.get('vehicle_age', 0))
    except ValueError:
        # If conversion fails, redirect back with error
        return redirect(url_for('entry', error='invalid_input'))

    # Validate minimum values
    if vehicle_value < 1000:
        return redirect(url_for('entry', error='vehicle_value_too_low'))
    if driver_age < 17:
        return redirect(url_for('entry', error='driver_age_too_low'))

    # Prepare customer data for agents (we'll pass the dict as is)
    customer_data = {
        'vehicle_value': vehicle_value,
        'driver_age': driver_age,
        'purpose_of_use': purpose,
        'vehicle_age': vehicle_age
    }

    # Agent 1: Data Receiver and Retrieval Agent
    # Note: The agent's endpoints are set to localhost:5000 (this same app) but different paths.
    agent1 = DataReceiverRetrievalAgent()
    unified_quotes = agent1.get_unified_quote_set(customer_data)

    if not unified_quotes:
        # If no quotes, show error page (we'll redirect back to entry with error)
        return redirect(url_for('entry', error='no_quotes'))

    # Agent 2: Recommendation Agent
    agent2 = RecommendationAgent()
    recommended_quote, breakdown = agent2.recommend(unified_quotes, customer_data)

    if not recommended_quote:
        return redirect(url_for('entry', error='no_recommendation'))

    # Prepare scored quotes for Agent 3
    scored_list = agent2.compute_scores(unified_quotes, customer_data)

    # Agent 3: Explainer Agent
    agent3 = ExplainerAgent()
    explanation = agent3.explain(recommended_quote, breakdown, scored_list)

    # Render result page
    return render_template(
        'result.html',
        recommendation=recommended_quote,
        explanation=explanation,
        year=datetime.now().year
    )

# ========== Error Handling ==========
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# ========== Run the App ==========
if __name__ == '__main__':
    # Run on port 5000, debug=False for production-like behavior
    app.run(host='0.0.0.0', port=5000, debug=False)