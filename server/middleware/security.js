/** Apply response headers while allowing the project's hosted font/icon/style assets. */
function securityHeaders(req, res, next) {
  res.set({
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
  });
  next();
}
module.exports = { securityHeaders };
