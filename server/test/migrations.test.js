const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { DatabaseSync } = require("node:sqlite");
const root =
  "C:/Users/Hessah/AppData/Local/hermes/profiles/mimo-v2-6-pro/cache/scratch/thiqa";
test("legacy-shaped migration retains profile, vehicle, request, quote, recommendation and explanation rows", (t) => {
  const dir = fs.mkdtempSync(path.join(root, "legacy-shape-"));
  const dbPath = path.join(dir, "legacy.sqlite");
  const legacy = new DatabaseSync(dbPath);
  legacy.exec(`
    CREATE TABLE Users(UserId INTEGER PRIMARY KEY,UserName TEXT,Email TEXT,PasswordHash TEXT,IsAdmin INTEGER,
      CreatedAt TEXT);
    CREATE TABLE Customer_Profiles(ProfileId INTEGER PRIMARY KEY,UserId INTEGER,NationalId TEXT,BirthDate TEXT);
    CREATE TABLE Vehicles(VehicleId INTEGER PRIMARY KEY,ProfileId INTEGER,VehicleSerial TEXT,
      MakeModelYear TEXT,EstimatedValue REAL,PurposeOfUse TEXT);
    CREATE TABLE Insurance_Providers(ProviderId INTEGER PRIMARY KEY,ProviderName TEXT,Website TEXT,LogoUrl TEXT);
    CREATE TABLE Quote_Requests(RequestId INTEGER PRIMARY KEY,ProfileId INTEGER,VehicleId INTEGER,
      CoverageType TEXT,RequestedAddOns TEXT,Timestamp TEXT);
    CREATE TABLE Retrieved_Quotes(QuoteId INTEGER PRIMARY KEY,RequestId INTEGER,ProviderId INTEGER,
      Premium REAL,CoverageType TEXT,Deductible REAL,AddOns TEXT,PlanName TEXT,Rank INTEGER);
    CREATE TABLE Recommendations(RecId INTEGER PRIMARY KEY,RequestId INTEGER,QuoteId INTEGER,
      SuitabilityScore REAL,CreatedAt TEXT);
    CREATE TABLE Explanations(ExplanationId INTEGER PRIMARY KEY,RecId INTEGER,MainReasons TEXT,
      CriteriaBreakdown TEXT,ComparisonText TEXT);
    INSERT INTO Users VALUES(91,'legacyrow','legacyrow@example.test','hash-preserved',0,'2020-01-01');
    INSERT INTO Customer_Profiles VALUES(71,91,'1098765432','1990-01-01');
    INSERT INTO Vehicles VALUES(61,71,'SERIAL123','2020',50000,'personal');
    INSERT INTO Insurance_Providers VALUES(41,'Legacy Provider','','');
    INSERT INTO Quote_Requests VALUES(51,71,61,'TPL','[]','2020-01-02');
    INSERT INTO Retrieved_Quotes VALUES(31,51,41,1000,'TPL',500,'[]','Legacy Plan',1);
    INSERT INTO Recommendations VALUES(21,51,31,0.7,'2020-01-03');
    INSERT INTO Explanations VALUES(11,21,'reason','{}','comparison');
  `);
  legacy.close();
  const prior = process.env.THIQA_DB_PATH;
  process.env.THIQA_DB_PATH = dbPath;
  const { openDb } = require("../db/connection");
  const migrated = openDb();
  for (const table of [
    "Customer_Profiles",
    "Vehicles",
    "Quote_Requests",
    "Retrieved_Quotes",
    "Recommendations",
    "Explanations",
  ])
    assert.equal(
      migrated.prepare(`SELECT count(*) n FROM ${table}`).get().n,
      1,
      table,
    );
  assert.equal(
    migrated
      .prepare("SELECT DateOfBirth FROM Customer_Profiles WHERE ProfileId=71")
      .get().DateOfBirth,
    "1990-01-01",
  );
  assert.equal(
    migrated
      .prepare("SELECT SerialNumber FROM Vehicles WHERE VehicleId=61")
      .get().SerialNumber,
    "SERIAL123",
  );
  assert.equal(
    migrated
      .prepare("SELECT SelectedQuoteId FROM Recommendations WHERE RecId=21")
      .get().SelectedQuoteId,
    31,
  );
  assert.equal(
    migrated.prepare("SELECT ExplId FROM Explanations WHERE ExplId=11").get()
      .ExplId,
    11,
  );
  migrated.close();
  process.env.THIQA_DB_PATH = prior;
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
});

test("migration is repeatable on the archived database without changing company/policy rows", (t) => {
  const source = path.join(root, "imp/database/thiqa.db.orig");
  assert.ok(fs.existsSync(source));
  const dir = fs.mkdtempSync(path.join(root, "migration-"));
  const copy = path.join(dir, "copy.db");
  fs.copyFileSync(source, copy);
  const tableCounts = (db) =>
    Object.fromEntries(
      ["Company_Offers", "Company_Pricing_Rules", "Issued_Policies"].map(
        (table) => [
          table,
          db.prepare(`SELECT count(*) n FROM ${table}`).get().n,
        ],
      ),
    );
  const beforeDb = new DatabaseSync(copy);
  const beforeCounts = tableCounts(beforeDb);
  beforeDb.close();
  const prior = process.env.THIQA_DB_PATH;
  process.env.THIQA_DB_PATH = copy;
  const { openDb } = require("../db/connection");
  let db = openDb();
  const users = db
    .prepare("SELECT UserId,PasswordHash FROM Users ORDER BY UserId")
    .all();
  assert.equal(users.length, 9);
  assert.ok(users.every((u) => u.PasswordHash));
  assert.deepEqual(tableCounts(db), beforeCounts);
  db.close();
  db = openDb();
  assert.equal(db.prepare("SELECT count(*) n FROM Users").get().n, 9);
  assert.deepEqual(
    db.prepare("SELECT UserId,PasswordHash FROM Users ORDER BY UserId").all(),
    users,
  );
  assert.deepEqual(tableCounts(db), beforeCounts);
  db.close();
  process.env.THIQA_DB_PATH = prior;
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
});
