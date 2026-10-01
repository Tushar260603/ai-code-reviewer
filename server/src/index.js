/**
 * index.js
 * Main Express server entry point for the AI Code Reviewer backend.
 */

const express = require("express");
const cors = require("cors");
const cookieParser = require("cookie-parser");
const passport = require("passport");

const { PORT, NODE_ENV, FRONTEND_URL } = require("./config/env");
const { connectDB, closeDB } = require("./config/db");
const { syncModels } = require("./models");
const { closeReviewQueue } = require("./queues/review.queue");

// Load Passport strategy configuration
require("./config/passport");

// Initialize review queue worker to process jobs asynchronously
try {
  require("./queue/reviewWorker");
} catch (err) {
  console.warn("[Server] Note: Review worker not initialized (Redis may be offline):", err.message);
}

// Route imports
const webhookRoutes = require("./routes/webhook.routes");
const authRoutes = require("./routes/auth.routes");
const reviewsRoutes = require("./routes/reviews.routes");
const metricsRoutes = require("./routes/metrics.routes");
const reposRoutes = require("./routes/repos.routes");

const app = express();

// ── 1. Security, CORS & Cookie Parsing ──────────────────────────────────────
app.use(
  cors({
    origin: FRONTEND_URL || "http://localhost:3000",
    credentials: true,
  })
);

app.use(cookieParser());
app.use(passport.initialize());

// ── 2. Body Parsing Middleware ────────────────────────────────────────────
// IMPORTANT: GitHub webhook verification requires the exact raw payload.
// We apply express.raw() exclusively to /api/webhook/github.
app.use("/api/webhook/github", express.raw({ type: "application/json" }));

// Standard JSON and URL-encoded parsers for all other routes
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// ── 3. Health Check Endpoint ──────────────────────────────────────────────
app.get("/health", (req, res) => {
  return res.status(200).json({
    status: "healthy",
  });
});

// ── 4. Routes Mounting ────────────────────────────────────────────────────
app.use("/api/webhook", webhookRoutes);
app.use("/api/auth", authRoutes);
app.use("/api/reviews", reviewsRoutes);
app.use("/api/metrics", metricsRoutes);
app.use("/api/repos", reposRoutes);

// ── 5. 404 Route Handler ──────────────────────────────────────────────────
app.use((req, res) => {
  return res.status(404).json({
    error: "Not Found",
    message: `Cannot ${req.method} ${req.originalUrl}`,
  });
});

// ── 6. Centralized Error Handler ──────────────────────────────────────────
app.use((err, req, res, next) => {
  console.error(`[Server Error] ${req.method} ${req.originalUrl}:`, err.message);

  const statusCode = err.status || err.statusCode || 500;
  return res.status(statusCode).json({
    error: err.name || "Internal Server Error",
    message:
      NODE_ENV === "production" && statusCode === 500
        ? "An internal server error occurred."
        : err.message || "An unexpected error occurred.",
  });
});

// ── 7. Server Initialization ──────────────────────────────────────────────
let server = null;

async function startServer() {
  try {
    // 1. Connect to MySQL and sync all model tables
    await connectDB();
    await syncModels({ alter: true });
    console.log("[Server] Database tables synced.");

    server = app.listen(PORT, () => {
      console.log(`[Server] AI Reviewer Node service listening on port ${PORT}`);
      console.log(`[Server] Health check available at http://localhost:${PORT}/health`);
      console.log(
        `[Server] Webhook endpoint mounted at http://localhost:${PORT}/api/webhook/github`
      );
      console.log(
        `[Server] Auth endpoints mounted at http://localhost:${PORT}/api/auth`
      );
    });
  } catch (error) {
    console.error("[Server] Fatal error during startup:", error.message);
    process.exit(1);
  }
}

// ── 8. Graceful Shutdown ──────────────────────────────────────────────────
async function handleShutdown(signal) {
  console.log(`\n[Server] Received ${signal}. Initiating graceful shutdown...`);

  if (server) {
    server.close(() => {
      console.log("[Server] HTTP server closed.");
    });
  }

  try {
    await closeReviewQueue();
    await closeDB();
    console.log("[Server] All database and queue connections closed.");
    process.exit(0);
  } catch (err) {
    console.error("[Server] Error during shutdown:", err.message);
    process.exit(1);
  }
}

process.on("SIGINT", () => handleShutdown("SIGINT"));
process.on("SIGTERM", () => handleShutdown("SIGTERM"));

// Auto-start when executed directly
if (require.main === module) {
  startServer();
}

module.exports = {
  app,
  startServer,
};
