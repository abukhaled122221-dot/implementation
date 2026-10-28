function transaction(db, fn) {
  db.exec("BEGIN");
  try {
    const value = fn();
    db.exec("COMMIT");
    return value;
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}
function ensureProfile(db, userId, body) {
  const row = db
    .prepare("SELECT ProfileId FROM Customer_Profiles WHERE UserId=?")
    .get(userId);
  if (row) {
    db.prepare(
      "UPDATE Customer_Profiles SET NationalId=?,DateOfBirth=?,UpdatedAt=datetime('now') WHERE ProfileId=?",
    ).run(body.national_id, body.birth_date, row.ProfileId);
    return row.ProfileId;
  }
  return Number(
    db
      .prepare(
        "INSERT INTO Customer_Profiles(UserId,NationalId,DateOfBirth) VALUES(?,?,?)",
      )
      .run(userId, body.national_id, body.birth_date).lastInsertRowid,
  );
}
function ensureVehicle(db, profileId, body) {
  const row = db
    .prepare(
      "SELECT VehicleId FROM Vehicles WHERE ProfileId=? AND SerialNumber=?",
    )
    .get(profileId, body.vehicle_serial);
  if (row) {
    db.prepare(
      "UPDATE Vehicles SET MakeModelYear=?,EstimatedValue=?,PurposeOfUse=? WHERE VehicleId=?",
    ).run(
      String(body.manufacture_year),
      body.vehicle_value,
      body.purpose_of_use,
      row.VehicleId,
    );
    return row.VehicleId;
  }
  return Number(
    db
      .prepare(
        "INSERT INTO Vehicles(ProfileId,SerialNumber,MakeModelYear,EstimatedValue,PurposeOfUse) VALUES(?,?,?,?,?)",
      )
      .run(
        profileId,
        body.vehicle_serial,
        String(body.manufacture_year),
        body.vehicle_value,
        body.purpose_of_use,
      ).lastInsertRowid,
  );
}
function persistRecommendation(db, requestId, data) {
  let selected;
  for (const [i, offer] of (data.all_offers_ranked || []).entries()) {
    const providerId = String(offer.provider_id || "unknown");
    db.prepare(
      "INSERT OR IGNORE INTO Insurance_Providers(ProviderId,ProviderName) VALUES(?,?)",
    ).run(providerId, offer.provider_name || providerId);
    const quoteId = Number(
      db
        .prepare(
          "INSERT INTO " +
            "Retrieved_Quotes(RequestId,ProviderId,Premium,CoverageType,Deductible," +
            "AddOns,PlanName,ExternalQuoteId,SuitabilityScore,Rank,QuoteData) " +
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        )
        .run(
          requestId,
          providerId,
          offer.premium,
          offer.coverage_type,
          offer.deductible,
          JSON.stringify(offer.add_ons || []),
          offer.plan_name || null,
          offer.quote_id || null,
          offer.suitability_score,
          i + 1,
          JSON.stringify(offer),
        ).lastInsertRowid,
    );
    if (!i) selected = { quoteId, score: offer.suitability_score };
  }
  if (!selected) return;
  const recId = Number(
    db
      .prepare(
        "INSERT INTO Recommendations(RequestId,SelectedQuoteId,SuitabilityScore) VALUES(?,?,?)",
      )
      .run(requestId, selected.quoteId, selected.score).lastInsertRowid,
  );
  const e = data.explanation || {};
  db.prepare(
    "INSERT INTO Explanations(RecId,MainReasons,CriteriaBreakdown,ComparisonText) VALUES(?,?,?,?)",
  ).run(
    recId,
    JSON.stringify(e.main_reasons || ""),
    JSON.stringify({
      strengths: e.strengths || [],
      criteria_explanations: e.criteria_explanations || [],
    }),
    JSON.stringify(e.comparison || e.comparison_array || []),
  );
}
function logFailed(db, profileId, vehicleId, body, message) {
  return Number(
    db
      .prepare(
        "INSERT INTO " +
          "Quote_Requests(ProfileId,VehicleId,CoverageType,RequestedAddOns,Status," +
          "ErrorMessage,Priority,RequestPayload) " +
          "VALUES(?,?,?,?,?,?,?,?)",
      )
      .run(
        profileId,
        vehicleId || null,
        body.coverage_type || null,
        JSON.stringify(body.requested_add_ons || []),
        "failed",
        message,
        body.priority || null,
        JSON.stringify(body),
      ).lastInsertRowid,
  );
}
function recordResponse(db, profileId, vehicleId, body, response, data) {
  return transaction(db, () => {
    const id = Number(
      db
        .prepare(
          "INSERT INTO " +
            "Quote_Requests(ProfileId,VehicleId,CoverageType,RequestedAddOns,Status," +
            "ErrorMessage,Priority,ProviderStatus,RequestPayload) " +
            "VALUES(?,?,?,?,?,?,?,?,?)",
        )
        .run(
          profileId,
          vehicleId,
          body.coverage_type,
          JSON.stringify(body.requested_add_ons || []),
          response.ok ? "success" : "failed",
          response.ok ? null : data.error || "Upstream failure",
          body.priority,
          JSON.stringify(data.provider_status || []),
          JSON.stringify(body),
        ).lastInsertRowid,
    );
    if (response.ok) persistRecommendation(db, id, data);
    return id;
  });
}
module.exports = {
  transaction,
  ensureProfile,
  ensureVehicle,
  persistRecommendation,
  logFailed,
  recordResponse,
};
