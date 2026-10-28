const fs = require("node:fs");
const path = require("node:path");

const schemaPath = path.resolve(__dirname, "../../database/schema.sqlite.sql");

/** Rebuild incompatible tables by copying shared columns instead of discarding customer data. */
function migrate(db) {
  // نزيل تعليقات SQL (-- ...) أولاً حتى يبقى الملف موثقاً ومقروءاً للتقرير دون أن يؤثر على التحليل
  const schema = fs
    .readFileSync(schemaPath, "utf8")
    .split(/\r?\n/)
    .map((line) => line.replace(/--.*$/, ""))
    .join("\n");
  const statements = schema
    .split(";")
    .map((sql) => sql.trim())
    .filter(Boolean);
  const createTables = statements.filter((sql) =>
    /^CREATE TABLE IF NOT EXISTS/i.test(sql),
  );
  const indexes = statements.filter((sql) =>
    /^CREATE INDEX IF NOT EXISTS/i.test(sql),
  );
  const tableNames = createTables.map((sql) => sql.match(/EXISTS\s+(\w+)/i)[1]);

  db.exec("PRAGMA foreign_keys=OFF");
  db.exec(
    "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT " +
      "NULL DEFAULT(datetime('now')))",
  );
  const applied = db
    .prepare("SELECT 1 FROM schema_migrations WHERE version=1")
    .get();
  if (!applied) {
    db.exec("BEGIN");
    try {
      // Create missing tables first so the canonical schema always exists.
      for (const sql of createTables) db.exec(sql);
      for (const table of tableNames) {
        const exists = db
          .prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?")
          .get(table);
        if (!exists) continue;
        const columns = db
          .prepare(`PRAGMA table_info(${table})`)
          .all()
          .map((column) => column.name);
        const createSql = createTables.find((sql) =>
          new RegExp(`EXISTS\\s+${table}\\b`, "i").test(sql),
        );
        const expected = [
          ...createSql.matchAll(
            /(?:^|[,(])\s*(\w+)\s+(?:INTEGER|TEXT|REAL|NUMERIC|BLOB)\b/gi,
          ),
        ].map((match) => match[1]);
        if (expected.every((column) => columns.includes(column))) continue;
        const createNew = createSql.replace(
          new RegExp(`(EXISTS\\s+)${table}\\b`, "i"),
          `$1${table}__new`,
        );
        db.exec(`DROP TABLE IF EXISTS ${table}__new`);
        db.exec(createNew);
        const newColumns = db
          .prepare(`PRAGMA table_info(${table}__new)`)
          .all()
          .map((column) => column.name);
        const mappings = new Map([
          ["ProviderId", ["ProviderId"]],
          ["PasswordHash", ["PasswordHash"]],
        ]);
        const common = newColumns.filter((column) => columns.includes(column));
        const renamed = {
          DateOfBirth: ["DateOfBirth", "BirthDate"],
          MakeModelYear: ["MakeModelYear", "ManufactureYear", "ModelYear"],
          SerialNumber: [
            "SerialNumber",
            "VehicleSerial",
            "VehicleSerialNumber",
          ],
          SelectedQuoteId: ["SelectedQuoteId", "QuoteId"],
          ExplId: ["ExplId", "ExplanationId"],
        };
        const targetColumns = [...common];
        const expressions = common.map((column) => {
          const source = (renamed[column] || [column]).find((candidate) =>
            columns.includes(candidate),
          );
          return column === "ProviderId" ? `CAST(${source} AS TEXT)` : source;
        });
        for (const [target, candidates] of Object.entries(renamed)) {
          if (targetColumns.includes(target)) continue;
          const source = candidates.find((candidate) =>
            columns.includes(candidate),
          );
          if (source && newColumns.includes(target)) {
            targetColumns.push(target);
            expressions.push(
              target === "ProviderId" ? `CAST(${source} AS TEXT)` : source,
            );
          }
        }
        if (targetColumns.length) {
          db.exec(
            `INSERT OR IGNORE INTO ${table}__new ` +
              `(${targetColumns.join(",")}) SELECT ${expressions.join(",")} FROM ${table}`,
          );
        }
        db.exec(`DROP TABLE ${table}`);
        db.exec(`ALTER TABLE ${table}__new RENAME TO ${table}`);
      }
      for (const sql of indexes) db.exec(sql);
      db.prepare("INSERT INTO schema_migrations(version) VALUES(1)").run();
      db.exec("COMMIT");
    } catch (error) {
      db.exec("ROLLBACK");
      throw error;
    }
  }
  // Legacy users need identity/hash preservation while removing only obsolete columns.
  const userColumns = db
    .prepare("PRAGMA table_info(Users)")
    .all()
    .map((column) => column.name);
  if (!userColumns.includes("IsActive"))
    db.exec("ALTER TABLE Users ADD COLUMN IsActive INTEGER NOT NULL DEFAULT 1");
  if (!userColumns.includes("LastLoginAt"))
    db.exec("ALTER TABLE Users ADD COLUMN LastLoginAt TEXT");
  db.exec("PRAGMA foreign_key_check");
  db.exec("PRAGMA foreign_keys=ON");
  db.exec("PRAGMA user_version=1");
}

module.exports = { migrate };
