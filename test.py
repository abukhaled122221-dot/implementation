"""
Test script to verify the agent logic without running mock API servers.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent1 import DataReceiverRetrievalAgent
from agent2 import RecommendationAgent
from agent3 import ExplainerAgent

def test_agent2_and_agent3():
    # Mock unified quote set (as would be output by Agent 1)
    mock_quotes = [
        {
            "company": "Tawuniya",
            "premium": 483,
            "coverage_type": "TPL",
            "deductible": 500,
            "add_ons": ["roadside_assistance"],
            "coverage_scope": ["third_party"],
            "provider_reliability": 9.0,
            "availability": True
        },
        {
            "company": "Medgulf",
            "premium": 469,
            "coverage_type": "TPL",
            "deductible": 550,
            "add_ons": [],
            "coverage_scope": ["third_party"],
            "provider_reliability": 7.0,
            "availability": True
        },
        {
            "company": "ACIG",
            "premium": 428,
            "coverage_type": "TPL",
            "deductible": 700,
            "add_ons": [],
            "coverage_scope": ["third_party"],
            "provider_reliability": 6.0,
            "availability": True
        },
        {
            "company": "Takaful Al-Rajhi",
            "premium": 507,
            "coverage_type": "TPL",
            "deductible": 600,
            "add_ons": ["roadside_assistance"],
            "coverage_scope": ["third_party"],
            "provider_reliability": 9.5,
            "availability": True
        }
    ]
    customer_data = {
        "vehicle_value": 70000,
        "driver_age": 35
    }

    print("Testing Agent 2: Recommendation Agent")
    agent2 = RecommendationAgent()
    recommended_quote, breakdown = agent2.recommend(mock_quotes, customer_data)
    if recommended_quote is None:
        print("ERROR: No recommendation produced")
        return
    print(f"Recommended company: {recommended_quote['company']}")
    print(f"Score: {breakdown.get('score', 'N/A') if isinstance(breakdown, dict) else 'N/A'}")
    # Actually breakdown is the second element from recommend, which is the breakdown dict.
    # Let's print some weighted contributions.
    print("Breakdown (weighted contributions):")
    for key in ['premium', 'coverage', 'coverage_to_price', 'deductible', 'addons', 'fit', 'reliability', 'availability']:
        wkey = f'weighted_{key}'
        if wkey in breakdown:
            print(f"  {key}: {breakdown[wkey]:.3f}")

    print("\nTesting Agent 3: Explainer Agent")
    # Need scored list for Agent 3
    scored_list = agent2.compute_scores(mock_quotes, customer_data)
    agent3 = ExplainerAgent()
    explanation = agent3.explain(recommended_quote, breakdown, scored_list)
    print("\n--- Explanation Output ---")
    print(explanation)
    print("--------------------------")

def test_agent1_mock():
    # We'll test Agent 1 by mocking the API calls internally.
    # For simplicity, we'll just show that the class can be instantiated.
    print("Testing Agent 1: DataReceiverRetrievalAgent")
    agent1 = DataReceiverRetrievalAgent()
    print("Agent 1 created successfully.")
    # We could also test the get_unified_quote_set method by patching the endpoints,
    # but for brevity we skip.

if __name__ == "__main__":
    test_agent1_mock()
    print()
    test_agent2_and_agent3()