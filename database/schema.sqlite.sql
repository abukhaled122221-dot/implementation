-- =====================================================================
-- THIQA — مخطط قاعدة البيانات (SQLite)
-- المصدر الوحيد لبنية قاعدة بيانات موقع ثقة. يُطبَّق تلقائياً عند تشغيل
-- السيرفر (server/db/migrations.js) مع ترحيل آمن يحافظ على البيانات.
-- النسخة المكافئة لـ MySQL (للتقرير): database/thiqa_database.sql
-- ملاحظة: لا تضع فاصلة منقوطة داخل التعليقات (يُقسَّم الملف عليها).
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- 1) المستخدمون (العملاء والمسؤولون). IsAdmin يفصل مكوّن الأدمن عن العميل
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Users (
    UserId        INTEGER PRIMARY KEY AUTOINCREMENT,
    UserName      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    Email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    PasswordHash  TEXT    NOT NULL,                       -- bcrypt (cost 10)
    IsAdmin       INTEGER NOT NULL DEFAULT 0,
    CreatedAt     TEXT    NOT NULL DEFAULT (datetime('now')),
    IsActive      INTEGER NOT NULL DEFAULT 1,             -- الأدمن يستطيع تعطيل الحساب
    LastLoginAt   TEXT
);

-- ---------------------------------------------------------------------
-- 2) ملف العميل (واحد لكل مستخدم، يُحدَّث مع كل طلب توصية)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Customer_Profiles (
    ProfileId        INTEGER PRIMARY KEY AUTOINCREMENT,
    UserId           INTEGER NOT NULL UNIQUE REFERENCES Users(UserId) ON DELETE CASCADE,
    FullName         TEXT,
    NationalId       TEXT,
    DateOfBirth      TEXT,
    DriverLicenseNo  TEXT,
    UpdatedAt        TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- 3) المركبات (مركبة واحدة لكل رقم تسلسلي لكل عميل)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Vehicles (
    VehicleId       INTEGER PRIMARY KEY AUTOINCREMENT,
    ProfileId       INTEGER NOT NULL REFERENCES Customer_Profiles(ProfileId) ON DELETE CASCADE,
    SerialNumber    TEXT    NOT NULL,
    MakeModelYear   TEXT,
    EstimatedValue  REAL,
    PurposeOfUse    TEXT,
    UNIQUE (ProfileId, SerialNumber)
);

-- ---------------------------------------------------------------------
-- 4) شركات التأمين + بياناتها التعريفية التي يستخدمها Agent 2 في التقييم
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Insurance_Providers (
    ProviderId       TEXT    PRIMARY KEY,                 -- مثال: tawuniya
    ProviderName     TEXT    NOT NULL,
    LogoUrl          TEXT,
    Website          TEXT,
    IsActive         INTEGER NOT NULL DEFAULT 1,          -- المعطّلة لا تُستعلم
    Reliability      REAL,                                -- 0..1 (معيار الموثوقية)
    WorkshopNetwork  TEXT,                                -- واسع جداً / متوسط / محدود
    DigitalScore     REAL                                 -- 0..1 (التجربة الرقمية)
);

-- ---------------------------------------------------------------------
-- 5) إعدادات الاتصال بـ API كل شركة (يقرؤها Agent 1 مع كل طلب)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS API_Settings (
    SettingId   INTEGER PRIMARY KEY AUTOINCREMENT,
    ProviderId  TEXT    NOT NULL UNIQUE REFERENCES Insurance_Providers(ProviderId) ON DELETE CASCADE,
    Endpoint    TEXT    NOT NULL,                         -- رابط كامل
    AuthKey     TEXT,                                     -- لا يُعاد للواجهة أبداً
    AuthScheme  TEXT    NOT NULL DEFAULT 'x-api-key' CHECK (AuthScheme IN ('x-api-key', 'bearer')),
    Adapter     TEXT    NOT NULL,                         -- صيغة طلب/رد الشركة
    Protocol    TEXT    NOT NULL DEFAULT 'REST/JSON',
    Timeout     INTEGER NOT NULL DEFAULT 5 CHECK (Timeout BETWEEN 1 AND 30)
);

-- ---------------------------------------------------------------------
-- 6) طلبات التوصية (الناجحة والفاشلة) — سجل التدقيق المطلوب في التقرير
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Quote_Requests (
    RequestId        INTEGER PRIMARY KEY AUTOINCREMENT,
    ProfileId        INTEGER NOT NULL REFERENCES Customer_Profiles(ProfileId),
    VehicleId        INTEGER REFERENCES Vehicles(VehicleId),
    CoverageType     TEXT,
    RequestedAddOns  TEXT,                                -- JSON
    Timestamp        TEXT    NOT NULL DEFAULT (datetime('now')),
    Status           TEXT    NOT NULL DEFAULT 'success',  -- success / failed
    ErrorMessage     TEXT,
    Priority         TEXT,
    ProviderStatus   TEXT,                                -- JSON: حالة كل شركة
    RequestPayload   TEXT                                 -- JSON: بيانات الطلب كما أُرسلت
);

-- ---------------------------------------------------------------------
-- 7) العروض المسترجعة من الشركات (كل عرض مع ترتيبه ودرجته)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Retrieved_Quotes (
    QuoteId           INTEGER PRIMARY KEY AUTOINCREMENT,
    RequestId         INTEGER NOT NULL REFERENCES Quote_Requests(RequestId) ON DELETE CASCADE,
    ProviderId        TEXT    NOT NULL REFERENCES Insurance_Providers(ProviderId),
    Premium           REAL,
    CoverageType      TEXT,
    Deductible        REAL,
    AddOns            TEXT,                               -- JSON
    PlanName          TEXT,
    ExternalQuoteId   TEXT,
    SuitabilityScore  REAL,
    Rank              INTEGER,
    QuoteData         TEXT                                -- JSON: العرض كاملاً مع تفصيل الدرجات
);

-- ---------------------------------------------------------------------
-- 8) التوصية النهائية (العرض المختار من Agent 2)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Recommendations (
    RecId             INTEGER PRIMARY KEY AUTOINCREMENT,
    RequestId         INTEGER NOT NULL UNIQUE REFERENCES Quote_Requests(RequestId) ON DELETE CASCADE,
    SelectedQuoteId   INTEGER REFERENCES Retrieved_Quotes(QuoteId),
    SuitabilityScore  REAL,
    CreatedAt         TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- 9) التفسير (مخرجات Agent 3)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Explanations (
    ExplId             INTEGER PRIMARY KEY AUTOINCREMENT,
    RecId              INTEGER NOT NULL UNIQUE REFERENCES Recommendations(RecId) ON DELETE CASCADE,
    MainReasons        TEXT,
    CriteriaBreakdown  TEXT,                              -- JSON
    ComparisonText     TEXT
);

-- ---------------------------------------------------------------------
-- 10) جلسات الدخول (التوكن يُخزَّن مشفّراً SHA-256 وليس كنص)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Sessions (
    SessionId     INTEGER PRIMARY KEY AUTOINCREMENT,
    UserId        INTEGER NOT NULL REFERENCES Users(UserId) ON DELETE CASCADE,
    TokenHash     TEXT    NOT NULL UNIQUE,
    CreatedAt     INTEGER NOT NULL,                       -- epoch seconds
    LastSeenAt    INTEGER NOT NULL,
    ExpiresAt     INTEGER NOT NULL,                       -- انتهاء بعد الخمول (8 ساعات)
    MaxExpiresAt  INTEGER NOT NULL,                       -- حد أقصى مطلق (7 أيام)
    Kind          TEXT    NOT NULL DEFAULT 'customer'     -- customer / admin
);

-- ---------------------------------------------------------------------
-- 11) سجل عمليات المسؤولين (كل تعديل من لوحة التحكم)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Audit_Log (
    AuditId      INTEGER PRIMARY KEY AUTOINCREMENT,
    AdminUserId  INTEGER REFERENCES Users(UserId),
    Action       TEXT    NOT NULL,
    EntityType   TEXT,
    EntityId     TEXT,
    Details      TEXT,                                    -- JSON
    CreatedAt    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- الفهارس (لسرعة السجل والصفحات)
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_sessions_expiry        ON Sessions(ExpiresAt);
CREATE INDEX IF NOT EXISTS idx_requests_profile_time  ON Quote_Requests(ProfileId, Timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_quotes_request_rank    ON Retrieved_Quotes(RequestId, Rank);
CREATE INDEX IF NOT EXISTS idx_audit_time             ON Audit_Log(CreatedAt DESC);
