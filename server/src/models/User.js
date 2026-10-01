"use strict";

/**
 * models/User.js
 *
 * Represents an authenticated GitHub user.
 *
 * Security note: accessToken is NEVER logged, returned in API responses,
 * or included in error messages. toJSON() strips it automatically.
 */

const { DataTypes } = require("sequelize");
const { getSequelizeInstance } = require("../config/db");

const sequelize = getSequelizeInstance();

const User = sequelize.define(
  "User",
  {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true,
    },

    githubId: {
      type: DataTypes.STRING,
      allowNull: false,
      unique: true,
      comment: "Numeric GitHub user ID stored as string for safety",
    },

    username: {
      type: DataTypes.STRING,
      allowNull: false,
    },

    accessToken: {
      // Sensitive: stripped from API responses via toJSON override below.
      // Future: swap DataTypes.TEXT for an encrypted blob if needed.
      type: DataTypes.TEXT,
      allowNull: true,
      defaultValue: null,
    },

    connectedRepos: {
      // Array of "owner/repo" strings the user has connected for AI review.
      // Example: ["tushar/project-one", "tushar/project-two"]
      type: DataTypes.JSON,
      allowNull: false,
      defaultValue: [],
    },
  },
  {
    tableName: "users",
    timestamps: true, // createdAt, updatedAt
    indexes: [
      { unique: true, fields: ["githubId"] },
    ],
  }
);

/**
 * Never expose accessToken in serialised output.
 */
User.prototype.toJSON = function () {
  const values = Object.assign({}, this.get());
  delete values.accessToken;
  return values;
};

module.exports = User;
