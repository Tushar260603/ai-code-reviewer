/**
 * config/db.js
 *
 * MySQL database connection manager using Sequelize + mysql2.
 *
 * Reads connection parameters exclusively from environment variables:
 *   MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
 *   (or MYSQL_URI / DATABASE_URL for a connection-string override)
 *
 * Rules:
 *  - Never hardcode credentials.
 *  - Do NOT call sequelize.sync() from here — that belongs in startup code.
 *  - Export a singleton Sequelize instance via getSequelizeInstance().
 */

"use strict";

const { Sequelize } = require("sequelize");

// ── Read env vars directly so this file has no circular dependency on env.js ──
// (models require db.js, env.js is safe, but keeping it self-contained avoids
//  load-order surprises when running tests.)
const {
  MYSQL_HOST     = "localhost",
  MYSQL_PORT     = "3306",
  MYSQL_USER     = "root",
  MYSQL_PASSWORD = "",
  MYSQL_DATABASE = "ai_code_reviewer",
  MYSQL_URI      = "",
  DATABASE_URL   = "",
  NODE_ENV       = "development",
} = process.env;

// ── Singleton instance ─────────────────────────────────────────────────────────
let _sequelize = null;

/**
 * Return (or lazily create) the singleton Sequelize instance.
 * Reads environment variables dynamically at creation time.
 *
 * @returns {import('sequelize').Sequelize}
 */
function getSequelizeInstance() {
  if (_sequelize) return _sequelize;

  const host = process.env.MYSQL_HOST || "localhost";
  const port = parseInt(process.env.MYSQL_PORT || "3306", 10);
  const user = process.env.MYSQL_USER || "root";
  const password = process.env.MYSQL_PASSWORD || "";
  const database = process.env.MYSQL_DATABASE || "aireview";
  const uri = process.env.MYSQL_URI || process.env.DATABASE_URL || "";
  const nodeEnv = process.env.NODE_ENV || "development";

  const logging =
    nodeEnv === "development"
      ? (msg) => console.log(`[SQL] ${msg}`)
      : false;

  if (uri) {
    _sequelize = new Sequelize(uri, {
      dialect: "mysql",
      logging,
      pool: { max: 10, min: 0, acquire: 30_000, idle: 10_000 },
    });
  } else {
    _sequelize = new Sequelize(database, user, password, {
      host,
      port,
      dialect: "mysql",
      logging,
      pool: { max: 10, min: 0, acquire: 30_000, idle: 10_000 },
    });
  }

  return _sequelize;
}

// ── connectDB / connectDatabase ────────────────────────────────────────────────

/**
 * Authenticate the MySQL connection.
 * Logs success or throws on failure.
 *
 * @returns {Promise<import('sequelize').Sequelize>}
 */
async function connectDB() {
  const sequelize = getSequelizeInstance();
  try {
    await sequelize.authenticate();
    const cfg = sequelize.config || {};
    console.log(
      `[MySQL] Connected to ${cfg.host || "localhost"}:${cfg.port || 3306}/${cfg.database || "aireview"}`
    );
    return sequelize;
  } catch (err) {
    console.error(`[MySQL] Connection failed: ${err.message}`);
    throw err;
  }
}

/**
 * Alias for connectDB — matches the name used in the spec.
 */
const connectDatabase = connectDB;

// ── closeDB ────────────────────────────────────────────────────────────────────

/**
 * Gracefully close the connection pool.
 */
async function closeDB() {
  if (_sequelize) {
    await _sequelize.close();
    _sequelize = null;
    console.log("[MySQL] Connection closed.");
  }
}

// ── Exports ────────────────────────────────────────────────────────────────────
// NOTE: `sequelize` is exported as a getter so models that do
//   const { sequelize } = require('../config/db')
// get the same singleton without triggering a premature Sequelize constructor
// call at require-time (before env vars may be loaded in tests).

module.exports = {
  get sequelize() {
    return getSequelizeInstance();
  },
  getSequelizeInstance,
  connectDB,
  connectDatabase, // spec alias
  closeDB,
};
