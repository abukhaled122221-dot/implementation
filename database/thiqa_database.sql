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
    Website VARCHAR(255)
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