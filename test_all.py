import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("Testing imports...")
try:
    from agent1 import DataReceiverRetrievalAgent
    print("✓ agent1 imported")
except Exception as e:
    print(f"✗ agent1 import failed: {e}")

try:
    from agent2 import RecommendationAgent
    print("✓ agent2 imported")
except Exception as e:
    print(f"✗ agent2 import failed: {e}")

try:
    from agent3 import ExplainerAgent
    print("✓ agent3 imported")
except Exception as e:
    print(f"✗ agent3 import failed: {e}")

try:
    from mock_insurance import (
        get_taawuniya_offers,
        get_takaful_alrajhi_offers,
        get_medgulf_offers,
        get_acig_offers
    )
    print("✓ mock_insurance imported")
except Exception as e:
    print(f"✗ mock_insurance import failed: {e}")

try:
    from app import app
    print("✓ app imported")
except Exception as e:
    print(f"✗ app import failed: {e}")

print("\nTesting mock_insurance functions with sample data...")
sample_data = {
    'vehicle_value': 70000,
    'driver_age': 35,
    'purpose_of_use': 'شخصي',
    'vehicle_age': 5
}
try:
    offers_ta = get_taawuniya_offers(sample_data)
    print(f"✓ Tawuniya offers: {len(offers_ta)} offers")
    assert len(offers_ta) == 10, f"Expected 10 offers, got {len(offers_ta)}"
    for i, o in enumerate(offers_ta):
        assert 'company' in o and o['company'] == 'Tawuniya', f"Offer {i} missing company"
        assert 'premium' in o and isinstance(o['premium'], (int, float)), f"Offer {i} premium invalid"
        assert 'coverage_type' in o and o['coverage_type'] in ['TPL', 'Comprehensive'], f"Offer {i} coverage_type invalid"
        assert 'deductible' in o and isinstance(o['deductible'], (int, float)), f"Offer {i} deductible invalid"
        assert 'add_ons' in o and isinstance(o['add_ons'], list), f"Offer {i} add_ons invalid"
        assert 'availability' in o and o['availability'] == True, f"Offer {i} availability missing"
    print("  All Tawuniya offers valid.")
except Exception as e:
    print(f"✗ Tawuniya test failed: {e}")

try:
    offers_taka = get_takaful_alrajhi_offers(sample_data)
    print(f"✓ Takaful Al-Rajhi offers: {len(offers_taka)} offers")
    assert len(offers_taka) == 10
except Exception as e:
    print(f"✗ Takaful Al-Rajhi test failed: {e}")

try:
    offers_med = get_medgulf_offers(sample_data)
    print(f"✓ Medgulf offers: {len(offers_med)} offers")
    assert len(offers_med) == 10
except Exception as e:
    print(f"✗ Medgulf test failed: {e}")

try:
    offers_ac = get_acig_offers(sample_data)
    print(f"✓ ACIG offers: {len(offers_ac)} offers")
    assert len(offers_ac) == 10
except Exception as e:
    print(f"✗ ACIG test failed: {e}")

print("\nTesting agent1 with sample data (will call mock APIs via localhost? we'll skip actual calls)...")
# We'll not actually call the APIs because they are not running; just test instantiation.
try:
    agent1 = DataReceiverRetrievalAgent()
    print("✓ Agent1 instantiated")
    # We could test get_unified_quote_set but it would require running APIs; skip.
except Exception as e:
    print(f"✗ Agent1 test failed: {e}")

print("\nTesting agent2 and agent3 with mock data...")
# Create mock unified quotes (simulating output of agent1)
mock_quotes = []
for i in range(5):
    mock_quotes.append({
        "company": "TestCo",
        "premium": 500 + i*50,
        "coverage_type": "TPL" if i % 2 == 0 else "Comprehensive",
        "deductible": 500 + i*100,
        "add_ons": ["roadside_assistance"] if i % 3 == 0 else [],
        "coverage_scope": ["third_party"] if i % 2 == 0 else ["collision", "theft"],
        "provider_reliability": 8.0,
        "availability": True
    })
try:
    agent2 = RecommendationAgent()
    recommended_quote, breakdown = agent2.recommend(mock_quotes, sample_data)
    if recommended_quote is None:
        print("✗ Agent2 returned no recommendation")
    else:
        print("✓ Agent2 recommendation successful")
        print(f"  Recommended company: {recommended_quote['company']}")
        print(f"  Premium: {recommended_quote['premium']}")
        # Check breakdown exists
        assert breakdown is not None, "Breakdown is None"
        assert isinstance(breakdown, dict), "Breakdown not dict"
        print(f"  Breakdown keys: {list(breakdown.keys())}")
except Exception as e:
    print(f"✗ Agent2 test failed: {e}")

try:
    agent3 = ExplainerAgent()
    # Need scored list from agent2
    scored_list = agent2.compute_scores(mock_quotes, sample_data)
    explanation = agent3.explain(recommended_quote, breakdown, scored_list)
    if explanation is None:
        print("✗ Agent3 returned no explanation")
    else:
        print("✓ Agent3 explanation successful")
        # Explanation is a string (HTML text)
        assert isinstance(explanation, str), "Explanation not string"
        assert len(explanation) > 0, "Explanation empty"
        print(f"  Explanation length: {len(explanation)} chars")
except Exception as e:
    print(f"✗ Agent3 test failed: {e}")

print("\nAll tests completed.")