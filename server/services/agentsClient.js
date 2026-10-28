const { agentsTimeoutMs } = require("../config");
async function requestAgents(base, route, body, timeoutMs = agentsTimeoutMs) {
  const response = await fetch(`${base}${route}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  });
  let data;
  try {
    data = await response.json();
  } catch {
    data = { error: "Invalid agents response" };
  }
  return { response, data };
}
module.exports = { requestAgents };
