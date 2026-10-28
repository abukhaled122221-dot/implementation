function writeAudit(db, user, action, targetType, targetId, details = {}) {
  db.prepare(
    "INSERT INTO Audit_Log(AdminUserId,Action,EntityType,EntityId,Details) VALUES(?,?,?,?,?)",
  ).run(
    user.UserId,
    action,
    targetType,
    String(targetId),
    JSON.stringify(details),
  );
}
module.exports = { writeAudit };
