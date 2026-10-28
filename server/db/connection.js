const fs = require("node:fs");
const path = require("node:path");
const { DatabaseSync } = require("node:sqlite");
const { migrate } = require("./migrations");
const { seed } = require("./seed");

/** Open the configured SQLite file and run safe schema upgrades before serving requests. */
function openDb() {
  const dbPath =
    process.env.THIQA_DB_PATH ||
    path.resolve(__dirname, "../../database/thiqa.db");
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  const db = new DatabaseSync(dbPath);
  db.exec("PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;");
  migrate(db);
  seed(db);
  return db;
}

module.exports = { openDb };
