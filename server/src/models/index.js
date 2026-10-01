"use strict";

/**
 * models/index.js
 *
 * Central model registry.
 *
 * Responsibilities:
 *  1. Import all Sequelize models.
 *  2. Declare inter-model associations.
 *  3. Export models + sequelize instance + syncModels() helper.
 *
 * Usage:
 *   const { PullRequest, Review, Finding, User, sequelize, syncModels } =
 *     require('../models');
 *
 * NOTE: Do NOT call sequelize.sync() here. Call syncModels() from application
 *       startup code (index.js) after connectDB() succeeds.
 */

const { getSequelizeInstance } = require("../config/db");
const sequelize = getSequelizeInstance();

// ── Import models ──────────────────────────────────────────────────────────────
const User        = require("./User");
const PullRequest = require("./PullRequest");
const Review      = require("./Review");
const Finding     = require("./Finding");

// ── Associations ───────────────────────────────────────────────────────────────

/**
 * PullRequest → Review  (1 : N)
 * One PR can have many review runs (one per push / retry).
 */
PullRequest.hasMany(Review, {
  foreignKey: "prId",
  as: "reviews",
  onDelete: "CASCADE",
});
Review.belongsTo(PullRequest, {
  foreignKey: "prId",
  as: "pullRequest",
});

/**
 * Review → Finding  (1 : N)
 * One review run produces many per-line findings.
 */
Review.hasMany(Finding, {
  foreignKey: "reviewId",
  as: "findings",
  onDelete: "CASCADE",
});
Finding.belongsTo(Review, {
  foreignKey: "reviewId",
  as: "review",
});

// ── Sync helper ────────────────────────────────────────────────────────────────

/**
 * syncModels(opts)
 *
 * Synchronise all model definitions to the MySQL database.
 * Call from application startup, never from model files.
 *
 * @param {object}  [opts]
 * @param {boolean} [opts.force=false]  DROP + re-create tables (DESTRUCTIVE).
 * @param {boolean} [opts.alter=true]   ALTER tables to match current schema.
 */
async function syncModels({ force = false, alter = true } = {}) {
  await sequelize.sync({ force, alter });
  console.log("[MySQL] Models synchronised.");
}

// ── Exports ────────────────────────────────────────────────────────────────────
module.exports = {
  sequelize,
  User,
  PullRequest,
  Review,
  Finding,
  syncModels,
};
