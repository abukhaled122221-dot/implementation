#!/usr/bin/env node
const bcrypt = require("bcryptjs"),
  { openDb } = require("../db/connection"),
  readline = require("node:readline/promises");
const args = Object.fromEntries(
  process.argv
    .slice(2)
    .reduce(
      (a, x, i, v) => (x.startsWith("--") ? [...a, [x.slice(2), v[i + 1]]] : a),
      [],
    ),
);
(async () => {
  const db = openDb();
  try {
    const username = args.username,
      email = args.email;
    if (!username || !email)
      throw Error(
        "Usage: npm run create-admin -- --username NAME --email EMAIL --password PASSWORD",
      );
    let password = args.password;
    if (!password) {
      const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
      });
      password = await rl.question(
        "Admin password (8+ chars, letter and digit): ",
      );
      rl.close();
    }
    if (
      password.length < 8 ||
      !/[A-Za-z]/.test(password) ||
      !/[0-9]/.test(password)
    )
      throw Error(
        "Password must be at least 8 characters with a letter and digit",
      );
    const info = db
      .prepare(
        "INSERT INTO Users(UserName,Email,PasswordHash,IsAdmin,IsActive) VALUES(?,?,?,1,1)",
      )
      .run(username, email, await bcrypt.hash(password, 10));
    console.log(`Created admin ${username} (UserId ${info.lastInsertRowid}).`);
  } finally {
    db.close();
  }
})().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
