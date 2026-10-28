const express = require("express");
const { authenticate } = require("../auth");
const { recommendationErrors } = require("../services/validation");
const { requestAgents } = require("../services/agentsClient");
const {
  ensureProfile,
  ensureVehicle,
  recordResponse,
  logFailed,
} = require("../services/recommendationStore");
module.exports = ({ db, agentsUrl, agentsTimeoutMs }) => {
  const r = express.Router();
  r.post("/", authenticate(db), async (req, res) => {
    const body = req.body || {},
      errors = recommendationErrors(body);
    if (errors.length)
      return res.status(422).json({ error: "بيانات الطلب غير صالحة", errors });
    let profileId, vehicleId;
    try {
      profileId = ensureProfile(db, req.user.UserId, body);
      vehicleId = ensureVehicle(db, profileId, body);
      const { response, data } = await requestAgents(
        agentsUrl,
        "/recommend",
        body,
        agentsTimeoutMs,
      );
      const requestId = recordResponse(
        db,
        profileId,
        vehicleId,
        body,
        response,
        data,
      );
      return res
        .status(response.status)
        .json({ ...data, request_id: requestId });
    } catch (error) {
      try {
        if (profileId)
          logFailed(
            db,
            profileId,
            vehicleId,
            body,
            error.name === "TimeoutError"
              ? "Agents service timeout"
              : "Agents service unavailable",
          );
      } catch {}
      return res.status(502).json({ error: "تعذر الاتصال بخدمة التوصية" });
    }
  });
  return r;
};
