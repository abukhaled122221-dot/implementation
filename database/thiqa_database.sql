-- 1. Users
CREATE TABLE Users (
    UserId INT PRIMARY KEY AUTO_INCREMENT,
    UserName VARCHAR(50),
    Email VARCHAR(100),
    PasswordHash VARCHAR(255),
    IsAdmin BOOLEAN,
    CreatedAt DATETIME
);

-- 2. Customer Profiles
CREATE TABLE Customer_Profiles (
    ProfileId INT PRIMARY KEY AUTO_INCREMENT,
    UserId INT NOT NULL,
    FullName VARCHAR(100),
    NationalId VARCHAR(20),
    DateOfBirth DATE,
    DriverLicenseNo VARCHAR(30),

    FOREIGN KEY (UserId)
        REFERENCES Users(UserId)
);

-- 3. Vehicles
CREATE TABLE Vehicles (
    VehicleId INT PRIMARY KEY AUTO_INCREMENT,
    ProfileId INT NOT NULL,
    SerialNumber VARCHAR(40),
    MakeModelYear VARCHAR(80),
    EstimatedValue DECIMAL(10,2),
    PurposeOfUse VARCHAR(40),

    FOREIGN KEY (ProfileId)
        REFERENCES Customer_Profiles(ProfileId)
);

-- 4. Insurance Providers
CREATE TABLE Insurance_Providers (
    ProviderId INT PRIMARY KEY AUTO_INCREMENT,
    ProviderName VARCHAR(100),
    LogoUrl VARCHAR(255),
    Website VARCHAR(255),
    BaseRate FLOAT,
    Reliability FLOAT,
    WorkshopNetwork VARCHAR(100),
    DigitalScore FLOAT
);

-- 5. API Settings
CREATE TABLE API_Settings (
    SettingId INT PRIMARY KEY AUTO_INCREMENT,
    ProviderId INT NOT NULL,
    Endpoint VARCHAR(255),
    AuthKey VARCHAR(255),
    Protocol VARCHAR(40),
    Timeout INT,

    FOREIGN KEY (ProviderId)
        REFERENCES Insurance_Providers(ProviderId)
);

-- 6. Quote Requests
CREATE TABLE Quote_Requests (
    RequestId INT PRIMARY KEY AUTO_INCREMENT,
    ProfileId INT NOT NULL,
    VehicleId INT NOT NULL,
    CoverageType VARCHAR(30),
    RequestedAddOns TEXT,
    Timestamp DATETIME,

    FOREIGN KEY (ProfileId)
        REFERENCES Customer_Profiles(ProfileId),

    FOREIGN KEY (VehicleId)
        REFERENCES Vehicles(VehicleId)
);

-- 7. Retrieved Quotes
CREATE TABLE Retrieved_Quotes (
    QuoteId INT PRIMARY KEY AUTO_INCREMENT,
    RequestId INT NOT NULL,
    ProviderId INT NOT NULL,
    Premium DECIMAL(10,2),
    CoverageType VARCHAR(30),
    Deductible DECIMAL(10,2),
    AddOns TEXT,

    FOREIGN KEY (RequestId)
        REFERENCES Quote_Requests(RequestId),

    FOREIGN KEY (ProviderId)
        REFERENCES Insurance_Providers(ProviderId)
);

-- 8. Recommendations
CREATE TABLE Recommendations (
    RecId INT PRIMARY KEY AUTO_INCREMENT,
    RequestId INT NOT NULL,
    SelectedQuoteId INT NOT NULL,
    SuitabilityScore DECIMAL(5,4),
    CreatedAt DATETIME,

    FOREIGN KEY (RequestId)
        REFERENCES Quote_Requests(RequestId),

    FOREIGN KEY (SelectedQuoteId)
        REFERENCES Retrieved_Quotes(QuoteId),

    UNIQUE (RequestId)
);

-- 9. Explanations
CREATE TABLE Explanations (
    ExplId INT PRIMARY KEY AUTO_INCREMENT,
    RecId INT NOT NULL,
    MainReasons TEXT,
    CriteriaBreakdown TEXT,
    ComparisonText TEXT,

    FOREIGN KEY (RecId)
        REFERENCES Recommendations(RecId),

    UNIQUE (RecId)
);

-- Data for Insurance Providers
INSERT INTO Insurance_Providers (ProviderId, ProviderName, LogoUrl, Website, BaseRate, Reliability, WorkshopNetwork, DigitalScore) VALUES
(1, 'التعاونية للتأمين', '/assets/logos/tawuniya.png', 'https://www.tawuniya.com.sa', 1.00, 0.95, 'واسع جداً', 0.82),
(2, 'الراجحي تكافل', '/assets/logos/rajhi.png', 'https://www.rajhitakaful.com.sa', 1.05, 0.90, 'متوسط', 0.96),
(3, 'ميدغلف للتأمين', '/assets/logos/medgulf.png', 'https://www.medgulf.com.sa', 0.97, 0.85, 'متوسط', 0.88),
(4, 'المجموعة المتحدة للتأمين (ACIG)', '/assets/logos/acig.png', 'https://www.acig.com.sa', 0.89, 0.78, 'محدود', 0.78);

-- Data for API Settings
INSERT INTO API_Settings (SettingId, ProviderId, Endpoint, AuthKey, Protocol, Timeout) VALUES
(1, 1, 'https://api.tawuniya.com.sa/v1/insurance/quotes', 'mock_tawuniya_api_key_2026', 'REST', 30),
(2, 2, 'https://api.rajhitakaful.com.sa/v1/takaful/quotes', 'mock_rajhi_api_key_2026', 'REST', 30),
(3, 3, 'https://api.medgulf.com.sa/v1/insurance/quotes', 'mock_medgulf_api_key_2026', 'REST', 30),
(4, 4, 'https://api.acig.com.sa/v1/insurance/quotes', 'mock_acig_api_key_2026', 'REST', 30);