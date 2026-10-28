"""
منظومة المواقع المستقلة لشركات التأمين (منفذ 8001):
- بدون أي بيانات عميل مسجلة مسبقاً (حقول فارغة يدخلها العميل بنفسه)
- إزالة قسم الوثائق المصدرة من واجهة الأفراد نهائياً
- 28 عرضاً تأمينياً جاهزاً في قاعدة البيانات
- تسجيل دخول مستقل لموظفي كل شركة (الأدمن)
"""

import asyncio
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from insurers_config import api_key_for

app = FastAPI(title="مواقع شركات التأمين المستقلة")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FAULT_TYPES = {"timeout", "500", "503", "bad_json", "empty", "malformed"}
PROVIDERS = {"tawuniya", "rajhi", "medgulf", "acig"}
DB_PATH = os.getenv("INSURERS_DB_PATH") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "database", "insurers_mock.db"))


def _faults_from_env() -> dict[str, str]:
    faults = {}
    for part in os.getenv("MOCK_FAULTS", "").split(","):
        if "=" in part:
            pid, fault = part.split("=", 1)
            if pid.strip() in PROVIDERS and fault.strip() in FAULT_TYPES:
                faults[pid.strip()] = fault.strip()
    return faults


FAULTS: dict[str, str] = _faults_from_env()

DEFAULT_PRICING_RULES = {
    "tawuniya": {
        "id": "tawuniya",
        "name": "التعاونية",
        "slogan": "الخيار الأول لتأمين المركبات في المملكة العربية السعودية",
        "badge": "T",
        "color": "#059669",
        "bg_hero": "from-emerald-900 via-emerald-800 to-slate-900",
        "endpoint": "/tawuniya/quotes",
        "tpl_base": 483.0,
        "comp_base": 1650.0,
        "deductible": 500.0,
        "city_major_mult": 1.10,
        "city_other_mult": 0.95,
        "gender_male_mult": 1.05,
        "gender_female_mult": 0.95,
        "no_accidents_mult": 0.85,
        "has_accidents_mult": 1.35,
        "single_car_mult": 1.00,
        "multi_car_mult": 0.90,
        "addons": ["roadside_assistance", "replacement_car", "gulf_coverage"],
    },
    "rajhi": {
        "id": "rajhi",
        "name": "الراجحي تكافل",
        "slogan": "تأمين تكافلي متوافق مع الشريعة الإسلامية بخدمات رقمية فورية",
        "badge": "R",
        "color": "#2563eb",
        "bg_hero": "from-blue-900 via-indigo-900 to-slate-900",
        "endpoint": "/rajhi/offers",
        "tpl_base": 507.0,
        "comp_base": 1580.0,
        "deductible": 750.0,
        "city_major_mult": 1.08,
        "city_other_mult": 0.92,
        "gender_male_mult": 1.03,
        "gender_female_mult": 0.95,
        "no_accidents_mult": 0.88,
        "has_accidents_mult": 1.30,
        "single_car_mult": 1.00,
        "multi_car_mult": 0.88,
        "addons": ["agency_repair", "roadside_assistance", "windshield_cover"],
    },
    "medgulf": {
        "id": "medgulf",
        "name": "ميدغلف",
        "slogan": "حماية متكاملة وباقات مرنة تناسب تطلعاتك وميزانيتك",
        "badge": "M",
        "color": "#d97706",
        "bg_hero": "from-amber-900 via-yellow-900 to-slate-900",
        "endpoint": "/medgulf/plans",
        "tpl_base": 469.0,
        "comp_base": 1490.0,
        "deductible": 1000.0,
        "city_major_mult": 1.12,
        "city_other_mult": 0.94,
        "gender_male_mult": 1.04,
        "gender_female_mult": 0.96,
        "no_accidents_mult": 0.90,
        "has_accidents_mult": 1.40,
        "single_car_mult": 1.00,
        "multi_car_mult": 0.92,
        "addons": ["windshield_cover", "gulf_coverage"],
    },
    "acig": {
        "id": "acig",
        "name": "أسيج",
        "slogan": "أفضل العروض الاقتصادية لتأمين المركبات الشامل وضد الغير",
        "badge": "ACIG",
        "color": "#dc2626",
        "bg_hero": "from-red-900 via-rose-900 to-slate-900",
        "endpoint": "/acig/quote",
        "tpl_base": 428.0,
        "comp_base": 1350.0,
        "deductible": 1500.0,
        "city_major_mult": 1.05,
        "city_other_mult": 0.90,
        "gender_male_mult": 1.00,
        "gender_female_mult": 0.95,
        "no_accidents_mult": 0.90,
        "has_accidents_mult": 1.25,
        "single_car_mult": 1.00,
        "multi_car_mult": 0.85,
        "addons": ["roadside_assistance"],
    },
}

PRICING_RULES = json.loads(json.dumps(DEFAULT_PRICING_RULES))

DEFAULT_28_OFFERS = [
    ("tawuniya", "التعاونية ضد الغير الأساسي (اقتصادي)", "TPL", 420, 420,
     "[فئة اقتصادية] تأمين إلزامي ضد الغير بأقل تكلفة يغطي المسؤولية المدنية للطرف الثالث حتى 10 مليون ريال."),
    ("tawuniya", "التعاونية ضد الغير بلس (متوسط)", "TPL", 540, 540,
     "[فئة متوسطة] تأمين ضد الغير مع خدمة المساعدة على الطريق على مدار الساعة وسرعة إنهاء الإجراءات."),
    ("tawuniya", "التعاونية ضد الغير بريميوم (مميز)", "TPL", 690, 690,
     "[فئة مميزة] تأمين ضد الغير يشمل الحوادث الشخصية للسائق والركاب مع تغطية القطر والسحب المجاني."),
    ("tawuniya", "التعاونية الشامل الاقتصادي (رخيص)", "Comprehensive", 1250, 1250,
     "[فئة اقتصادية] تأمين شامل أساسي بسعر مخفض مع إصلاح في الورش المعتمدة لدى التعاونية."),
    ("tawuniya", "التعاونية الشامل الفضي (متوسط)", "Comprehensive", 1650, 1650,
     "[فئة متوسطة] تغطية شاملة متوازنة تشمل الحوادث والسرقة والحريق مع مساعدة فورية على الطريق."),
    ("tawuniya", "التعاونية الشامل الذهبي (فوق المتوسط)", "Comprehensive", 2200, 2200,
     "[فئة متقدمة] تأمين شامل يضم سيارة بديلة مجانية وتغطية الزجاج والكوارث الطبيعية."),
    ("tawuniya", "باقة التعاونية الماسية الشاملة VIP (غالي)", "Comprehensive", 2950, 2950,
     "[فئة كبار الشخصيات VIP] أعلى تغطية شاملة مع إصلاح وكالة وتغطية دول الخليج وسيارة بديلة فورية."),

    ("rajhi", "الراجحي ضد الغير الاقتصادي (رخيص)", "TPL", 440, 440,
     "[فئة اقتصادية] وثيقة تكافلية ضد الغير متوافقة مع الشريعة الإسلامية بسعر اقتصادي وإصدار رقمي فوري."),
    ("rajhi", "الراجحي ضد الغير الرقمي (متوسط)", "TPL", 560, 560,
     "[فئة متوسطة] تأمين ضد الغير مع إدارة ذكية للمطالبات عبر تطبيق الراجحي تكافل ومساعدة الطريق."),
    ("rajhi", "الراجحي ضد الغير بلس الذكي (مميز)", "TPL", 710, 710,
     "[فئة مميزة] تغطية ضد الغير موسعة مع حماية السائق والركاب وخدمة الطوارئ السريعة في كافة مناطق المملكة."),
    ("rajhi", "الراجحي الشامل الميسر (رخيص)", "Comprehensive", 1190, 1190,
     "[فئة اقتصادية] أرخص باقة تأمين شامل تكافلي تغطي الحوادث المرورية والسرقة والحريق."),
    ("rajhi", "الراجحي الشامل العائلي (متوسط)", "Comprehensive", 1580, 1580,
     "[فئة متوسطة] باقة شاملة متوازنة لسيارات الأفراد والعائلات مع تغطية الزجاج الأمامي ومساعدة الطريق."),
    ("rajhi", "الراجحي الشامل بريميوم (فوق المتوسط)", "Comprehensive", 2100, 2100,
     "[فئة متقدمة] تغطية شاملة واسعة مع سيارة بديلة لمدة 15 يوماً وتغطية الأعطال الميكانيكية الطارئة."),
    ("rajhi", "باقة الراجحي التكافلية النخبة وكالة (غالي)", "Comprehensive", 2850, 2850,
     "[فئة النخبة VIP] تأمين شامل فاخر مع إصلاح وكالة المعتمد وتغطية دول مجلس التعاون الخليجي بالكامل."),

    ("medgulf", "ميدغلف ضد الغير التوفير (رخيص)", "TPL", 410, 410,
     "[فئة اقتصادية] تأمين ضد الغير بسعر منافس جداً يفي بكافة متطلبات المرور والربط الإلكتروني الفوري."),
    ("medgulf", "ميدغلف ضد الغير المتوازن (متوسط)", "TPL", 520, 520,
     "[فئة متوسطة] تأمين ضد الغير مع دعم فني متواصل وخدمة سحب المركبة عند التعطل."),
    ("medgulf", "ميدغلف ضد الغير الشامل للغير (مميز)", "TPL", 660, 660,
     "[فئة مميزة] حماية موسعة ضد الغير تشمل تغطية الحوادث الشخصية للسائق وأفراد العائلة."),
    ("medgulf", "ميدغلف الشامل الاقتصادي (رخيص)", "Comprehensive", 1120, 1120,
     "[فئة اقتصادية] تأمين شامل بتكلفة اقتصادية ممتازة مع شبكة واسعة من الورش المعتمدة."),
    ("medgulf", "ميدغلف الشامل العائلي (متوسط)", "Comprehensive", 1490, 1490,
     "[فئة متوسطة] الخيار المتوازن لتأمين المركبات شاملاً الحوادث والسيول والبرد وتغطية الزجاج."),
    ("medgulf", "ميدغلف الشامل البلاتيني (فوق المتوسط)", "Comprehensive", 1980, 1980,
     "[فئة متقدمة] تأمين شامل بلاتيني مع سيارة بديلة وتغطية جغرافية ممتدة لدول الخليج."),
    ("medgulf", "باقة ميدغلف رويال الشاملة VIP (غالي)", "Comprehensive", 2690, 2690,
     "[فئة رويال VIP] أقصى درجات الحماية الشاملة مع إصلاح في الوكالة وخدمة استلام وتسليم المركبة."),

    ("acig", "أسيج التوفير ضد الغير (الأرخص)", "TPL", 380, 380,
     "[فئة اقتصادية] أرخص وثيقة تأمين ضد الغير في المنصة لأصحاب الميزانية الاقتصادية المحدودة."),
    ("acig", "أسيج ضد الغير المطور (متوسط)", "TPL", 490, 490,
     "[فئة متوسطة] تأمين ضد الغير بسعر معتدل يشمل خدمة المساعدة على الطريق داخل المدن."),
    ("acig", "أسيج ضد الغير بلس (مميز)", "TPL", 620, 620,
     "[فئة مميزة] تأمين ضد الغير مع تغطية الحوادث الشخصية للسائق وميزة تسوية المطالبات السريعة."),
    ("acig", "أسيج الشامل التوفير (رخيص)", "Comprehensive", 990, 990,
     "[فئة اقتصادية] أوفر وثيقة تأمين شامل في السوق تغطي أضرار الحوادث والسرقة والحريق."),
    ("acig", "أسيج الشامل المتوازن (متوسط)", "Comprehensive", 1350, 1350,
     "[فئة متوسطة] تأمين شامل بسعر متوازن جداً مع مساعدة على الطريق وتغطية الكوارث الطبيعية."),
    ("acig", "أسيج الشامل المميز (فوق المتوسط)", "Comprehensive", 1790, 1790,
     "[فئة متقدمة] تغطية شاملة مطورة تشمل سيارة بديلة وتغطية الزجاج والحوادث الشخصية."),
    ("acig", "باقة أسيج القمة الشاملة وكالة (غالي)", "Comprehensive", 2450, 2450,
     "[فئة القمة VIP] الباقة العليا من أسيج مع إصلاح وكالة وتغطية شاملة داخل المملكة ودول الخليج."),
]


def _tier_defaults(rate: float, provider_id: str) -> tuple[float, list[str]]:
    """Return the seeded offer's deductible and add-ons for its price tier.

    Higher tiers include more add-ons and lower deductibles. The top (VIP) tier of
    every company is described as including agency repair ("إصلاح وكالة"), so it
    always gets agency_repair on top of the company's standard add-ons.
    """
    addons = list(DEFAULT_PRICING_RULES[provider_id]["addons"])
    if rate >= 2400:
        return 500, ["agency_repair"] + [a for a in addons if a != "agency_repair"]
    if rate >= 1800:
        return 1000, addons[:2]
    if rate >= 1300:
        return 1500, addons[:1]
    return 2000, addons[:1]


def _backfill_offer_tiers(cur, only_empty: bool = True) -> None:
    """Fill Deductible/AddOnsJson from the tier table for offers that predate those columns.

    Called only right after a schema/legacy migration — never on normal startups, so an
    insurer admin who deliberately sets an offer to "no add-ons" is not overridden.
    """
    rows = cur.execute(
        "SELECT OfferId, ProviderId, BasePremiumRate, AddOnsJson FROM Company_Offers"
    ).fetchall()
    for offer_id, provider_id, rate, addons_json in rows:
        if provider_id not in DEFAULT_PRICING_RULES:
            continue
        if only_empty and addons_json not in (None, "", "[]"):
            continue
        deductible, addons = _tier_defaults(float(rate), provider_id)
        cur.execute(
            "UPDATE Company_Offers SET Deductible=?, AddOnsJson=? WHERE OfferId=?",
            (deductible, json.dumps(addons), offer_id),
        )


def _init_db():
    new_mock_db = not os.path.exists(DB_PATH)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
CREATE TABLE IF NOT EXISTS Company_Offers (
            OfferId           INTEGER PRIMARY KEY AUTOINCREMENT,
            ProviderId        TEXT NOT NULL,
            OfferName         VARCHAR(100) NOT NULL,
            CoverageType      VARCHAR(30) NOT NULL,
            BasePremiumRate   DECIMAL(10,4) NOT NULL,
            MinPremium        DECIMAL(10,2) NOT NULL,
            Description       TEXT,
            Deductible        REAL NOT NULL DEFAULT 1500,
            AddOnsJson        TEXT NOT NULL DEFAULT '[]',
            IsActive          BOOLEAN NOT NULL DEFAULT 1,
            CreatedAt         DATETIME NOT NULL DEFAULT (datetime('now')),
            UpdatedAt         DATETIME NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS Company_Pricing_Rules (
            ProviderId        TEXT PRIMARY KEY,
            TplBase           REAL NOT NULL,
            CompBase          REAL NOT NULL,
            Deductible        REAL NOT NULL,
            CityMajorMult     REAL NOT NULL,
            CityOtherMult     REAL NOT NULL,
            GenderMaleMult    REAL NOT NULL,
            GenderFemaleMult  REAL NOT NULL,
            NoAccidentsMult   REAL NOT NULL,
            HasAccidentsMult  REAL NOT NULL,
            SingleCarMult     REAL NOT NULL,
            MultiCarMult      REAL NOT NULL,
            AddOnsJson        TEXT NOT NULL,
            UpdatedAt         DATETIME NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS Issued_Policies (
            PolicyId        INTEGER PRIMARY KEY AUTOINCREMENT,
            PolicyNumber    TEXT NOT NULL UNIQUE,
            ProviderId      TEXT NOT NULL,
            ProviderName    TEXT NOT NULL,
            OfferName       TEXT NOT NULL,
            CustomerName    TEXT NOT NULL,
            NationalId      TEXT NOT NULL,
            Phone           TEXT NOT NULL,
            VehicleSerial   TEXT NOT NULL,
            City            TEXT DEFAULT 'riyadh',
            Gender          TEXT DEFAULT 'male',
            HasAccidents    TEXT DEFAULT 'no',
            CarsCount       TEXT DEFAULT 'single',
            CoverageType    TEXT NOT NULL,
            TotalAmount     REAL NOT NULL,
            PaymentMethod   TEXT NOT NULL,
            CardLast4       TEXT DEFAULT '0000',
            IssuedAt        DATETIME NOT NULL DEFAULT (datetime('now'))
        );
    """)

    offer_columns = [c[1] for c in cur.execute("PRAGMA table_info(Company_Offers)").fetchall()]
    added_offer_columns = False
    if "Deductible" not in offer_columns:
        cur.execute("ALTER TABLE Company_Offers ADD COLUMN Deductible REAL NOT NULL DEFAULT 1500")
        added_offer_columns = True
    if "AddOnsJson" not in offer_columns:
        cur.execute("ALTER TABLE Company_Offers ADD COLUMN AddOnsJson TEXT NOT NULL DEFAULT '[]'")
        added_offer_columns = True
    if added_offer_columns:
        _backfill_offer_tiers(cur, only_empty=False)
    existing_cols_rules = [c[1] for c in cur.execute("PRAGMA table_info(Company_Pricing_Rules)").fetchall()]
    if "CompBase" not in existing_cols_rules:
        cur.execute("ALTER TABLE Company_Pricing_Rules ADD COLUMN CompBase REAL NOT NULL DEFAULT 1500.0")

    existing_cols_pol = [c[1] for c in cur.execute("PRAGMA table_info(Issued_Policies)").fetchall()]
    for col_name, col_def in [
        ("City", "TEXT DEFAULT 'riyadh'"),
        ("Gender", "TEXT DEFAULT 'male'"),
        ("HasAccidents", "TEXT DEFAULT 'no'"),
        ("CarsCount", "TEXT DEFAULT 'single'"),
        ("CardLast4", "TEXT DEFAULT '0000'"),
    ]:
        if col_name not in existing_cols_pol:
            cur.execute(f"ALTER TABLE Issued_Policies ADD COLUMN {col_name} {col_def}")

    legacy_path = os.getenv("THIQA_DB_PATH")
    if new_mock_db and legacy_path and os.path.abspath(legacy_path) != os.path.abspath(DB_PATH) and os.path.exists(legacy_path):
        legacy = sqlite3.connect(legacy_path)
        legacy.row_factory = sqlite3.Row
        try:
            for table in ("Company_Offers", "Company_Pricing_Rules", "Issued_Policies"):
                exists = legacy.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
                if not exists:
                    continue
                source_cols = [x[1] for x in legacy.execute(f"PRAGMA table_info({table})")]
                target_cols = [x[1] for x in cur.execute(f"PRAGMA table_info({table})")]
                common = [name for name in source_cols if name in target_cols]
                if not cur.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                    cols = ",".join(common)
                    marks = ",".join("?" for _ in common)
                    values = [tuple(row[name] for name in common) for row in legacy.execute(f"SELECT {cols} FROM {table}")]
                    if values:
                        cur.executemany(f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({marks})", values)
                    # العروض القديمة لم يكن لها تحمّل/إضافات لكل باقة → نعبئها من جدول الفئات
                    if table == "Company_Offers" and "AddOnsJson" not in source_cols:
                        _backfill_offer_tiers(cur, only_empty=False)
                legacy.execute(f"DROP TABLE {table}")
            legacy.commit()
        finally:
            legacy.close()

    for pid, r in DEFAULT_PRICING_RULES.items():
        cur.execute(
            """
            INSERT OR IGNORE INTO Company_Pricing_Rules
            (ProviderId, TplBase, CompBase, Deductible, CityMajorMult, CityOtherMult,
             GenderMaleMult, GenderFemaleMult, NoAccidentsMult, HasAccidentsMult, SingleCarMult, MultiCarMult, AddOnsJson)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pid, r["tpl_base"], r["comp_base"], r["deductible"],
                r["city_major_mult"], r["city_other_mult"], r["gender_male_mult"], r["gender_female_mult"],
                r["no_accidents_mult"], r["has_accidents_mult"], r["single_car_mult"], r["multi_car_mult"],
                json.dumps(r["addons"])
            )
        )

    # البذر فقط عند جدول فارغ: لو حذف أدمن الشركة عرضاً لا نعيد إنشاء كل العروض عند التشغيل التالي
    offers_count = cur.execute("SELECT COUNT(*) FROM Company_Offers").fetchone()[0]
    if offers_count == 0:
        for prov_id, name, cov, rate, min_p, desc in DEFAULT_28_OFFERS:
            deductible, addons = _tier_defaults(rate, prov_id)
            cur.execute(
                """
                INSERT INTO Company_Offers (ProviderId, OfferName, CoverageType, BasePremiumRate, MinPremium, Description, Deductible, AddOnsJson, IsActive)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    prov_id,
                    name,
                    cov,
                    rate,
                    min_p,
                    desc,
                    deductible,
                    json.dumps(addons),
                ),
            )

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS Company_Admins (ProviderId TEXT PRIMARY KEY, Username TEXT NOT NULL, PasswordSalt BLOB NOT NULL, PasswordHash BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS Admin_Sessions (TokenHash TEXT PRIMARY KEY, ProviderId TEXT NOT NULL, ExpiresAt TEXT NOT NULL);
    """)
    for pid in PROVIDERS:
        user = os.getenv(f"{pid.upper()}_PORTAL_USER", f"{pid}_admin")
        password = os.getenv(f"{pid.upper()}_PORTAL_PASSWORD", {"tawuniya":"Tawuniya@2026","rajhi":"Rajhi@2026","medgulf":"Medgulf@2026","acig":"Acig@2026"}[pid])
        row = cur.execute("SELECT ProviderId FROM Company_Admins WHERE ProviderId=?", (pid,)).fetchone()
        if not row:
            salt = os.urandom(16)
            digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000)
            cur.execute("INSERT INTO Company_Admins VALUES(?,?,?,?)", (pid, user, salt, digest))
    conn.commit()

    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM Company_Pricing_Rules").fetchall()
    for row in rows:
        pid = row["ProviderId"]
        if pid in PRICING_RULES:
            comp_b = float(row["CompBase"]) if "CompBase" in row.keys() and row["CompBase"] else DEFAULT_PRICING_RULES[pid]["comp_base"]
            if comp_b < 100:
                comp_b = DEFAULT_PRICING_RULES[pid]["comp_base"]
            PRICING_RULES[pid].update({
                "tpl_base": float(row["TplBase"]),
                "comp_base": comp_b,
                "deductible": float(row["Deductible"]),
                "city_major_mult": float(row["CityMajorMult"]),
                "city_other_mult": float(row["CityOtherMult"]),
                "gender_male_mult": float(row["GenderMaleMult"]),
                "gender_female_mult": float(row["GenderFemaleMult"]),
                "no_accidents_mult": float(row["NoAccidentsMult"]),
                "has_accidents_mult": float(row["HasAccidentsMult"]),
                "single_car_mult": float(row["SingleCarMult"]),
                "multi_car_mult": float(row["MultiCarMult"]),
                "addons": json.loads(row["AddOnsJson"] or "[]"),
            })
    conn.close()


_init_db()


def _session_provider(authorization: str | None, requested_provider: str | None = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="admin authorization required")
    raw = authorization[7:].strip()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT ProviderId FROM Admin_Sessions WHERE TokenHash=? AND ExpiresAt > datetime('now')", (hashlib.sha256(raw.encode()).hexdigest(),)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    provider = row[0]
    if requested_provider and provider != requested_provider:
        raise HTTPException(status_code=403, detail="provider mismatch")
    return provider


def _age_from_birth(birth_iso: str) -> int:
    try:
        b = date.fromisoformat(birth_iso)
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid birth date")
    t = date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def price(
    provider_id: str,
    age: int,
    value: float,
    coverage: str,
    usage: str,
    mileage: str | None,
    serial: str,
    use_custom_risk: bool = False,
    custom_risk: dict | None = None,
    base_override: float | None = None,
) -> float:
    """Price an offer from its tier base and risk multipliers.

    Comprehensive premium is vehicle_value times a tier-specific rate derived
    from the offer's reference premium (2%–5% of value), with a 500 SAR floor.
    TPL deliberately omits vehicle value because third-party liability does not
    insure the vehicle itself.
    """
    r = PRICING_RULES[provider_id]
    base = base_override if base_override is not None else (r["tpl_base"] if coverage == "TPL" else r["comp_base"])
    age_mult = 1.35 if age < 25 else 1.10 if age < 30 else 1.10 if age >= 60 else 1.0
    use_mult = 1.25 if "commercial" in (usage or "").lower() else 1.0
    km_mult = {"low": 0.95, "high": 1.08}.get((mileage or "").lower(), 1.0)
    h = int(hashlib.sha256(f"{provider_id}|{serial}|{coverage}".encode()).hexdigest()[:8], 16)
    jitter = 0.97 + (h % 600) / 10000

    risk_mult = 1.0
    if custom_risk is not None:
        rk = custom_risk if "city" in custom_risk else custom_risk.get("risk", {})
        city_mult = r["city_major_mult"] if rk.get("city", "riyadh") in ("riyadh", "jeddah", "eastern") else r["city_other_mult"]
        gender_mult = r["gender_female_mult"] if rk.get("gender") == "female" else r["gender_male_mult"]
        acc_mult = r["has_accidents_mult"] if rk.get("has_accidents") == "yes" else r["no_accidents_mult"]
        cars_mult = r["multi_car_mult"] if rk.get("cars_count") == "multiple" else r["single_car_mult"]
        risk_mult = city_mult * gender_mult * acc_mult * cars_mult

    if coverage == "Comprehensive":
        tier_rate = max(0.02, min(0.05, base / 50_000))
        base = max(500.0, max(value, 5000.0) * tier_rate)
    premium = base * age_mult * use_mult * km_mult * jitter * risk_mult
    if coverage == "Comprehensive":
        premium = max(500.0, premium)
    return round(premium, 2)


def _active_offer_packages(provider_id: str, coverage: str, age: int, value: float, usage: str, mileage: str | None, serial: str, risk: dict) -> list[dict]:
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    offers = conn.execute("SELECT * FROM Company_Offers WHERE ProviderId=? AND CoverageType=? AND IsActive=1 ORDER BY BasePremiumRate", (provider_id, coverage)).fetchall()
    conn.close()
    result = []
    for offer in offers:
        try: addons = json.loads(offer["AddOnsJson"] or "[]")
        except (ValueError, TypeError): addons = []
        premium = price(provider_id, age, value, coverage, usage, mileage, serial, custom_risk=risk, base_override=float(offer["BasePremiumRate"]))
        result.append({"id": offer["OfferId"], "name": offer["OfferName"], "description": offer["Description"] or "", "premium": premium, "deductible": float(offer["Deductible"]), "addons": addons})
    return result


def _ref(provider_id: str, serial: str, coverage: str) -> str:
    return hashlib.sha256(f"ref|{provider_id}|{serial}|{coverage}".encode()).hexdigest()[:6].upper()


def _check_key(provider_id: str, presented: str | None):
    if not presented or presented != api_key_for(provider_id):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def _gate(provider_id: str) -> str | None:
    await asyncio.sleep(float(os.getenv("MOCK_LATENCY", "0.25")))
    fault = FAULTS.get(provider_id)
    if fault == "timeout":
        await asyncio.sleep(float(os.getenv("MOCK_TIMEOUT_SLEEP", "30")))
    if fault in ("500", "503"):
        raise HTTPException(status_code=int(fault), detail="insurer internal error (injected)")
    return fault


def _special(fault: str | None, empty_body: dict):
    if fault == "bad_json":
        return PlainTextResponse("<<this is not json>>", media_type="application/json")
    if fault == "empty":
        return JSONResponse(empty_body)
    if fault == "malformed":
        return JSONResponse({"unexpected": "shape"})
    return None


# =============================================================================
# 1. نقاط اتصال الـ API للشركات الأربع
# =============================================================================

class _TawVehicle(BaseModel):
    serial: str
    manufacture_year: int
    value: float = 0.0


class TawuniyaRequest(BaseModel):
    national_id: str
    birth_date: str
    vehicle: _TawVehicle
    coverage: Literal["TPL", "COMP"]
    usage: str
    annual_mileage: str = "medium"
    city: str = "riyadh"
    gender: str = "male"
    has_accidents: str = "no"
    cars_count: str = "single"
    annual_mileage: str | None = None
    city: str = "riyadh"
    gender: str = "male"
    has_accidents: str = "no"
    cars_count: str = "single"


@app.post("/tawuniya/quotes")
async def tawuniya_quotes(body: TawuniyaRequest, x_api_key: str | None = Header(default=None)):
    _check_key("tawuniya", x_api_key)
    fault = await _gate("tawuniya")
    if r := _special(fault, {"insurer": "tawuniya", "packages": []}): return r
    cov = "TPL" if body.coverage == "TPL" else "Comprehensive"
    offers = _active_offer_packages(
        "tawuniya",
        cov,
        _age_from_birth(body.birth_date),
        body.vehicle.value,
        body.usage,
        body.annual_mileage,
        body.vehicle.serial,
        body.model_dump(),
    )
    return {
        "insurer": "tawuniya",
        "packages": [
            {
                "package_id": f"TAW-{offer['id']}-{_ref('tawuniya', body.vehicle.serial, cov)}",
                "coverage": body.coverage,
                "premium_sar": offer["premium"],
                "deductible_sar": offer["deductible"],
                "add_ons": offer["addons"],
                "plan_name": offer["name"],
                "plan_description": offer["description"],
            }
            for offer in offers
        ],
    }


class _RajhiCustomer(BaseModel):
    id_number: str
    dob: str


class _RajhiCar(BaseModel):
    sequence_no: str
    model_year: int
    market_value: float = 0.0


class RajhiRequest(BaseModel):
    customer: _RajhiCustomer
    car: _RajhiCar
    product: Literal["THIRD_PARTY", "COMPREHENSIVE"]
    use: str
    annual_mileage: str = "medium"
    risk: dict = {}


@app.post("/rajhi/offers")
async def rajhi_offers(body: RajhiRequest, authorization: str | None = Header(default=None)):
    _check_key("rajhi", _bearer(authorization)); fault = await _gate("rajhi")
    if r := _special(fault, {"data": {"offers": []}}): return r
    cov = "TPL" if body.product == "THIRD_PARTY" else "Comprehensive"
    offers = _active_offer_packages("rajhi", cov, _age_from_birth(body.customer.dob), body.car.market_value, body.use, body.annual_mileage, body.car.sequence_no, body.risk)
    return {
        "data": {
            "offers": [
                {
                    "id": f"RJ{offer['id']}-{_ref('rajhi', body.car.sequence_no, cov)}",
                    "type": body.product,
                    "price": {
                        "amount": offer["premium"],
                        "currency": "SAR",
                    },
                    "excess": offer["deductible"],
                    "extras": offer["addons"],
                    "name": offer["name"],
                    "description": offer["description"],
                }
                for offer in offers
            ]
        }
    }


class MedgulfRequest(BaseModel):
    idNo: str
    birthDate: str
    chassis: str
    year: int
    value: float = 0.0
    plan: Literal["ضد الغير", "شامل"]
    purpose: str
    mileage: str | None = None
    city: str = "riyadh"
    gender: str = "male"
    has_accidents: str = "no"
    cars_count: str = "single"


@app.post("/medgulf/plans")
async def medgulf_plans(body: MedgulfRequest, x_api_key: str | None = Header(default=None)):
    _check_key("medgulf", x_api_key); fault = await _gate("medgulf")
    if r := _special(fault, {"result": []}): return r
    cov = "TPL" if body.plan == "ضد الغير" else "Comprehensive"
    offers = _active_offer_packages(
        "medgulf",
        cov,
        _age_from_birth(body.birthDate),
        body.value,
        body.purpose,
        body.mileage,
        body.chassis,
        body.model_dump(),
    )
    return {
        "result": [
            {
                "ref": f"MG{offer['id']}-{_ref('medgulf', body.chassis, cov)}",
                "plan": body.plan,
                "annual_cost": f"{offer['premium']:.2f}",
                "deductible": str(int(offer["deductible"])),
                "options": ",".join(offer["addons"]),
                "name": offer["name"],
                "description": offer["description"],
            }
            for offer in offers
        ]
    }


class AcigRequest(BaseModel):
    insured_id: str
    age: int
    vehicle_serial: str
    manufacture_year: int
    vehicle_value: float = 0.0
    cover_type: Literal["TPL", "COMPREHENSIVE"]
    usage: str
    annual_mileage: str = "medium"
    city: str = "riyadh"
    gender: str = "male"
    has_accidents: str = "no"
    cars_count: str = "single"


@app.post("/acig/quote")
async def acig_quote(body: AcigRequest, x_api_key: str | None = Header(default=None)):
    _check_key("acig", x_api_key); fault = await _gate("acig")
    if r := _special(fault, {"quotes": []}): return r
    cov = "TPL" if body.cover_type == "TPL" else "Comprehensive"
    offers = _active_offer_packages(
        "acig",
        cov,
        body.age,
        body.vehicle_value,
        body.usage,
        body.annual_mileage,
        body.vehicle_serial,
        body.model_dump(),
    )
    return {
        "quotes": [
            {
                "quote_ref": f"AC{offer['id']}-{_ref('acig', body.vehicle_serial, cov)}",
                "product": body.cover_type,
                "premium_halalas": int(round(offer["premium"] * 100)),
                "co_pay": offer["deductible"],
                "addons": offer["addons"],
                "name": offer["name"],
                "description": offer["description"],
            }
            for offer in offers
        ]
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "thiqa-mock-insurers"}


# =============================================================================
# 2. خدمات تسجيل دخول الأدمن، التسعير، العروض، وإصدار الوثائق
# =============================================================================

class AdminLoginRequest(BaseModel):
    provider_id: str
    username: str
    password: str


_login_failures: dict[tuple[str, str], list[datetime]] = {}


@app.post("/portal/api/admin/login")
def admin_login(body: AdminLoginRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    key = (body.provider_id, ip)
    cutoff = datetime.now() - timedelta(minutes=10)
    attempts = [when for when in _login_failures.get(key, []) if when > cutoff]
    _login_failures[key] = attempts
    if len(attempts) >= 5:
        raise HTTPException(status_code=429, detail="تم تجاوز عدد محاولات الدخول، حاول بعد 10 دقائق")
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT Username, PasswordSalt, PasswordHash FROM Company_Admins WHERE ProviderId=?", (body.provider_id,)).fetchone()
    if row:
        digest = hashlib.pbkdf2_hmac("sha256", body.password.encode(), row[1], 310000)
        valid = body.username.strip() == row[0] and hmac.compare_digest(digest, row[2])
    else:
        valid = False
    if not valid:
        _login_failures[key] = attempts + [datetime.now()]
        conn.close()
        raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة المرور غير صحيحة")
    _login_failures.pop(key, None)
    token = __import__("secrets").token_urlsafe(32)
    conn.execute("INSERT INTO Admin_Sessions VALUES(?,?,datetime('now','+8 hours'))", (hashlib.sha256(token.encode()).hexdigest(), body.provider_id))
    conn.commit(); conn.close()
    return {"status": "ok", "token": token, "provider_id": body.provider_id}


@app.post("/portal/api/admin/logout")
def admin_logout(authorization: str | None = Header(default=None)):
    provider = _session_provider(authorization)
    token = authorization[7:].strip()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM Admin_Sessions WHERE TokenHash=?", (hashlib.sha256(token.encode()).hexdigest(),))
    conn.commit(); conn.close()
    return {"status": "ok"}


@app.get("/portal/api/company/{provider_id}")
def get_single_company_data(provider_id: str):
    if provider_id not in PRICING_RULES:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    offers = [dict(r) for r in conn.execute("SELECT * FROM Company_Offers WHERE ProviderId = ? AND IsActive=1 ORDER BY BasePremiumRate ASC", (provider_id,)).fetchall()]
    conn.close()
    return {
        "company": PRICING_RULES[provider_id],
        "offers": offers,
    }


@app.get("/portal/api/admin/company/{provider_id}")
def get_admin_company_data(provider_id: str, authorization: str | None = Header(default=None)):
    _session_provider(authorization, provider_id)
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    offers = [dict(r) for r in conn.execute("SELECT * FROM Company_Offers WHERE ProviderId=? ORDER BY BasePremiumRate", (provider_id,)).fetchall()]
    policies = [dict(r) for r in conn.execute("SELECT * FROM Issued_Policies WHERE ProviderId=? ORDER BY PolicyId DESC LIMIT 30", (provider_id,)).fetchall()]
    conn.close()
    return {"company": PRICING_RULES[provider_id], "offers": offers, "policies": policies}


class PricingRuleUpdate(BaseModel):
    tpl_base: float
    comp_base: float
    deductible: float
    city_major_mult: float
    city_other_mult: float
    gender_male_mult: float
    gender_female_mult: float
    no_accidents_mult: float
    has_accidents_mult: float
    single_car_mult: float
    multi_car_mult: float
    addons: list[str]


@app.put("/portal/api/pricing/{provider_id}")
def update_pricing_rules(provider_id: str, body: PricingRuleUpdate, authorization: str | None = Header(default=None)):
    _session_provider(authorization, provider_id)
    if provider_id not in PRICING_RULES:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")

    PRICING_RULES[provider_id].update({
        "tpl_base": round(body.tpl_base, 2),
        "comp_base": round(body.comp_base, 2),
        "deductible": round(body.deductible, 2),
        "city_major_mult": round(body.city_major_mult, 3),
        "city_other_mult": round(body.city_other_mult, 3),
        "gender_male_mult": round(body.gender_male_mult, 3),
        "gender_female_mult": round(body.gender_female_mult, 3),
        "no_accidents_mult": round(body.no_accidents_mult, 3),
        "has_accidents_mult": round(body.has_accidents_mult, 3),
        "single_car_mult": round(body.single_car_mult, 3),
        "multi_car_mult": round(body.multi_car_mult, 3),
        "addons": list(body.addons),
    })

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        UPDATE Company_Pricing_Rules
        SET TplBase=?, CompBase=?, Deductible=?,
            CityMajorMult=?, CityOtherMult=?, GenderMaleMult=?, GenderFemaleMult=?,
            NoAccidentsMult=?, HasAccidentsMult=?, SingleCarMult=?, MultiCarMult=?,
            AddOnsJson=?, UpdatedAt=datetime('now')
        WHERE ProviderId=?
        """,
        (
            body.tpl_base, body.comp_base, body.deductible,
            body.city_major_mult, body.city_other_mult, body.gender_male_mult, body.gender_female_mult,
            body.no_accidents_mult, body.has_accidents_mult, body.single_car_mult, body.multi_car_mult,
            json.dumps(body.addons), provider_id
        )
    )
    conn.commit()
    conn.close()
    return {"message": f"تم حفظ إعدادات التسعيرة لشركة {PRICING_RULES[provider_id]['name']} بنجاح!"}


class OfferCreateModel(BaseModel):
    provider_id: str
    offer_name: str
    coverage_type: Literal["TPL", "Comprehensive"]
    base_premium_rate: float = Field(gt=0)
    description: str = ""
    deductible: float = Field(default=1500, ge=0)
    addons: list[str] = []


@app.post("/portal/api/offers")
def add_company_offer(body: OfferCreateModel, authorization: str | None = Header(default=None)):
    _session_provider(authorization, body.provider_id)
    if body.provider_id not in PRICING_RULES:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO Company_Offers (ProviderId, OfferName, CoverageType, BasePremiumRate, MinPremium, Description, Deductible, AddOnsJson, IsActive)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (body.provider_id, body.offer_name.strip(), body.coverage_type, body.base_premium_rate, body.base_premium_rate, body.description.strip(), body.deductible, json.dumps(body.addons))
    )
    conn.commit()
    conn.close()

    return {"message": "تم إضافة العرض بنجاح!"}


@app.delete("/portal/api/offers/{offer_id}")
def delete_company_offer(offer_id: int, authorization: str | None = Header(default=None)):
    provider_id = _session_provider(authorization)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM Company_Offers WHERE OfferId = ? AND ProviderId = ?", (offer_id, provider_id))
    conn.commit()
    conn.close()
    return {"message": "تم حذف العرض"}


class OfferPatchModel(BaseModel):
    offer_name: str | None = None
    coverage_type: Literal["TPL", "Comprehensive"] | None = None
    base_premium_rate: float | None = Field(default=None, gt=0)
    description: str | None = None
    deductible: float | None = Field(default=None, ge=0)
    addons: list[str] | None = None
    is_active: bool | None = None


@app.patch("/portal/api/offers/{offer_id}")
def update_company_offer(offer_id: int, body: OfferPatchModel, authorization: str | None = Header(default=None)):
    """Update only fields supplied by an authenticated provider administrator."""
    provider_id = _session_provider(authorization)
    # Restrict SQL identifiers to these fixed columns; client values are bound separately.
    allowed_updates = {
        "OfferName": body.offer_name,
        "CoverageType": body.coverage_type,
        "BasePremiumRate": body.base_premium_rate,
        "Description": body.description,
        "Deductible": body.deductible,
        "AddOnsJson": json.dumps(body.addons) if body.addons is not None else None,
        "IsActive": int(body.is_active) if body.is_active is not None else None,
    }
    updates = {
        column: value
        for column, value in allowed_updates.items()
        if value is not None
    }
    if not updates:
        raise HTTPException(status_code=422, detail="no offer fields provided")
    conn = sqlite3.connect(DB_PATH)
    assignments = ", ".join(f"{column}=?" for column in updates)
    cursor = conn.execute(
        f"UPDATE Company_Offers SET {assignments}, UpdatedAt=datetime('now') "
        "WHERE OfferId=? AND ProviderId=?",
        (*updates.values(), offer_id, provider_id),
    )
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="العرض غير موجود")
    return {"status": "ok"}


class PolicyPurchaseModel(BaseModel):
    provider_id: str
    offer_name: str
    customer_name: str
    national_id: str = Field(pattern=r"^[12]\d{9}$")
    phone: str = Field(pattern=r"^(?:05\d{8}|\+9665\d{8})$")
    vehicle_serial: str = Field(min_length=6, max_length=17, pattern=r"^[A-Za-z0-9]{6,17}$")
    city: str = "riyadh"
    gender: str = "male"
    has_accidents: str = "no"
    cars_count: str = "single"
    coverage_type: str
    total_amount: float = Field(gt=0)
    payment_method: str
    card_last4: str = Field(default="0000", pattern=r"^\d{4}$")


@app.post("/portal/api/purchase")
def purchase_policy(body: PolicyPurchaseModel):
    if body.provider_id not in PROVIDERS:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")
    conn = sqlite3.connect(DB_PATH)
    offer = conn.execute("SELECT OfferId FROM Company_Offers WHERE ProviderId=? AND OfferName=? AND CoverageType=? AND IsActive=1", (body.provider_id, body.offer_name, body.coverage_type)).fetchone()
    if offer is None:
        conn.close()
        raise HTTPException(status_code=422, detail="العرض غير متاح")
    p_name = PRICING_RULES[body.provider_id]["name"]
    policy_no = f"POL-{body.provider_id[:3].upper()}-{datetime.now().strftime('%Y%m%d')}-{hashlib.md5(f'{body.national_id}{datetime.now().timestamp()}'.encode()).hexdigest()[:5].upper()}"
    conn.execute(
        """
        INSERT INTO Issued_Policies
        (PolicyNumber, ProviderId, ProviderName, OfferName, CustomerName, NationalId, Phone, VehicleSerial,
         City, Gender, HasAccidents, CarsCount, CoverageType, TotalAmount, PaymentMethod, CardLast4)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            policy_no, body.provider_id, p_name, body.offer_name, body.customer_name,
            body.national_id, body.phone, body.vehicle_serial, body.city, body.gender,
            body.has_accidents, body.cars_count, body.coverage_type, body.total_amount,
            body.payment_method, body.card_last4
        )
    )
    conn.commit()
    conn.close()
    return {
        "policy_number": policy_no,
        "provider_name": p_name,
        "offer_name": body.offer_name,
        "customer_name": body.customer_name,
        "national_id": body.national_id,
        "phone": body.phone,
        "vehicle_serial": body.vehicle_serial,
        "city": body.city,
        "gender": body.gender,
        "has_accidents": body.has_accidents,
        "cars_count": body.cars_count,
        "coverage_type": body.coverage_type,
        "payment_method": body.payment_method,
        "card_last4": body.card_last4,
        "issued_at": date.today().isoformat(),
        "expires_at": (date.today() + timedelta(days=365)).isoformat(),
        "total_amount": body.total_amount,
    }


# =============================================================================
# 3. واجهة المواقع المستقلة لكل شركة تأمين
# =============================================================================

def _render_independent_company_site(provider_id: str) -> str:
    c = PRICING_RULES[provider_id]
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{c['name']}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>body {{ font-family: 'Tajawal', sans-serif; background-color: #f8fafc; }}</style>
</head>
<body class="text-slate-800 min-h-screen flex flex-col">

    <!-- هيدر الموقع المستقل للشركة -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
        <div class="max-w-7xl mx-auto px-4 h-20 flex flex-wrap items-center justify-between gap-4">
            <div class="flex items-center gap-3">
                <div class="w-12 h-12 rounded-2xl text-white flex items-center justify-center text-xl font-black shadow-md" style="background:{c['color']}">
                    {c['badge']}
                </div>
                <div>
                    <h1 class="text-xl font-black text-slate-900">{c['name']}</h1>
                    <span class="text-xs text-slate-500 font-medium">{c['slogan']}</span>
                </div>
            </div>

            <div class="flex items-center gap-2 bg-slate-100 p-1.5 rounded-2xl border border-slate-200">
                <button onclick="switchView('customer')" id="btn-view-customer" class="px-5 py-2 rounded-xl text-xs font-black transition text-white shadow" style="background:{c['color']}">
                    <i class="fa-solid fa-car ml-1"></i> الأفراد وعروض التأمين
                </button>
                <button onclick="switchView('admin')" id="btn-view-admin" class="px-5 py-2 rounded-xl text-xs font-black transition text-slate-600 hover:text-slate-900">
                    <i class="fa-solid fa-user-shield ml-1"></i> بوابة موظفي {c['name']} (الأدمن)
                </button>
            </div>
        </div>
    </header>

    <main class="flex-grow max-w-7xl mx-auto px-4 py-8 w-full">

        <!-- ======================================================= -->
        <!-- 1. واجهة الأفراد وعروض التأمين -->
        <!-- ======================================================= -->
        <div id="view-customer" class="space-y-8">

            <!-- بانر العرض المختار عند الانتقال من منصة ثقة -->
            <div id="recommended-offer-banner" class="hidden rounded-3xl p-8 text-white shadow-xl border-2 border-white/20 bg-gradient-to-r {c['bg_hero']}">
                <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                    <div>
                        <span class="bg-white/20 text-white text-xs font-black px-3.5 py-1 rounded-full uppercase">
                            <i class="fa-solid fa-star ml-1 text-amber-300"></i> عرضك الموصى به في {c['name']}
                        </span>
                        <h2 id="rec-banner-title" class="text-2xl md:text-3xl font-black mt-3">وثيقة تأمين جاهزة للإصدار الفوري</h2>
                        <p id="rec-banner-details" class="text-slate-200 text-sm mt-1"></p>
                    </div>
                    <div class="bg-white text-slate-900 p-5 rounded-2xl shadow-lg flex items-center gap-6 w-full md:w-auto justify-between">
                        <div>
                            <span class="text-xs text-slate-400 font-bold block">السعر المحسوب لبياناتك</span>
                            <span id="rec-banner-price" class="text-3xl font-black font-mono" style="color:{c['color']}"></span>
                        </div>
                        <button id="rec-banner-buy-btn" class="px-6 py-3.5 rounded-xl text-white font-black text-xs shadow-md transition hover:opacity-95" style="background:{c['color']}">
                            إتمام الطلب والشراء الآن <i class="fa-solid fa-cart-shopping mr-1"></i>
                        </button>
                    </div>
                </div>
            </div>

            <!-- بيانات العميل والمركبة (فارغة بدون بيانات مسبقة) -->
            <div class="bg-gradient-to-r {c['bg_hero']} text-white rounded-3xl p-8 shadow-lg">
                <div class="max-w-2xl">
                    <h2 class="text-3xl font-black mb-2">أهلاً بك في البوابة الإلكترونية لشركة {c['name']}</h2>
                    <p class="text-slate-200 text-sm">أدخل بياناتك بالأسفل ليتم احتساب السعر الفوري لجميع الباقات وربط بياناتك تلقائياً بصفحة الشراء.</p>
                </div>

                <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 mt-6 bg-white/10 p-4 rounded-2xl border border-white/15 text-xs">
                    <div>
                        <label class="block text-white/80 font-bold mb-1">رقم الهوية / الإقامة</label>
                        <input type="text" id="c-id" placeholder="أدخل رقم الهوية" maxlength="10" oninput="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white placeholder-slate-400 border border-white/20 font-mono font-bold">
                    </div>
                    <div>
                        <label class="block text-white/80 font-bold mb-1">الرقم التسلسلي للمركبة</label>
                        <input type="text" id="c-serial" placeholder="أدخل الرقم التسلسلي" maxlength="17" oninput="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white placeholder-slate-400 border border-white/20 font-mono font-bold">
                    </div>
                    <div>
                        <label class="block text-white/80 font-bold mb-1">عمر السائق</label>
                        <input type="number" id="c-age" placeholder="مثال: 30" min="18" max="85" oninput="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white placeholder-slate-400 border border-white/20 font-mono font-bold">
                    </div>
                    <div>
                        <label class="block text-white/80 font-bold mb-1">موقع العميل</label>
                        <select id="c-city" onchange="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white border border-white/20 font-bold">
                            <option value="riyadh">الرياض</option>
                            <option value="jeddah">جدة / مكة</option>
                            <option value="eastern">الشرقية</option>
                            <option value="other">مدن أخرى</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-white/80 font-bold mb-1">الجنس</label>
                        <select id="c-gender" onchange="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white border border-white/20 font-bold">
                            <option value="male">ذكر</option>
                            <option value="female">أنثى</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-white/80 font-bold mb-1">الحوادث السابقة</label>
                        <select id="c-acc" onchange="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white border border-white/20 font-bold">
                            <option value="no">لا يوجد حوادث</option>
                            <option value="yes">يوجد حوادث سابقة</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-white/80 font-bold mb-1">عدد السيارات</label>
                        <select id="c-cars" onchange="renderCompanyOffers()" class="w-full px-3 py-2 rounded-xl bg-slate-900/90 text-white border border-white/20 font-bold">
                            <option value="single">سيارة واحدة</option>
                            <option value="multiple">عدة سيارات</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- شريط تصفية العروض حسب الفئة والتغطية -->
            <div class="flex flex-wrap items-center justify-between gap-4">
                <h3 class="text-xl font-black text-slate-900">باقات وعروض {c['name']} المتاحة</h3>
                <div class="flex items-center gap-2 text-xs font-bold">
                    <button onclick="setCovFilter('ALL')" id="cov-btn-ALL" class="px-4 py-2 rounded-xl bg-slate-900 text-white">جميع العروض</button>
                    <button onclick="setCovFilter('TPL')" id="cov-btn-TPL" class="px-4 py-2 rounded-xl bg-white border border-slate-200 text-slate-700">ضد الغير فقط (TPL)</button>
                    <button onclick="setCovFilter('Comprehensive')" id="cov-btn-Comprehensive" class="px-4 py-2 rounded-xl bg-white border border-slate-200 text-slate-700">التأمين الشامل فقط</button>
                </div>
            </div>

            <!-- قائمة عروض الشركة -->
            <div id="company-offers-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"></div>
        </div>

        <!-- ======================================================= -->
        <!-- 2. شاشة تسجيل دخول الأدمن (موظفي الشركة) -->
        <!-- ======================================================= -->
        <div id="view-admin-login" class="hidden py-12">
            <div class="max-w-md mx-auto bg-white rounded-3xl p-8 border border-slate-200 shadow-xl">
                <div class="text-center mb-6">
                    <div class="w-16 h-16 rounded-2xl text-white font-black text-2xl flex items-center justify-center mx-auto mb-3 shadow-md" style="background:{c['color']}">
                        <i class="fa-solid fa-lock"></i>
                    </div>
                    <h2 class="text-2xl font-black text-slate-900">تسجيل دخول موظفي {c['name']}</h2>
                    <p class="text-xs text-slate-500 mt-1">أدخل بيانات حساب الأدمن لإدارة نظام التسعيرة وإضافة العروض</p>
                </div>

                <div id="login-error-msg" class="hidden mb-4 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-bold text-center"></div>

                <form onsubmit="handleAdminLogin(event)" class="space-y-4 text-xs">
                    <div>
                        <label class="font-bold block mb-1.5 text-slate-700">اسم المستخدم</label>
                        <input type="text" id="adm-user" required placeholder="أدخل اسم المستخدم" class="w-full px-4 py-3 rounded-xl border border-slate-200 font-mono text-sm focus:outline-none focus:ring-2">
                    </div>
                    <div>
                        <label class="font-bold block mb-1.5 text-slate-700">كلمة المرور</label>
                        <input type="password" id="adm-pass" required placeholder="أدخل كلمة المرور" class="w-full px-4 py-3 rounded-xl border border-slate-200 font-mono text-sm focus:outline-none focus:ring-2">
                    </div>
                    <button type="submit" class="w-full text-white font-black py-3.5 rounded-xl shadow-lg text-sm transition hover:opacity-95" style="background:{c['color']}">
                        تسجيل الدخول إلى لوحة التحكم <i class="fa-solid fa-arrow-left mr-1"></i>
                    </button>
                </form>
            </div>
        </div>

        <!-- ======================================================= -->
        <!-- 3. لوحة تحكم الأدمن (تظهر فقط بعد تسجيل الدخول) -->
        <!-- ======================================================= -->
        <div id="view-admin" class="hidden space-y-8">
            <div class="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-4">
                <div class="flex items-center gap-4">
                    <div class="w-14 h-14 rounded-2xl text-white font-black text-xl flex items-center justify-center" style="background:{c['color']}">{c['badge']}</div>
                    <div>
                        <span class="text-xs font-bold text-emerald-600"><i class="fa-solid fa-circle-check ml-1"></i> تم تسجيل الدخول كمسؤول تسعير</span>
                        <h2 class="text-2xl font-black text-slate-900">إدارة عروض ونظام تسعيرة {c['name']}</h2>
                    </div>
                </div>
                <button onclick="logoutAdmin()" class="px-4 py-2.5 rounded-xl bg-red-50 hover:bg-red-100 text-red-600 font-bold text-xs transition flex items-center gap-1.5">
                    <i class="fa-solid fa-right-from-bracket"></i> تسجيل الخروج
                </button>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div class="lg:col-span-2 bg-white rounded-3xl p-6 border border-slate-200 shadow-sm">
                    <h3 class="text-lg font-black text-slate-900 mb-1">1. نظام التسعيرة الثابت لشركة {c['name']}</h3>
                    <p class="text-xs text-slate-500 mb-5">تحكم في الأسعار الأساسية الثابتة ومعاملات تسعير الشركة (موقع العميل، الجنس، سجل الحوادث، وعدد السيارات):</p>

                    <div id="adm-msg" class="hidden mb-4 p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm font-bold"></div>

                    <form onsubmit="savePricing(event)" class="space-y-5 text-xs">
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-slate-50 p-4 rounded-2xl border border-slate-200">
                            <div>
                                <label class="font-bold block mb-1">سعر ضد الغير الأساسي (ر.س)</label>
                                <input type="number" id="pr-tpl" step="any" required class="w-full px-3 py-2 rounded-xl border border-slate-300 font-mono font-bold">
                            </div>
                            <div>
                                <label class="font-bold block mb-1">سعر الشامل الأساسي (ر.س)</label>
                                <input type="number" id="pr-comp" step="any" required class="w-full px-3 py-2 rounded-xl border border-slate-300 font-mono font-bold">
                            </div>
                            <div>
                                <label class="font-bold block mb-1">مبلغ التحمل (ر.س)</label>
                                <input type="number" id="pr-ded" step="any" required class="w-full px-3 py-2 rounded-xl border border-slate-300 font-mono font-bold">
                            </div>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div class="p-4 rounded-2xl border border-slate-200 space-y-2">
                                <h4 class="font-black text-slate-900"><i class="fa-solid fa-location-dot ml-1"></i> معامل موقع العميل</h4>
                                <div class="grid grid-cols-2 gap-2">
                                    <div><label class="text-slate-500 block mb-1">المدن المزدحمة (الرياض/جدة)</label><input type="number" id="pr-city-major" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold"></div>
                                    <div><label class="text-slate-500 block mb-1">المدن الأخرى</label><input type="number" id="pr-city-other" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold"></div>
                                </div>
                            </div>

                            <div class="p-4 rounded-2xl border border-slate-200 space-y-2">
                                <h4 class="font-black text-slate-900"><i class="fa-solid fa-venus-mars ml-1"></i> معامل الجنس</h4>
                                <div class="grid grid-cols-2 gap-2">
                                    <div><label class="text-slate-500 block mb-1">ذكر</label><input type="number" id="pr-gender-m" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold"></div>
                                    <div><label class="text-slate-500 block mb-1">أنثى</label><input type="number" id="pr-gender-f" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold"></div>
                                </div>
                            </div>

                            <div class="p-4 rounded-2xl border border-slate-200 space-y-2">
                                <h4 class="font-black text-slate-900"><i class="fa-solid fa-car-burst ml-1"></i> معامل الحوادث السابقة</h4>
                                <div class="grid grid-cols-2 gap-2">
                                    <div><label class="text-slate-500 block mb-1">بدون حوادث سابقة</label><input type="number" id="pr-acc-no" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold text-emerald-700"></div>
                                    <div><label class="text-slate-500 block mb-1">يوجد حوادث سابقة</label><input type="number" id="pr-acc-yes" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold text-red-600"></div>
                                </div>
                            </div>

                            <div class="p-4 rounded-2xl border border-slate-200 space-y-2">
                                <h4 class="font-black text-slate-900"><i class="fa-solid fa-cars ml-1"></i> معامل عدد السيارات</h4>
                                <div class="grid grid-cols-2 gap-2">
                                    <div><label class="text-slate-500 block mb-1">سيارة واحدة فقط</label><input type="number" id="pr-car-single" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold"></div>
                                    <div><label class="text-slate-500 block mb-1">عدة سيارات</label><input type="number" id="pr-car-multi" step="0.01" required class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono font-bold text-emerald-700"></div>
                                </div>
                            </div>
                        </div>

                        <div class="p-4 rounded-2xl border border-slate-200 bg-slate-50">
                            <label class="block font-black text-slate-800 mb-2">المزايا المشمولة في وثائق الشركة:</label>
                            <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                <label class="flex items-center gap-1.5"><input type="checkbox" name="adm-addon" value="agency_repair"> إصلاح وكالة</label>
                                <label class="flex items-center gap-1.5"><input type="checkbox" name="adm-addon" value="roadside_assistance"> مساعدة على الطريق</label>
                                <label class="flex items-center gap-1.5"><input type="checkbox" name="adm-addon" value="replacement_car"> سيارة بديلة</label>
                                <label class="flex items-center gap-1.5"><input type="checkbox" name="adm-addon" value="windshield_cover"> تغطية الزجاج</label>
                                <label class="flex items-center gap-1.5"><input type="checkbox" name="adm-addon" value="gulf_coverage"> تغطية الخليج</label>
                            </div>
                        </div>

                        <button type="submit" class="w-full text-white font-black py-4 rounded-2xl shadow-lg transition" style="background:{c['color']}">
                            حفظ واعتماد نظام التسعيرة للشركة
                        </button>
                    </form>
                </div>

                <div class="space-y-6">
                    <div class="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm">
                        <h3 class="text-md font-black text-slate-900 mb-3">2. إضافة عرض تأميني جديد في {c['name']}</h3>
                        <form onsubmit="addOffer(event)" class="space-y-3 text-xs">
                            <input type="text" id="of-name" required placeholder="اسم العرض" class="w-full px-3 py-2.5 rounded-xl border border-slate-200">
                            <div class="grid grid-cols-2 gap-2">
                                <select id="of-cov" class="w-full px-3 py-2.5 rounded-xl border border-slate-200 font-bold">
                                    <option value="TPL">ضد الغير (TPL)</option>
                                    <option value="Comprehensive">تأمين شامل</option>
                                </select>
                                <input type="number" id="of-rate" step="any" required placeholder="السعر الأساسي الثابت (ر.س)" class="w-full px-3 py-2.5 rounded-xl border border-slate-200 font-mono">
                            </div>
                            <textarea id="of-desc" rows="2" required placeholder="وصف العرض ومميزاته..." class="w-full px-3 py-2 rounded-xl border border-slate-200"></textarea>
                            <button type="submit" class="w-full text-white font-bold py-3 rounded-xl shadow" style="background:{c['color']}">إضافة العرض وتحديث السعر</button>
                        </form>
                        <hr class="my-4 border-slate-100">
                        <div id="adm-offers-list" class="space-y-2 max-h-60 overflow-y-auto text-xs"></div>
                    </div>

                    <div class="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm">
                        <h3 class="text-md font-black text-slate-900 mb-2">سجل الوثائق المباعة (خاص بالأدمن)</h3>
                        <div id="adm-policies-list" class="space-y-2 max-h-60 overflow-y-auto text-xs"></div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- نافذة إتمام الطلب وبيانات البطاقة البنكية والشراء (حقول فارغة بدون بيانات شخص آخر) -->
    <div id="checkout-modal" class="fixed inset-0 bg-slate-900/75 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4 overflow-y-auto">
        <div class="bg-white rounded-3xl max-w-xl w-full p-6 sm:p-8 shadow-2xl border border-slate-200 my-8 max-h-[92vh] overflow-y-auto">
            <div id="chk-form-box">
                <div class="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
                    <div>
                        <span class="text-xs font-bold text-slate-400">{c['name']}</span>
                        <h3 class="text-xl font-black text-slate-900">إكمال الطلب والدفع الإلكتروني</h3>
                    </div>
                    <button onclick="closeCheckout()" class="w-8 h-8 rounded-full bg-slate-100 text-slate-600"><i class="fa-solid fa-xmark"></i></button>
                </div>

                <!-- ملخص العرض وبيانات العميل المربوطة -->
                <div class="bg-slate-50 p-4 rounded-2xl border border-slate-200 mb-4 text-xs space-y-1.5">
                    <div class="flex justify-between"><span>العرض المختار:</span><strong id="chk-offer-name" class="text-slate-900"></strong></div>
                    <div class="flex justify-between"><span>نوع التغطية:</span><strong id="chk-cov-name"></strong></div>
                    <div class="flex justify-between"><span>بيانات التسعير المربوطة:</span><strong id="chk-linked-profile" class="text-indigo-700"></strong></div>
                    <div class="flex justify-between border-t border-slate-200 pt-2 text-sm">
                        <span class="font-bold">الإجمالي شامل الضريبة (15%):</span>
                        <strong id="chk-total-amt" class="font-mono text-lg font-black" style="color:{c['color']}"></strong>
                    </div>
                </div>

                <form onsubmit="submitPurchase(event)" class="space-y-4 text-xs">
                    <!-- 1. بيانات المؤمن له والمركبة -->
                    <div class="p-3.5 rounded-2xl border border-slate-200 space-y-3">
                        <h4 class="font-black text-slate-800 flex items-center gap-1.5">
                            <i class="fa-solid fa-user-check text-emerald-600"></i> 1. بيانات العميل والمركبة
                        </h4>
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                                <label class="font-bold block mb-1">اسم مالك الوثيقة <span class="text-red-500">*</span></label>
                                <input type="text" id="chk-cust-name" required placeholder="أدخل الاسم الثلاثي" class="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs font-bold">
                            </div>
                            <div>
                                <label class="font-bold block mb-1">رقم الجوال <span class="text-red-500">*</span></label>
                                <input type="tel" id="chk-cust-phone" required maxlength="10" placeholder="05XXXXXXXX" class="w-full px-3 py-2 rounded-xl border border-slate-200 font-mono text-xs font-bold">
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="font-bold block mb-1">رقم الهوية / الإقامة <span class="text-red-500">*</span></label>
                                <input type="text" id="chk-cust-id" required maxlength="10" placeholder="أدخل رقم الهوية" class="w-full px-3 py-2 rounded-xl border border-slate-200 bg-slate-50 font-mono text-xs font-bold">
                            </div>
                            <div>
                                <label class="font-bold block mb-1">الرقم التسلسلي / VIN <span class="text-red-500">*</span></label>
                                <input type="text" id="chk-cust-serial" required placeholder="أدخل الرقم التسلسلي" class="w-full px-3 py-2 rounded-xl border border-slate-200 bg-slate-50 font-mono text-xs font-bold">
                            </div>
                        </div>
                    </div>

                    <!-- 2. بيانات البطاقة البنكية أثناء الدفع -->
                    <div class="p-4 rounded-2xl border-2 border-indigo-100 bg-indigo-50/30 space-y-3">
                        <div class="flex items-center justify-between">
                            <h4 class="font-black text-slate-900 flex items-center gap-1.5">
                                <i class="fa-solid fa-credit-card text-indigo-600"></i> 2. بيانات البطاقة البنكية للدفع
                            </h4>
                            <div class="flex items-center gap-2 text-lg text-slate-500">
                                <i class="fa-brands fa-cc-visa text-blue-700"></i>
                                <i class="fa-brands fa-cc-mastercard text-amber-600"></i>
                                <span class="text-[10px] font-black bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded">مدى Mada</span>
                            </div>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div>
                                <label class="font-bold block mb-1">نوع البطاقة</label>
                                <select id="chk-pay-method" class="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white font-bold text-xs">
                                    <option value="بطاقة مدى (Mada)">بطاقة مدى البنكية (Mada)</option>
                                    <option value="بطاقة ائتمانية (Visa)">بطاقة فيزا (Visa)</option>
                                    <option value="بطاقة ائتمانية (MasterCard)">بطاقة ماستركارد (MasterCard)</option>
                                </select>
                            </div>
                            <div>
                                <label class="font-bold block mb-1">الاسم المطبوع على البطاقة <span class="text-red-500">*</span></label>
                                <input type="text" id="chk-card-holder" required placeholder="الاسم كما يظهر على البطاقة" class="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white font-mono text-xs uppercase">
                            </div>
                        </div>

                        <div>
                            <label class="font-bold block mb-1">رقم البطاقة البنكية (16 رقماً) <span class="text-red-500">*</span></label>
                            <input type="text" id="chk-card-number" required maxlength="19" placeholder="XXXX XXXX XXXX XXXX" oninput="formatCardNumber(this)"
                                class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white font-mono text-sm tracking-widest font-bold">
                        </div>

                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="font-bold block mb-1">تاريخ الانتهاء (MM/YY) <span class="text-red-500">*</span></label>
                                <input type="text" id="chk-card-exp" required maxlength="5" placeholder="MM/YY" oninput="formatExpiry(this)"
                                    class="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white font-mono text-xs text-center font-bold">
                            </div>
                            <div>
                                <label class="font-bold block mb-1">رمز الأمان (CVV) <span class="text-red-500">*</span></label>
                                <input type="password" id="chk-card-cvv" required maxlength="3" minlength="3" placeholder="CVV"
                                    class="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white font-mono text-xs text-center font-bold">
                            </div>
                        </div>
                    </div>

                    <button type="submit" class="w-full text-white font-black py-3.5 rounded-2xl shadow-lg text-sm transition flex items-center justify-center gap-2" style="background:{c['color']}">
                        <i class="fa-solid fa-lock"></i> تأكيد خصم المبلغ وإصدار الوثيقة فوراً
                    </button>
                </form>
            </div>

            <!-- شاشة الوثيقة المصدرة بعد الإصدار -->
            <div id="chk-success-box" class="hidden text-center space-y-4">
                <div class="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-3xl mx-auto">
                    <i class="fa-solid fa-circle-check"></i>
                </div>
                <div>
                    <span class="bg-emerald-50 text-emerald-700 text-[11px] font-black px-3 py-1 rounded-full">تم الدفع وإصدار الوثيقة بنجاح</span>
                    <h3 class="text-2xl font-black text-slate-900 mt-2">وثيقة تأمين رسمية - {c['name']}</h3>
                </div>
                <div class="bg-slate-50 p-4 rounded-2xl border border-slate-200 text-right text-xs space-y-2">
                    <div class="flex justify-between"><span>رقم الوثيقة الرسمي:</span><strong id="pol-no" class="font-mono text-emerald-700 text-sm"></strong></div>
                    <div class="flex justify-between"><span>اسم المؤمن له:</span><strong id="pol-cust"></strong></div>
                    <div class="flex justify-between"><span>رقم الهوية / الرقم التسلسلي:</span><strong id="pol-ids" class="font-mono"></strong></div>
                    <div class="flex justify-between"><span>البيانات المعتمدة:</span><strong id="pol-risk-info" class="text-indigo-700"></strong></div>
                    <div class="flex justify-between"><span>الباقة والتغطية:</span><strong id="pol-of"></strong></div>
                    <div class="flex justify-between"><span>فترة سريان الوثيقة:</span><strong id="pol-dates" class="font-mono"></strong></div>
                    <div class="flex justify-between"><span>طريقة الدفع والبطاقة:</span><strong id="pol-card" class="font-mono"></strong></div>
                    <div class="flex justify-between border-t border-slate-200 pt-2 text-sm"><span>المبلغ المدفوع (شامل الضريبة):</span><strong id="pol-total" class="font-mono text-emerald-700 font-black"></strong></div>
                </div>
                <div class="flex gap-3">
                    <button onclick="window.print()" class="flex-1 bg-slate-900 text-white font-bold py-3 rounded-xl text-xs"><i class="fa-solid fa-print ml-1"></i> طباعة الوثيقة</button>
                    <button onclick="closeCheckout()" class="flex-1 text-white font-bold py-3 rounded-xl text-xs" style="background:{c['color']}">إغلاق</button>
                </div>
            </div>
        </div>
    </div>

    <footer class="bg-slate-900 text-slate-400 py-8 mt-12 text-center text-xs">
        <span>© 2026 جميع الحقوق محفوظة - {c['name']}</span>
    </footer>

    <script>
        const PROVIDER_ID = "{provider_id}";
        const COMPANY_COLOR = "{c['color']}";
        const ADDON_AR = {{
            agency_repair: "إصلاح وكالة",
            roadside_assistance: "مساعدة على الطريق",
            replacement_car: "سيارة بديلة",
            windshield_cover: "تغطية الزجاج",
            gulf_coverage: "تغطية الخليج"
        }};
        const CITY_AR = {{ riyadh: "الرياض", jeddah: "جدة/مكة", eastern: "الشرقية", other: "مدن أخرى" }};
        const GENDER_AR = {{ male: "ذكر", female: "أنثى" }};
        const ACC_AR = {{ no: "سجل خالٍ من الحوادث", yes: "يوجد حوادث سابقة" }};
        const CARS_AR = {{ single: "سيارة واحدة", multiple: "عدة سيارات" }};

        let companyData = {{ company: {{}}, offers: [], policies: [] }};
        let activeOrder = null;
        let currentCovFilter = 'ALL';
        let adminToken = sessionStorage.getItem('admin_token_' + PROVIDER_ID) || '';
        let isAdminAuthenticated = Boolean(adminToken);

        async function loadCompanyPortal() {{
            const res = await fetch(`/portal/api/company/${{PROVIDER_ID}}`);
            companyData = await res.json();
            applyUrlCustomerParams();
            renderCompanyOffers();
            if (isAdminAuthenticated) await loadAdminCompany();
        }}

        async function adminFetch(url, options = {{}}) {{
            const res = await fetch(url, {{...options, headers: {{...(options.headers || {{}}), Authorization: `Bearer ${{adminToken}}`}}}});
            if (res.status === 401) {{ adminToken = ''; isAdminAuthenticated = false; sessionStorage.removeItem('admin_token_' + PROVIDER_ID); switchView('admin'); }}
            return res;
        }}

        async function loadAdminCompany() {{
            const res = await adminFetch(`/portal/api/admin/company/${{PROVIDER_ID}}`);
            if (res.ok) {{ companyData = await res.json(); populateAdmin(); }}
        }}

        function setCovFilter(cov) {{
            currentCovFilter = cov;
            ['ALL', 'TPL', 'Comprehensive'].forEach(k => {{
                const btn = document.getElementById('cov-btn-' + k);
                btn.className = (k === cov)
                    ? "px-4 py-2 rounded-xl bg-slate-900 text-white"
                    : "px-4 py-2 rounded-xl bg-white border border-slate-200 text-slate-700";
            }});
            renderCompanyOffers();
        }}

        function switchView(v) {{
            const isCust = v === 'customer';
            document.getElementById('view-customer').classList.add('hidden');
            document.getElementById('view-admin-login').classList.add('hidden');
            document.getElementById('view-admin').classList.add('hidden');

            if (isCust) {{
                document.getElementById('view-customer').classList.remove('hidden');
            }} else {{
                if (isAdminAuthenticated) {{
                    document.getElementById('view-admin').classList.remove('hidden');
                }} else {{
                    document.getElementById('view-admin-login').classList.remove('hidden');
                }}
            }}

            const btnC = document.getElementById('btn-view-customer');
            const btnA = document.getElementById('btn-view-admin');
            if (isCust) {{
                btnC.style.background = COMPANY_COLOR;
                btnC.className = "px-5 py-2 rounded-xl text-xs font-black transition text-white shadow";
                btnA.style.background = "transparent";
                btnA.className = "px-5 py-2 rounded-xl text-xs font-black transition text-slate-600";
            }} else {{
                btnA.style.background = COMPANY_COLOR;
                btnA.className = "px-5 py-2 rounded-xl text-xs font-black transition text-white shadow";
                btnC.style.background = "transparent";
                btnC.className = "px-5 py-2 rounded-xl text-xs font-black transition text-slate-600";
            }}
        }}

        async function handleAdminLogin(e) {{
            e.preventDefault();
            const username = document.getElementById('adm-user').value.trim();
            const password = document.getElementById('adm-pass').value;
            const errEl = document.getElementById('login-error-msg');
            errEl.classList.add('hidden');

            const res = await fetch('/portal/api/admin/login', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ provider_id: PROVIDER_ID, username, password }})
            }});

            if (!res.ok) {{
                const err = await res.json();
                errEl.textContent = err.detail || 'بيانات الدخول غير صحيحة';
                errEl.classList.remove('hidden');
                return;
            }}

            const login = await res.json();
            adminToken = login.token;
            isAdminAuthenticated = true;
            sessionStorage.setItem('admin_token_' + PROVIDER_ID, adminToken);
            switchView('admin');
            await loadAdminCompany();
        }}

        async function logoutAdmin() {{
            if (adminToken) await fetch('/portal/api/admin/logout', {{method: 'POST', headers: {{Authorization: `Bearer ${{adminToken}}`}}}});
            isAdminAuthenticated = false;
            adminToken = '';
            sessionStorage.removeItem('admin_token_' + PROVIDER_ID);
            switchView('admin');
        }}

        function formatCardNumber(input) {{
            let digits = input.value.replace(/\\D/g, '').substring(0, 16);
            input.value = digits.replace(/(\\d{{4}})(?=\\d)/g, '$1 ');
        }}

        function formatExpiry(input) {{
            let digits = input.value.replace(/\\D/g, '').substring(0, 4);
            if (digits.length >= 3) {{
                input.value = digits.substring(0, 2) + '/' + digits.substring(2, 4);
            }} else {{
                input.value = digits;
            }}
        }}

        function getTierBadge(baseRate, covType) {{
            if (covType === 'TPL') {{
                if (baseRate <= 450) return '<span class="px-2.5 py-0.5 rounded-md bg-emerald-100 text-emerald-800 text-[10px] font-black">اقتصادي / رخيص</span>';
                if (baseRate <= 580) return '<span class="px-2.5 py-0.5 rounded-md bg-blue-100 text-blue-800 text-[10px] font-black">متوسط / متوازن</span>';
                return '<span class="px-2.5 py-0.5 rounded-md bg-amber-100 text-amber-800 text-[10px] font-black">مميز / بلس</span>';
            }} else {{
                if (baseRate <= 1300) return '<span class="px-2.5 py-0.5 rounded-md bg-emerald-100 text-emerald-800 text-[10px] font-black">شامل اقتصادي / رخيص</span>';
                if (baseRate <= 1850) return '<span class="px-2.5 py-0.5 rounded-md bg-blue-100 text-blue-800 text-[10px] font-black">شامل متوسط / متوازن</span>';
                return '<span class="px-2.5 py-0.5 rounded-md bg-purple-100 text-purple-800 text-[10px] font-black">شامل فاخر / VIP</span>';
            }}
        }}

        function calcOfferPrice(offer) {{
            const r = companyData.company;
            const age = parseInt(document.getElementById('c-age').value) || 30;
            const city = document.getElementById('c-city').value;
            const gender = document.getElementById('c-gender').value;
            const acc = document.getElementById('c-acc').value;
            const cars = document.getElementById('c-cars').value;

            let base = parseFloat(offer.BasePremiumRate) || (offer.CoverageType === 'TPL' ? r.tpl_base : r.comp_base);
            if (base < 100) base = offer.CoverageType === 'TPL' ? r.tpl_base : r.comp_base;

            const ageMult = age < 25 ? 1.35 : (age < 30 || age >= 60) ? 1.10 : 1.0;
            const cityMult = (city === 'riyadh' || city === 'jeddah' || city === 'eastern') ? r.city_major_mult : r.city_other_mult;
            const genderMult = (gender === 'female') ? r.gender_female_mult : r.gender_male_mult;
            const accMult = (acc === 'yes') ? r.has_accidents_mult : r.no_accidents_mult;
            const carsMult = (cars === 'multiple') ? r.multi_car_mult : r.single_car_mult;

            return Math.round(base * ageMult * cityMult * genderMult * accMult * carsMult);
        }}

        function renderCompanyOffers() {{
            const grid = document.getElementById('company-offers-grid');
            const r = companyData.company;
            grid.innerHTML = '';

            const addonsBadges = (r.addons || []).map(a => `<span class="bg-slate-100 text-slate-700 px-2 py-0.5 rounded-lg text-[10px] font-bold">✓ ${{ADDON_AR[a] || a}}</span>`).join('');

            const filteredOffers = (companyData.offers || []).filter(o => currentCovFilter === 'ALL' || o.CoverageType === currentCovFilter);

            filteredOffers.forEach(o => {{
                const price = calcOfferPrice(o);
                const tierBadge = getTierBadge(parseFloat(o.BasePremiumRate), o.CoverageType);
                grid.innerHTML += `
                    <div class="bg-white rounded-3xl p-6 border border-slate-200 shadow-sm hover:shadow-md transition flex flex-col justify-between">
                        <div>
                            <div class="flex items-center justify-between gap-2 mb-2">
                                ${{tierBadge}}
                                <span class="px-2.5 py-0.5 rounded-full text-[11px] font-black ${{o.CoverageType === 'Comprehensive' ? 'bg-indigo-50 text-indigo-700' : 'bg-emerald-50 text-emerald-700'}}">
                                    ${{o.CoverageType === 'Comprehensive' ? 'تأمين شامل' : 'ضد الغير (TPL)'}}
                                </span>
                            </div>
                            <h4 class="text-base font-black text-slate-900 mb-2">${{o.OfferName}}</h4>
                            <p class="text-xs text-slate-600 mb-4 leading-relaxed">${{o.Description || 'وثيقة تأمين معتمدة من الشركة.'}}</p>
                            <div class="flex flex-wrap gap-1 mb-4">${{addonsBadges}}</div>
                        </div>
                        <div class="flex items-center justify-between pt-4 border-t border-slate-100">
                            <div>
                                <span class="text-[10px] text-slate-400 block font-bold">السعر السنوي المحسوب</span>
                                <span class="text-2xl font-black text-slate-900 font-mono">${{price}} <small class="text-xs">ر.س</small></span>
                                <span class="text-[10px] text-slate-400 block">السعر الأساسي: ${{o.BasePremiumRate}} ر.س</span>
                            </div>
                            <button onclick="openCheckout('${{o.OfferName.replace(/'/g, "")}}', '${{o.CoverageType}}', ${{price}})"
                                    class="px-5 py-3 rounded-2xl text-white font-black text-xs shadow-lg transition hover:opacity-95"
                                    style="background:${{COMPANY_COLOR}}">
                                اختيار وشراء <i class="fa-solid fa-cart-shopping mr-1"></i>
                            </button>
                        </div>
                    </div>
                `;
            }});
        }}

        function applyUrlCustomerParams() {{
            const p = new URLSearchParams(window.location.search);
            if (!p.has('selected_offer') && !p.has('national_id')) return;

            if (p.get('national_id')) document.getElementById('c-id').value = p.get('national_id');
            if (p.get('serial')) document.getElementById('c-serial').value = p.get('serial');
            if (p.get('age')) document.getElementById('c-age').value = p.get('age');
            if (p.get('city')) document.getElementById('c-city').value = p.get('city');
            if (p.get('gender')) document.getElementById('c-gender').value = p.get('gender');
            if (p.get('accidents')) document.getElementById('c-acc').value = p.get('accidents');
            if (p.get('cars')) document.getElementById('c-cars').value = p.get('cars');

            if (p.get('selected_offer') === '1') {{
                const cov = p.get('coverage') || 'TPL';
                const prem = parseFloat(p.get('premium')) || 500;
                const matchedOffer = (companyData.offers || []).find(o => o.CoverageType === cov) || (companyData.offers || [])[0];
                const offerTitle = matchedOffer ? matchedOffer.OfferName : (cov === 'Comprehensive' ? 'وثيقة التأمين الشامل' : 'وثيقة التأمين ضد الغير');

                const banner = document.getElementById('recommended-offer-banner');
                banner.classList.remove('hidden');
                document.getElementById('rec-banner-title').textContent = offerTitle;
                document.getElementById('rec-banner-details').textContent =
                    `التغطية: ${{cov === 'Comprehensive' ? 'تأمين شامل' : 'ضد الغير (TPL)'}} | رقم الهوية: ${{document.getElementById('c-id').value}} | المركبة: ${{document.getElementById('c-serial').value}} | المدينة: ${{CITY_AR[document.getElementById('c-city').value] || ''}}`;
                document.getElementById('rec-banner-price').textContent = prem + ' ر.س';
                document.getElementById('rec-banner-buy-btn').onclick = () => openCheckout(offerTitle, cov, prem);
            }}
        }}

        function populateAdmin() {{
            const r = companyData.company;
            document.getElementById('pr-tpl').value = r.tpl_base;
            document.getElementById('pr-comp').value = r.comp_base;
            document.getElementById('pr-ded').value = r.deductible;
            document.getElementById('pr-city-major').value = r.city_major_mult;
            document.getElementById('pr-city-other').value = r.city_other_mult;
            document.getElementById('pr-gender-m').value = r.gender_male_mult;
            document.getElementById('pr-gender-f').value = r.gender_female_mult;
            document.getElementById('pr-acc-no').value = r.no_accidents_mult;
            document.getElementById('pr-acc-yes').value = r.has_accidents_mult;
            document.getElementById('pr-car-single').value = r.single_car_mult;
            document.getElementById('pr-car-multi').value = r.multi_car_mult;

            document.querySelectorAll('input[name="adm-addon"]').forEach(cb => {{
                cb.checked = (r.addons || []).includes(cb.value);
            }});

            document.getElementById('adm-offers-list').innerHTML = (companyData.offers || []).map(o => `
                <div class="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
                    <div>
                        <strong class="block text-slate-900">${{o.OfferName}}</strong>
                        <span class="text-slate-500">${{o.CoverageType === 'TPL' ? 'ضد الغير' : 'شامل'}} | السعر الأساسي: ${{o.BasePremiumRate}} ر.س</span>
                    </div>
                    <button onclick="deleteOffer(${{o.OfferId}})" class="text-red-500 hover:bg-red-50 p-1.5 rounded"><i class="fa-solid fa-trash"></i></button>
                </div>
            `).join('');

            document.getElementById('adm-policies-list').innerHTML = (companyData.policies || []).map(pol => `
                <div class="p-3 rounded-xl bg-slate-50 border border-slate-200">
                    <div class="flex justify-between font-bold"><span class="font-mono text-emerald-700">${{pol.PolicyNumber}}</span><span>${{pol.TotalAmount}} ر.س</span></div>
                    <div class="text-slate-600 mt-0.5">${{pol.CustomerName}} | الهوية: ${{pol.NationalId}}</div>
                    <div class="text-slate-400 text-[11px]">${{pol.OfferName}} | بطاقة ****${{pol.CardLast4 || '0000'}}</div>
                </div>
            `).join('') || '<p class="text-slate-400">لا توجد وثائق مصدرة بعد.</p>';
        }}

        async function savePricing(e) {{
            e.preventDefault();
            const addons = Array.from(document.querySelectorAll('input[name="adm-addon"]:checked')).map(c => c.value);
            const body = {{
                tpl_base: parseFloat(document.getElementById('pr-tpl').value),
                comp_base: parseFloat(document.getElementById('pr-comp').value),
                deductible: parseFloat(document.getElementById('pr-ded').value),
                city_major_mult: parseFloat(document.getElementById('pr-city-major').value),
                city_other_mult: parseFloat(document.getElementById('pr-city-other').value),
                gender_male_mult: parseFloat(document.getElementById('pr-gender-m').value),
                gender_female_mult: parseFloat(document.getElementById('pr-gender-f').value),
                no_accidents_mult: parseFloat(document.getElementById('pr-acc-no').value),
                has_accidents_mult: parseFloat(document.getElementById('pr-acc-yes').value),
                single_car_mult: parseFloat(document.getElementById('pr-car-single').value),
                multi_car_mult: parseFloat(document.getElementById('pr-car-multi').value),
                addons
            }};
            const res = await fetch(`/portal/api/pricing/${{PROVIDER_ID}}`, {{
                method: 'PUT',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body)
            }});
            const data = await res.json();
            const msg = document.getElementById('adm-msg');
            msg.textContent = data.message;
            msg.classList.remove('hidden');
            setTimeout(() => msg.classList.add('hidden'), 4000);
            await loadAdminCompany();
        }}

        async function addOffer(e) {{
            e.preventDefault();
            const body = {{
                provider_id: PROVIDER_ID,
                offer_name: document.getElementById('of-name').value,
                coverage_type: document.getElementById('of-cov').value,
                base_premium_rate: parseFloat(document.getElementById('of-rate').value),
                description: document.getElementById('of-desc').value
            }};
            await adminFetch('/portal/api/offers', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body)
            }});
            e.target.reset();
            await loadAdminCompany();
        }}

        async function deleteOffer(id) {{
            await fetch(`/portal/api/offers/${{id}}`, {{ method: 'DELETE' }});
            await loadAdminCompany();
        }}

        function openCheckout(offerName, covType, basePrice) {{
            const totalWithVat = Math.round(basePrice * 1.15);
            const cid = document.getElementById('c-id').value.trim();
            const cserial = document.getElementById('c-serial').value.trim();
            const ccity = document.getElementById('c-city').value;
            const cgender = document.getElementById('c-gender').value;
            const cacc = document.getElementById('c-acc').value;
            const ccars = document.getElementById('c-cars').value;

            activeOrder = {{ offerName, covType, totalWithVat, city: ccity, gender: cgender, has_accidents: cacc, cars_count: ccars }};

            document.getElementById('chk-offer-name').textContent = offerName;
            document.getElementById('chk-cov-name').textContent = covType === 'Comprehensive' ? 'تأمين شامل' : 'ضد الغير (TPL)';
            document.getElementById('chk-linked-profile').textContent =
                `${{CITY_AR[ccity]}} | ${{GENDER_AR[cgender]}} | ${{ACC_AR[cacc]}} | ${{CARS_AR[ccars]}}`;
            document.getElementById('chk-total-amt').textContent = totalWithVat + ' ر.س';

            // تعبئة الهوية والرقم التسلسلي فقط إذا كان المستخدم قد أدخلهما بنفسه
            document.getElementById('chk-cust-id').value = cid;
            document.getElementById('chk-cust-serial').value = cserial;

            document.getElementById('chk-form-box').classList.remove('hidden');
            document.getElementById('chk-success-box').classList.add('hidden');
            document.getElementById('checkout-modal').classList.remove('hidden');
        }}

        function closeCheckout() {{
            document.getElementById('checkout-modal').classList.add('hidden');
        }}

        async function submitPurchase(e) {{
            e.preventDefault();
            const rawCard = document.getElementById('chk-card-number').value.replace(/\\D/g, '');
            if (rawCard.length < 16) {{
                alert('يرجى إدخال رقم بطاقة بنكية صحيح مكون من 16 رقماً');
                return;
            }}
            const last4 = rawCard.slice(-4);

            const body = {{
                provider_id: PROVIDER_ID,
                offer_name: activeOrder.offerName,
                customer_name: document.getElementById('chk-cust-name').value.trim(),
                national_id: document.getElementById('chk-cust-id').value.trim(),
                phone: document.getElementById('chk-cust-phone').value.trim(),
                vehicle_serial: document.getElementById('chk-cust-serial').value.trim(),
                city: activeOrder.city,
                gender: activeOrder.gender,
                has_accidents: activeOrder.has_accidents,
                cars_count: activeOrder.cars_count,
                coverage_type: activeOrder.covType,
                total_amount: activeOrder.totalWithVat,
                payment_method: document.getElementById('chk-pay-method').value,
                card_last4: last4
            }};
            const res = await fetch('/portal/api/purchase', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body)
            }});
            const data = await res.json();

            document.getElementById('chk-form-box').classList.add('hidden');
            document.getElementById('chk-success-box').classList.remove('hidden');
            document.getElementById('pol-no').textContent = data.policy_number;
            document.getElementById('pol-cust').textContent = `${{data.customer_name}} (${{data.phone}})`;
            document.getElementById('pol-ids').textContent = `هوية: ${{data.national_id}} | مركبة: ${{data.vehicle_serial}}`;
            document.getElementById('pol-risk-info').textContent =
                `${{CITY_AR[data.city]}} - ${{GENDER_AR[data.gender]}} - ${{ACC_AR[data.has_accidents]}} - ${{CARS_AR[data.cars_count]}}`;
            document.getElementById('pol-of').textContent = `${{data.offer_name}} (${{data.coverage_type === 'Comprehensive' ? 'شامل' : 'ضد الغير'}})`;
            document.getElementById('pol-dates').textContent = `من ${{data.issued_at}} إلى ${{data.expires_at}}`;
            document.getElementById('pol-card').textContent = `${{data.payment_method}} - بطاقة تنتهي بـ **** ${{data.card_last4}}`;
            document.getElementById('pol-total').textContent = data.total_amount + ' ر.س';

            const banner = document.getElementById('recommended-offer-banner');
            if (!banner.classList.contains('hidden')) {{
                document.getElementById('rec-banner-title').innerHTML = `<i class="fa-solid fa-circle-check text-emerald-300 ml-1"></i> تم إصدار وثيقتك بنجاح (${{data.policy_number}})`;
            }}
            await loadAdminCompany();
        }}

        loadCompanyPortal();
    </script>
</body>
</html>"""


@app.get("/tawuniya", response_class=HTMLResponse)
def tawuniya_independent_website():
    return _render_independent_company_site("tawuniya")


@app.get("/rajhi", response_class=HTMLResponse)
def rajhi_independent_website():
    return _render_independent_company_site("rajhi")


@app.get("/medgulf", response_class=HTMLResponse)
def medgulf_independent_website():
    return _render_independent_company_site("medgulf")


@app.get("/acig", response_class=HTMLResponse)
def acig_independent_website():
    return _render_independent_company_site("acig")


@app.get("/", response_class=HTMLResponse)
def companies_directory_home():
    cards = ""
    for pid, c in PRICING_RULES.items():
        cards += f"""
        <a href="/{pid}" class="bg-white p-6 rounded-3xl border border-slate-200 shadow-sm hover:shadow-lg transition flex items-center justify-between group">
            <div class="flex items-center gap-4">
                <div class="w-14 h-14 rounded-2xl text-white font-black text-lg flex items-center justify-center shadow" style="background:{c['color']}">{c['badge']}</div>
                <div>
                    <h2 class="text-xl font-black text-slate-900 group-hover:underline">{c['name']}</h2>
                    <p class="text-xs text-slate-500 mt-1">{c['slogan']}</p>
                    <span class="inline-block mt-2 text-[11px] font-bold bg-slate-100 text-slate-700 px-2.5 py-0.5 rounded-lg">باقات متنوعة (اقتصادي / متوسط / VIP)</span>
                </div>
            </div>
            <i class="fa-solid fa-arrow-left text-slate-400 group-hover:text-slate-900 transition"></i>
        </a>
        """
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>شركات التأمين</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>body {{ font-family: 'Tajawal', sans-serif; background-color: #f1f5f9; }}</style>
</head>
<body class="min-h-screen flex items-center justify-center p-6">
    <div class="max-w-4xl w-full space-y-6">
        <div class="text-center">
            <h1 class="text-3xl font-black text-slate-900">المواقع الإلكترونية المستقلة لشركات التأمين</h1>
            <p class="text-slate-600 text-sm mt-2">اختر موقع الشركة للدخول إلى واجهتها المستقلة:</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-5">{cards}</div>
    </div>
</body>
</html>"""