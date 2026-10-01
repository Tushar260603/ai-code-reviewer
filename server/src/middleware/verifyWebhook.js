/**
 * verifyWebhook.js
 * Express middleware to verify GitHub webhook HMAC-SHA256 signatures.
 */

const crypto = require("crypto");
const { GITHUB_WEBHOOK_SECRET } = require("../config/env");

/**
 * Middleware that verifies the X-Hub-Signature-256 header against the raw request body.
 * Rejects invalid signatures with HTTP 401.
 * On success, parses the raw body buffer into JSON for downstream handlers.
 */
function verifyWebhook(req, res, next) {
  const signatureHeader = req.headers["x-hub-signature-256"];

  if (!signatureHeader) {
    return res.status(401).json({ error: "Invalid webhook signature" });
  }

  const secret = GITHUB_WEBHOOK_SECRET;
  if (!secret) {
    console.error("[Webhook Error] GITHUB_WEBHOOK_SECRET is not configured.");
    return res.status(500).json({ error: "Webhook secret is not configured" });
  }

  // Ensure raw body is available
  if (!req.body) {
    return res.status(400).json({ error: "Request body is empty" });
  }

  const rawBody = Buffer.isBuffer(req.body)
    ? req.body
    : Buffer.from(typeof req.body === "string" ? req.body : JSON.stringify(req.body), "utf8");

  // Compute expected HMAC SHA-256 signature
  const hmac = crypto.createHmac("sha256", secret);
  hmac.update(rawBody);
  const expectedSignature = `sha256=${hmac.digest("hex")}`;

  const sigBuffer = Buffer.from(signatureHeader, "utf8");
  const expectedBuffer = Buffer.from(expectedSignature, "utf8");

  // Constant-time comparison to prevent timing attacks
  if (
    sigBuffer.length !== expectedBuffer.length ||
    !crypto.timingSafeEqual(sigBuffer, expectedBuffer)
  ) {
    return res.status(401).json({ error: "Invalid webhook signature" });
  }

  // Parse raw body into JSON object for route handlers
  if (Buffer.isBuffer(req.body)) {
    try {
      req.body = JSON.parse(req.body.toString("utf8"));
    } catch (parseErr) {
      return res.status(400).json({ error: "Malformed JSON payload" });
    }
  }

  return next();
}

module.exports = verifyWebhook;
