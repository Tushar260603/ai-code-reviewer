"use strict";

/**
 * models/Finding.js
 *
 * One row per issue identified by a specialist agent (security, style, logic).
 *
 * The `resolved` flag supports a future feedback-loop feature:
 *   resolved = false  → finding is still active
 *   resolved = true   → developer has addressed the issue
 */

const { DataTypes } = require("sequelize");
const { getSequelizeInstance } = require("../config/db");

const sequelize = getSequelizeInstance();

const Finding = sequelize.define(
  "Finding",
  {
    id: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true,
    },

    reviewId: {
      type: DataTypes.INTEGER,
      allowNull: false,
      references: { model: "reviews", key: "id" },
      onDelete: "CASCADE",
      onUpdate: "CASCADE",
      comment: "Foreign key → reviews.id",
    },

    agentType: {
      type: DataTypes.ENUM("security", "style", "logic"),
      allowNull: false,
      comment: "Which specialist agent raised this finding",
    },

    file: {
      type: DataTypes.STRING(512),
      allowNull: false,
      comment: "Relative path to the file containing the issue",
    },

    line: {
      type: DataTypes.INTEGER,
      allowNull: false,
      comment: "Line number (1-indexed) within the file",
    },

    severity: {
      type: DataTypes.ENUM("critical", "high", "medium", "low"),
      allowNull: false,
      comment: "Issue severity level",
    },

    message: {
      type: DataTypes.TEXT,
      allowNull: false,
      comment: "Human-readable description of the issue",
    },

    resolved: {
      type: DataTypes.BOOLEAN,
      allowNull: false,
      defaultValue: false,
      comment: "True when the developer has addressed this finding",
    },
  },
  {
    tableName: "findings",
    timestamps: true, // createdAt, updatedAt
    indexes: [
      { fields: ["reviewId"] },
      { fields: ["resolved"] },
      { fields: ["agentType"] },
      { fields: ["severity"] },
    ],
  }
);

module.exports = Finding;
