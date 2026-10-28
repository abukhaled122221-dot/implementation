/** Central runtime defaults for the Node gateway. */
module.exports = {
  agentsUrl: process.env.AGENTS_SERVICE_URL || "http://127.0.0.1:8000",
  bodyLimit: "64kb",
  agentsTimeoutMs: 20_000,
};
