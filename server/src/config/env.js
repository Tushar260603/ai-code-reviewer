/**
 * env.js
 * Central environment configuration loader.
 */

const path = require("path");
const dotenv = require("dotenv");

// Load .env from server directory
dotenv.config({ path: path.resolve(__dirname, "../../.env") });

const config = {
  NODE_ENV: process.env.NODE_ENV || "development",
  PORT: parseInt(process.env.PORT || "8000", 10),

  // MySQL Database Configuration
  MYSQL_HOST: process.env.MYSQL_HOST || "localhost",
  MYSQL_PORT: parseInt(process.env.MYSQL_PORT || "3306", 10),
  MYSQL_USER: process.env.MYSQL_USER || "root",
  MYSQL_PASSWORD: process.env.MYSQL_PASSWORD || "",
  MYSQL_DATABASE: process.env.MYSQL_DATABASE || "ai_code_reviewer",
  MYSQL_URI: process.env.MYSQL_URI || process.env.DATABASE_URL || "",

  // Redis & Queue Configuration
  REDIS_URL: process.env.REDIS_URL || "redis://localhost:6379",

  // GitHub & Agent Service Configuration
  GITHUB_WEBHOOK_SECRET: process.env.GITHUB_WEBHOOK_SECRET || "",
  GITHUB_TOKEN:          process.env.GITHUB_TOKEN           || "",
  WEBHOOK_PAYLOAD_URL:   process.env.WEBHOOK_PAYLOAD_URL || process.env.PUBLIC_URL || "http://localhost:5000/api/webhook/github",
  FASTAPI_URL:           process.env.FASTAPI_URL            || "http://localhost:8001",

  // GitHub OAuth Configuration
  GITHUB_CLIENT_ID:     process.env.GITHUB_CLIENT_ID     || "",
  GITHUB_CLIENT_SECRET: process.env.GITHUB_CLIENT_SECRET || "",
  GITHUB_CALLBACK_URL:  process.env.GITHUB_CALLBACK_URL  || "http://localhost:8000/api/auth/github/callback",

  // JWT Configuration
  JWT_SECRET:     process.env.JWT_SECRET     || "default_jwt_secret_change_in_production",
  JWT_EXPIRES_IN: process.env.JWT_EXPIRES_IN || "7d",

  // Frontend & Session Configuration
  FRONTEND_URL:   process.env.FRONTEND_URL   || "http://localhost:3000",
  SESSION_SECRET: process.env.SESSION_SECRET || "default_session_secret",
};

module.exports = config;
