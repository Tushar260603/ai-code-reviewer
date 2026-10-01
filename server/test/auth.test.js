/**
 * auth.test.js
 * Automated tests for Passport.js GitHub OAuth flow, JWT authentication,
 * and auth middleware.
 */

const { describe, it, before, after } = require("node:test");
const assert = require("node:assert");
const http = require("http");
const jwt = require("jsonwebtoken");

const { app } = require("../src/index");
const { User } = require("../src/models");
const { JWT_SECRET } = require("../src/config/env");

// Helper to make HTTP requests against Express server
function makeRequest(server, options, body) {
  return new Promise((resolve, reject) => {
    const port = server.address().port;
    const reqOptions = {
      hostname: "127.0.0.1",
      port,
      path: options.path,
      method: options.method || "GET",
      headers: options.headers || {},
    };

    const req = http.request(reqOptions, (res) => {
      let rawData = "";
      res.on("data", (chunk) => {
        rawData += chunk;
      });
      res.on("end", () => {
        let json = null;
        try {
          json = JSON.parse(rawData);
        } catch (_) {}
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: json,
          raw: rawData,
        });
      });
    });

    req.on("error", reject);

    if (body) {
      req.write(body);
    }
    req.end();
  });
}

describe("Authentication & JWT Suite", () => {
  let serverInstance = null;
  let originalFindByPk = null;

  before((_, done) => {
    serverInstance = app.listen(0, () => {
      done();
    });
  });

  after((_, done) => {
    if (originalFindByPk) {
      User.findByPk = originalFindByPk;
    }
    if (serverInstance) {
      serverInstance.close(done);
    } else {
      done();
    }
  });

  it("GET /api/auth/github redirects to GitHub OAuth URL (302)", async () => {
    const res = await makeRequest(serverInstance, {
      path: "/api/auth/github",
      method: "GET",
    });

    assert.strictEqual(res.statusCode, 302);
    assert.ok(
      res.headers.location && res.headers.location.includes("github.com/login/oauth/authorize"),
      "Should redirect to GitHub OAuth authorization URL"
    );
  });

  it("GET /api/auth/me returns 401 when no auth_token cookie is provided", async () => {
    const res = await makeRequest(serverInstance, {
      path: "/api/auth/me",
      method: "GET",
    });

    assert.strictEqual(res.statusCode, 401);
    assert.strictEqual(res.body.message, "Authentication required");
  });

  it("GET /api/auth/me returns 401 when an invalid JWT is supplied", async () => {
    const res = await makeRequest(serverInstance, {
      path: "/api/auth/me",
      method: "GET",
      headers: {
        Cookie: "auth_token=invalid.jwt.token_here",
      },
    });

    assert.strictEqual(res.statusCode, 401);
    assert.strictEqual(res.body.message, "Invalid or expired token");
  });

  it("GET /api/auth/me returns 401 when user in JWT does not exist in DB", async () => {
    const fakeToken = jwt.sign(
      { sub: 999999, githubId: "nonexistent", username: "ghost" },
      JWT_SECRET,
      { expiresIn: "1h" }
    );

    originalFindByPk = User.findByPk;
    User.findByPk = async (id) => {
      if (id === 999999) return null;
      return originalFindByPk.call(User, id);
    };

    const res = await makeRequest(serverInstance, {
      path: "/api/auth/me",
      method: "GET",
      headers: {
        Cookie: `auth_token=${fakeToken}`,
      },
    });

    assert.strictEqual(res.statusCode, 401);
    assert.strictEqual(res.body.message, "User not found");
  });

  it("GET /api/auth/me returns 200 with sanitized user profile when authenticated", async () => {
    const validToken = jwt.sign(
      { sub: 42, githubId: "gh-12345", username: "tushar-dev" },
      JWT_SECRET,
      { expiresIn: "1h" }
    );

    // Mock User.findByPk to return a mock user
    User.findByPk = async (id) => {
      if (id === 42) {
        return {
          id: 42,
          githubId: "gh-12345",
          username: "tushar-dev",
          accessToken: "gho_super_secret_oauth_token",
          connectedRepos: ["tushar/project-one"],
        };
      }
      return null;
    };

    const res = await makeRequest(serverInstance, {
      path: "/api/auth/me",
      method: "GET",
      headers: {
        Cookie: `auth_token=${validToken}`,
      },
    });

    assert.strictEqual(res.statusCode, 200);
    assert.strictEqual(res.body.id, 42);
    assert.strictEqual(res.body.githubId, "gh-12345");
    assert.strictEqual(res.body.username, "tushar-dev");
    assert.deepStrictEqual(res.body.connectedRepos, ["tushar/project-one"]);
    // Must NOT expose accessToken
    assert.strictEqual(res.body.accessToken, undefined);
  });

  it("POST /api/auth/logout clears auth_token cookie", async () => {
    const res = await makeRequest(serverInstance, {
      path: "/api/auth/logout",
      method: "POST",
    });

    assert.strictEqual(res.statusCode, 200);
    assert.strictEqual(res.body.message, "Logged out successfully");

    const setCookie = res.headers["set-cookie"];
    assert.ok(setCookie, "Response should set cookie header to clear auth_token");
    const cookieHeaderStr = Array.isArray(setCookie) ? setCookie.join(";") : setCookie;
    assert.ok(
      cookieHeaderStr.includes("auth_token=") || cookieHeaderStr.includes("Max-Age=0"),
      "auth_token cookie should be cleared"
    );
  });
});
