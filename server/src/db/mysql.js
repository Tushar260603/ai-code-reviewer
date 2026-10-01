/**
 * mysql.js
 * Central export of MySQL connection and Sequelize instance.
 */

const { sequelize, connectDB, closeDB } = require("../config/db");

module.exports = {
  sequelize,
  connectDB,
  closeDB,
};
