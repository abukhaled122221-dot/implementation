"""
تهيئة قاعدة بيانات منصة شركات التأمين (insurers_mock.db):
- نقل الجداول القديمة من thiqa.db مع تعبئة التحمّل والإضافات لكل باقة.
- عدم إعادة بذر العروض عند كل تشغيل (حذف أدمن الشركة لعرض يبقى محذوفاً).
- باقات VIP تتضمن إصلاح الوكالة كما في وصفها.
"""

import json
import sqlite3

import mock_insurer_api as mock

LEGACY_OFFERS_SQL = """
CREATE TABLE Company_Offers (
    OfferId INTEGER PRIMARY KEY AUTOINCREMENT, ProviderId TEXT NOT NULL, OfferName VARCHAR(100) NOT NULL,
    CoverageType VARCHAR(30) NOT NULL, BasePremiumRate DECIMAL(10,4) NOT NULL, MinPremium DECIMAL(10,2) NOT NULL,
    Description TEXT, IsActive BOOLEAN NOT NULL DEFAULT 1,
    CreatedAt DATETIME NOT NULL DEFAULT (datetime('now')), UpdatedAt DATETIME NOT NULL DEFAULT (datetime('now')));
"""


def init_with(monkeypatch, tmp_path, legacy_db=None):
    """يشغّل _init_db على قاعدة مؤقتة (واختيارياً قاعدة ثقة قديمة للترحيل)."""
    insurers_db = tmp_path / "insurers.sqlite"
    monkeypatch.setattr(mock, "DB_PATH", str(insurers_db))
    if legacy_db:
        monkeypatch.setenv("THIQA_DB_PATH", str(legacy_db))
    else:
        monkeypatch.delenv("THIQA_DB_PATH", raising=False)
    mock._init_db()
    return insurers_db


def offers(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT ProviderId, OfferName, BasePremiumRate, Deductible, AddOnsJson FROM Company_Offers"
    ).fetchall()
    conn.close()
    return rows


def test_legacy_offers_are_migrated_with_tier_addons_and_deductibles(monkeypatch, tmp_path):
    legacy = tmp_path / "thiqa.db"
    conn = sqlite3.connect(legacy)
    conn.executescript(LEGACY_OFFERS_SQL)
    for provider, name, cov, rate, min_p, desc in mock.DEFAULT_28_OFFERS:
        conn.execute(
            "INSERT INTO Company_Offers (ProviderId, OfferName, CoverageType, BasePremiumRate, MinPremium, Description)"
            " VALUES (?,?,?,?,?,?)",
            (provider, name, cov, rate, min_p, desc),
        )
    conn.commit()
    conn.close()

    rows = offers(init_with(monkeypatch, tmp_path, legacy))

    assert len(rows) == 28
    for provider, _name, rate, deductible, addons_json in rows:
        expected_deductible, expected_addons = mock._tier_defaults(float(rate), provider)
        assert deductible == expected_deductible
        assert json.loads(addons_json) == expected_addons
    # الجدول القديم حُذف من قاعدة ثقة بعد نقله
    conn = sqlite3.connect(legacy)
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='Company_Offers'").fetchone() is None
    conn.close()


def test_vip_tier_includes_agency_repair_for_every_company():
    for provider in mock.DEFAULT_PRICING_RULES:
        _deductible, addons = mock._tier_defaults(2500, provider)
        assert "agency_repair" in addons
        assert len(addons) == len(set(addons))


def test_deleted_offer_is_not_reseeded_on_restart(monkeypatch, tmp_path):
    db = init_with(monkeypatch, tmp_path)
    assert len(offers(db)) == 28

    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM Company_Offers WHERE OfferId = (SELECT min(OfferId) FROM Company_Offers)")
    conn.commit()
    conn.close()

    init_with(monkeypatch, tmp_path)  # إعادة تشغيل المنصة
    assert len(offers(db)) == 27


def test_admin_choice_of_no_addons_is_kept_on_restart(monkeypatch, tmp_path):
    db = init_with(monkeypatch, tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("UPDATE Company_Offers SET AddOnsJson='[]' WHERE OfferId = (SELECT max(OfferId) FROM Company_Offers)")
    conn.commit()
    conn.close()

    init_with(monkeypatch, tmp_path)
    conn = sqlite3.connect(db)
    addons = conn.execute(
        "SELECT AddOnsJson FROM Company_Offers WHERE OfferId = (SELECT max(OfferId) FROM Company_Offers)"
    ).fetchone()[0]
    conn.close()
    assert addons == "[]"
