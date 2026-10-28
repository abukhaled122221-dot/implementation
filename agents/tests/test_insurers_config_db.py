"""
قراءة إعدادات شركات التأمين من قاعدة بيانات ثقة (عقد C3):
- التعديلات تُقرأ في كل طلب (بدون إعادة تشغيل).
- الرجوع للإعدادات الافتراضية فقط عند غياب أي إعدادات في القاعدة.
- تعطيل كل الشركات من لوحة الأدمن لا يعيد تفعيلها بصمت.
"""

import sqlite3

import insurers_config
from insurers_config import load_insurers_from_db

SCHEMA = """
CREATE TABLE Insurance_Providers(ProviderId TEXT PRIMARY KEY, ProviderName TEXT NOT NULL, LogoUrl TEXT,
    Website TEXT, IsActive INTEGER NOT NULL DEFAULT 1, Reliability REAL, WorkshopNetwork TEXT, DigitalScore REAL);
CREATE TABLE API_Settings(SettingId INTEGER PRIMARY KEY AUTOINCREMENT, ProviderId TEXT NOT NULL UNIQUE,
    Endpoint TEXT NOT NULL, AuthKey TEXT, AuthScheme TEXT NOT NULL DEFAULT 'x-api-key', Adapter TEXT NOT NULL,
    Protocol TEXT NOT NULL DEFAULT 'REST/JSON', Timeout INTEGER NOT NULL DEFAULT 5);
"""


def make_db(tmp_path, providers):
    path = tmp_path / "thiqa.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    for pid, active, reliability in providers:
        conn.execute(
            "INSERT INTO Insurance_Providers VALUES (?,?,?,?,?,?,?,?)",
            (pid, pid.upper(), None, None, active, reliability, "متوسط", 0.7),
        )
        conn.execute(
            "INSERT INTO API_Settings(ProviderId, Endpoint, Adapter, Timeout) VALUES (?,?,?,?)",
            (pid, f"http://insurer.test/{pid}/quotes", pid, 7),
        )
    conn.commit()
    conn.close()
    return path


def test_reads_active_providers_with_full_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("THIQA_DB_PATH", str(make_db(tmp_path, [("tawuniya", 1, 0.9), ("acig", 0, 0.8)])))
    providers = load_insurers_from_db()
    assert [p["provider_id"] for p in providers] == ["tawuniya"]
    assert providers[0]["base_url"] + providers[0]["path"] == "http://insurer.test/tawuniya/quotes"
    assert providers[0]["timeout"] == 7.0
    assert providers[0]["_source"] == "db"


def test_include_inactive_returns_disabled_providers_for_connection_tests(tmp_path, monkeypatch):
    monkeypatch.setenv("THIQA_DB_PATH", str(make_db(tmp_path, [("tawuniya", 1, 0.9), ("acig", 0, 0.8)])))
    assert {p["provider_id"] for p in load_insurers_from_db(include_inactive=True)} == {"tawuniya", "acig"}


def test_all_providers_disabled_means_no_providers_not_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("THIQA_DB_PATH", str(make_db(tmp_path, [("tawuniya", 0, 0.9), ("acig", 0, 0.8)])))
    assert load_insurers_from_db() == []


def test_empty_configuration_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("THIQA_DB_PATH", str(make_db(tmp_path, [])))
    defaults = {p["provider_id"] for p in insurers_config.load_insurers()}
    assert {p["provider_id"] for p in load_insurers_from_db()} == defaults


def test_missing_database_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("THIQA_DB_PATH", str(tmp_path / "does-not-exist.db"))
    assert len(load_insurers_from_db()) == 4


def test_zero_reliability_is_kept_not_replaced_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("THIQA_DB_PATH", str(make_db(tmp_path, [("tawuniya", 1, 0.0)])))
    assert load_insurers_from_db()[0]["reliability"] == 0.0
