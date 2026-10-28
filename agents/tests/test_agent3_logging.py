import sqlite3

from agent3_explainer import ExplainerAgent


def test_agent3_logs_explanation_to_explicit_temp_database(tmp_path):
    db_path = tmp_path / "agent3.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE Explanations (ExplId INTEGER PRIMARY KEY, RecId INTEGER, MainReasons TEXT, CriteriaBreakdown TEXT, ComparisonText TEXT)")
    agent = ExplainerAgent(db_path=str(db_path))
    selected = {
        "provider_name": "Test Company", "plan_name": "Plan Gold", "premium": 500,
        "suitability_score": 0.8,
        "score_breakdown": {"premium_score": 0.8, "reliability_score": 0.9},
        "weighted_contributions": {"premium": 0.4, "reliability": 0.2},
        "add_ons": ["roadside_assistance"],
        "requested_add_ons_matched": ["roadside_assistance"],
        "requested_add_ons_missing": ["gulf_coverage"],
    }
    result = agent.run(selected, [selected], rec_id=42)
    assert "Plan Gold" in result["main_reasons"]
    assert any("مساعدة على الطريق" in text for text in result["criteria_explanations"])
    assert any("تغطية دول الخليج" in text for text in result["criteria_explanations"])
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT RecId, MainReasons FROM Explanations").fetchone()
    assert row and row[0] == 42 and "Plan Gold" in row[1]
