/**
 * Process entry point: construct dependencies and start the HTTP listener.
 */
const { openDb } = require("./db/connection");
const { createApp } = require("./app");

const db = openDb();
const app = createApp({ db });

if (require.main === module) {
  if (!db.prepare("SELECT 1 FROM Users WHERE IsAdmin=1").get()) {
    console.warn(
      "No administrator exists. Run: npm run create-admin -- --username X --email Y",
    );
  }
  const port = Number(process.env.PORT || 3000);
  app.listen(port, () => console.log(`Thiqa Node listening on ${port}`));
}

module.exports = { app, db };
