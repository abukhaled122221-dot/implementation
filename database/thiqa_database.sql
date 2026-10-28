-- =====================================================================
-- THIQA — المخطط المنطقي لقاعدة البيانات (MySQL 8) — مرجع التقرير
-- مطابق منطقياً لملف database/schema.sqlite.sql المستخدم فعلياً في النظام.
-- معرّفات الشركات نصية (مثل tawuniya) لتتوافق مع خدمة الوكلاء.
-- =====================================================================

-- 1) المستخدمون
CREATE TABLE Users (
    UserId        BIGINT       AUTO_INCREMENT PRIMARY KEY,
    UserName      VARCHAR(30)  NOT NULL UNIQUE,
    Email         VARCHAR(254) NOT NULL UNIQUE,
    PasswordHash  VARCHAR(255) NOT NULL,
    IsAdmin       BOOLEAN      NOT NULL DEFAULT FALSE,
    IsActive      BOOLEAN      NOT NULL DEFAULT TRUE,
    CreatedAt     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    LastLoginAt   TIMESTAMP    NULL
);

-- 2) ملف العميل
CREATE TABLE Customer_Profiles (
    ProfileId        BIGINT       AUTO_INCREMENT PRIMARY KEY,
    UserId           BIGINT       NOT NULL UNIQUE,
    FullName         VARCHAR(100),
    NationalId       VARCHAR(20),
    DateOfBirth      DATE,
    DriverLicenseNo  VARCHAR(30),
    UpdatedAt        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (UserId) REFERENCES Users(UserId) ON DELETE CASCADE
);

-- 3) المركبات
CREATE TABLE Vehicles (
    VehicleId       BIGINT        AUTO_INCREMENT PRIMARY KEY,
    ProfileId       BIGINT        NOT NULL,
    SerialNumber    VARCHAR(40)   NOT NULL,
    MakeModelYear   VARCHAR(80),
    EstimatedValue  DECIMAL(12,2),
    PurposeOfUse    VARCHAR(40),
    UNIQUE (ProfileId, SerialNumber),
    FOREIGN KEY (ProfileId) REFERENCES Customer_Profiles(ProfileId) ON DELETE CASCADE
);

-- 4) شركات التأمين
CREATE TABLE Insurance_Providers (
    ProviderId       VARCHAR(40)  PRIMARY KEY,
    ProviderName     VARCHAR(150) NOT NULL,
    LogoUrl          VARCHAR(500),
    Website          VARCHAR(500),
    IsActive         BOOLEAN      NOT NULL DEFAULT TRUE,
    Reliability      DECIMAL(4,3),
    WorkshopNetwork  VARCHAR(30),
    DigitalScore     DECIMAL(4,3)
);

-- 5) إعدادات الاتصال بـ API
CREATE TABLE API_Settings (
    SettingId   BIGINT        AUTO_INCREMENT PRIMARY KEY,
    ProviderId  VARCHAR(40)   NOT NULL UNIQUE,
    Endpoint    VARCHAR(1000) NOT NULL,
    AuthKey     TEXT          NULL,
    AuthScheme  VARCHAR(20)   NOT NULL DEFAULT 'x-api-key',
    Adapter     VARCHAR(30)   NOT NULL,
    Protocol    VARCHAR(30)   NOT NULL DEFAULT 'REST/JSON',
    Timeout     INT           NOT NULL DEFAULT 5,
    CHECK (AuthScheme IN ('x-api-key', 'bearer')),
    CHECK (Timeout BETWEEN 1 AND 30),
    FOREIGN KEY (ProviderId) REFERENCES Insurance_Providers(ProviderId) ON DELETE CASCADE
);

-- 6) طلبات التوصية
CREATE TABLE Quote_Requests (
    RequestId        BIGINT      AUTO_INCREMENT PRIMARY KEY,
    ProfileId        BIGINT      NOT NULL,
    VehicleId        BIGINT      NULL,
    CoverageType     VARCHAR(30),
    RequestedAddOns  JSON,
    Timestamp        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Status           VARCHAR(20) NOT NULL DEFAULT 'success',
    ErrorMessage     TEXT,
    Priority         VARCHAR(20),
    ProviderStatus   JSON,
    RequestPayload   JSON,
    FOREIGN KEY (ProfileId) REFERENCES Customer_Profiles(ProfileId),
    FOREIGN KEY (VehicleId) REFERENCES Vehicles(VehicleId)
);

-- 7) العروض المسترجعة
CREATE TABLE Retrieved_Quotes (
    QuoteId           BIGINT        AUTO_INCREMENT PRIMARY KEY,
    RequestId         BIGINT        NOT NULL,
    ProviderId        VARCHAR(40)   NOT NULL,
    Premium           DECIMAL(12,2),
    CoverageType      VARCHAR(30),
    Deductible        DECIMAL(12,2),
    AddOns            JSON,
    PlanName          VARCHAR(255),
    ExternalQuoteId   VARCHAR(100),
    SuitabilityScore  DECIMAL(8,5),
    `Rank`            INT,
    QuoteData         JSON,
    FOREIGN KEY (RequestId)  REFERENCES Quote_Requests(RequestId) ON DELETE CASCADE,
    FOREIGN KEY (ProviderId) REFERENCES Insurance_Providers(ProviderId)
);

-- 8) التوصيات
CREATE TABLE Recommendations (
    RecId             BIGINT       AUTO_INCREMENT PRIMARY KEY,
    RequestId         BIGINT       NOT NULL UNIQUE,
    SelectedQuoteId   BIGINT       NULL,
    SuitabilityScore  DECIMAL(8,5),
    CreatedAt         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (RequestId)       REFERENCES Quote_Requests(RequestId) ON DELETE CASCADE,
    FOREIGN KEY (SelectedQuoteId) REFERENCES Retrieved_Quotes(QuoteId)
);

-- 9) التفسيرات
CREATE TABLE Explanations (
    ExplId             BIGINT AUTO_INCREMENT PRIMARY KEY,
    RecId              BIGINT NOT NULL UNIQUE,
    MainReasons        TEXT,
    CriteriaBreakdown  JSON,
    ComparisonText     TEXT,
    FOREIGN KEY (RecId) REFERENCES Recommendations(RecId) ON DELETE CASCADE
);

-- 10) جلسات الدخول
CREATE TABLE Sessions (
    SessionId     BIGINT      AUTO_INCREMENT PRIMARY KEY,
    UserId        BIGINT      NOT NULL,
    TokenHash     CHAR(64)    NOT NULL UNIQUE,
    CreatedAt     BIGINT      NOT NULL,
    LastSeenAt    BIGINT      NOT NULL,
    ExpiresAt     BIGINT      NOT NULL,
    MaxExpiresAt  BIGINT      NOT NULL,
    Kind          VARCHAR(20) NOT NULL DEFAULT 'customer',
    FOREIGN KEY (UserId) REFERENCES Users(UserId) ON DELETE CASCADE
);

-- 11) سجل عمليات المسؤولين
CREATE TABLE Audit_Log (
    AuditId      BIGINT       AUTO_INCREMENT PRIMARY KEY,
    AdminUserId  BIGINT       NULL,
    Action       VARCHAR(100) NOT NULL,
    EntityType   VARCHAR(50),
    EntityId     VARCHAR(100),
    Details      JSON,
    CreatedAt    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (AdminUserId) REFERENCES Users(UserId)
);

-- الفهارس
CREATE INDEX idx_requests_profile_time ON Quote_Requests(ProfileId, Timestamp);
CREATE INDEX idx_quotes_request_rank   ON Retrieved_Quotes(RequestId, `Rank`);
CREATE INDEX idx_sessions_expiry       ON Sessions(ExpiresAt);
CREATE INDEX idx_audit_time            ON Audit_Log(CreatedAt);
