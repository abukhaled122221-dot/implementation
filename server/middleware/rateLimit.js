/** Build a small fixed-window login limiter keyed by client and identifier. */
function createRateLimiter({ max = 5, windowMs = 900_000 } = {}) {
  const failures = new Map();
  return {
    blocked(key) {
      const active = (failures.get(key) || []).filter(
        (time) => Date.now() - time < windowMs,
      );
      failures.set(key, active);
      return active.length >= max;
    },
    fail(key) {
      failures.set(key, [...(failures.get(key) || []), Date.now()]);
    },
    clear(key) {
      failures.delete(key);
    },
  };
}
module.exports = { createRateLimiter };
