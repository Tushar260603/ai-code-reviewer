/**
 * mongoose.js
 * Deprecated: Project migrated to MySQL.
 * Re-exports MySQL database helpers for backward compatibility.
 */

const { connectDB, closeDB, sequelize } = require("./mysql");

module.exports = {
  connectDB,
  closeDB,
  sequelize,
};
