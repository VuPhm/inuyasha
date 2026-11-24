#!/usr/bin/env node
/**
 * End-to-end automated tests for InuYasha Hybrid Sync Hub (Cloudflare Worker + D1).
 * Uses Node's built-in node:sqlite + node:test with a faithful D1 binding shim
 * running the exact schema.sql and src/worker.js.
 */

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";
import { fileURLToPath } from "node:url";

import worker from "./src/worker.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCHEMA_SQL = fs.readFileSync(path.join(__dirname, "schema.sql"), "utf8");

class D1StatementShim {
  constructor(db, sql, params = []) {
    this.db = db;
    this.sql = sql;
    this.params = params;
  }

  bind(...params) {
    return new D1StatementShim(this.db, this.sql, params);
  }

  async first() {
    const stmt = this.db.prepare(this.sql);
    const row = stmt.get(...this.params);
    return row === undefined ? null : { ...row };
  }

  async all() {
    const stmt = this.db.prepare(this.sql);
    const isSelect = /^\s*SELECT\b/i.test(this.sql);
    if (isSelect) {
      const rows = stmt.all(...this.params).map((r) => ({ ...r }));
      return { success: true, results: rows };
    }
    const info = stmt.run(...this.params);
    return { success: true, results: [], meta: info };
  }

  async run() {
    const stmt = this.db.prepare(this.sql);
    const info = stmt.run(...this.params);
    return { success: true, meta: info };
  }
}

class D1DatabaseShim {
  constructor() {
    this.db = new DatabaseSync(":memory:");
    this.db.exec("PRAGMA foreign_keys = ON;");
    this.db.exec(SCHEMA_SQL);
  }

  prepare(sql) {
    return new D1StatementShim(this.db, sql);
  }

  async batch(stmts) {
    this.db.exec("BEGIN");
    try {
      const results = [];
      for (const s of stmts) {
        results.push(await s.all());
      }
      this.db.exec("COMMIT");
      return results;
    } catch (err) {
      this.db.exec("ROLLBACK");
      throw err;
    }
  }
}

function makeEnv(overrides = {}) {
  return {
    DB: new D1DatabaseShim(),
    SERVER_NAME: "Test InuYasha Hybrid Hub",
    ALLOW_REGISTRATION: "true",
    MAX_ACCOUNTS: "50",
    INVITE_CODE: "TETSUIGA-2026",
    ADMIN_TOKEN: "super-secret-admin-token",
    ...overrides,
  };
}

async function req(env, method, urlPath, { body = null, token = null, headers = {} } = {}) {
  const hdrs = new Headers(headers);
  if (token) hdrs.set("Authorization", `Bearer ${token}`);
  let rawBody = undefined;
  if (body !== null) {
    hdrs.set("Content-Type", "application/json");
    rawBody = typeof body === "string" ? body : JSON.stringify(body);
  }
  const request = new Request(`https://sync.example.workers.dev${urlPath}`, {
    method,
    headers: hdrs,
    body: rawBody,
  });
  const res = await worker.fetch(request, env, {});
  const json = await res.json();
  return { status: res.status, json };
}

test("1. Health/Info reports invite_required, guilds_synced=false, and sync_policy", async () => {
  const env = makeEnv();
  const res = await req(env, "GET", "/health");
  assert.equal(res.status, 200);
  assert.equal(res.json.ok, true);
  assert.equal(res.json.invite_required, true);
  assert.equal(res.json.guilds_synced, false);
  assert.equal(res.json.sync_policy.auto_sync_interval_sec, 1800);
  assert.equal(res.json.sync_policy.zone_trigger_cooldown_sec, 180);
});

test("2. Register enforces invite_code, username rules, and uniqueness", async () => {
  const env = makeEnv();

  // Missing invite code
  const r1 = await req(env, "POST", "/auth/register", {
    body: { username: "alice", password: "secret", device_id: "dev-a" },
  });
  assert.equal(r1.status, 403);

  // Wrong invite code
  const r2 = await req(env, "POST", "/auth/register", {
    body: { username: "alice", password: "secret", invite_code: "WRONG", device_id: "dev-a" },
  });
  assert.equal(r2.status, 403);

  // Valid invite code
  const r3 = await req(env, "POST", "/auth/register", {
    body: { username: "Alice_VN", password: "secret", invite_code: "TETSUIGA-2026", device_id: "dev-a" },
  });
  assert.equal(r3.status, 201);
  assert.equal(r3.json.ok, true);
  assert.ok(r3.json.token.length >= 32);
  assert.equal(r3.json.sync_rev, 0);

  // Case-insensitive duplicate rejected
  const r4 = await req(env, "POST", "/auth/register", {
    body: { username: "alice_vn", password: "secret", invite_code: "TETSUIGA-2026", device_id: "dev-b" },
  });
  assert.equal(r4.status, 409);
});

test("3. Two-player Sync Push+Pull, Delta Peers, and Social Inbox ACK flow", async () => {
  const env = makeEnv();

  const aliceReg = await req(env, "POST", "/auth/register", {
    body: { username: "alice", password: "pw123", invite_code: "TETSUIGA-2026", device_id: "a51" },
  });
  const bobReg = await req(env, "POST", "/auth/register", {
    body: { username: "bob", password: "pw123", invite_code: "TETSUIGA-2026", device_id: "s23" },
  });
  assert.equal(aliceReg.status, 201);
  assert.equal(bobReg.status, 201);

  const aliceToken = aliceReg.json.token;
  const alicePid = aliceReg.json.player_id;
  const bobToken = bobReg.json.token;
  const bobPid = bobReg.json.player_id;
  assert.notEqual(alicePid, bobPid);

  // Alice pushes save v1
  const sA1 = await req(env, "POST", "/sync", {
    token: aliceToken,
    body: {
      base_rev: 0,
      device_id: "a51",
      save_hash: "hash-a-1",
      save_gzip_b64: "H4sIAAAAAAAA/2NgGAWjYBSMglEwCgAA",
      snapshot: { name: "InuAlice", lv: 55, fap: 180000, arena_score: 1320, slots: [{ id: 1 }] },
      peers_since_ts: 0,
    },
  });
  assert.equal(sA1.status, 200);
  assert.equal(sA1.json.pushed, true);
  assert.equal(sA1.json.sync_rev, 1);
  assert.equal(sA1.json.updated_peers.length, 0);

  // Bob pushes save v1 AND sends friend_req + send_sta + pvp_challenge_log to Alice
  const sB1 = await req(env, "POST", "/sync", {
    token: bobToken,
    body: {
      base_rev: 0,
      device_id: "s23",
      save_hash: "hash-b-1",
      save_gzip_b64: "H4sIAAAAAAAA/2NgGAWjYBSMglEwCgBB",
      snapshot: { name: "SesshoBob", lv: 52, fap: 165000, arena_score: 1280, slots: [{ id: 2 }] },
      outgoing_events: [
        { to_player_id: alicePid, event_type: "friend_req", payload: { from_name: "SesshoBob" } },
        { to_player_id: alicePid, event_type: "send_sta", payload: { sta: 2 } },
        { to_player_id: alicePid, event_type: "pvp_challenge_log", payload: { winner: bobPid, delta: 15 } },
      ],
      peers_since_ts: 0,
    },
  });
  assert.equal(sB1.status, 200);
  assert.equal(sB1.json.sync_rev, 1);
  assert.equal(sB1.json.accepted_events, 3);
  assert.equal(sB1.json.updated_peers.length, 1);
  assert.equal(sB1.json.updated_peers[0].player_id, alicePid);
  assert.equal(sB1.json.updated_peers[0].fap, 180000);

  // Alice syncs with unchanged save_hash -> no-op push, pulls Bob snapshot + 3 inbox events
  const sA2 = await req(env, "POST", "/sync", {
    token: aliceToken,
    body: {
      base_rev: 1,
      device_id: "a51",
      save_hash: "hash-a-1",
      save_gzip_b64: "H4sIAAAAAAAA/2NgGAWjYBSMglEwCgAA",
      peers_since_ts: 0,
    },
  });
  assert.equal(sA2.status, 200);
  assert.equal(sA2.json.pushed, false);
  assert.equal(sA2.json.sync_rev, 1);
  assert.equal(sA2.json.updated_peers.length, 1);
  assert.equal(sA2.json.updated_peers[0].player_id, bobPid);
  assert.equal(sA2.json.inbox_events.length, 3);

  // Alice ACKs all 3 inbox events -> inbox becomes empty
  const ackIds = sA2.json.inbox_events.map((e) => e.id);
  const sA3 = await req(env, "POST", "/sync", {
    token: aliceToken,
    body: {
      base_rev: 1,
      device_id: "a51",
      ack_inbox_ids: ackIds,
      peers_since_ts: sA2.json.server_time + 1,
    },
  });
  assert.equal(sA3.status, 200);
  assert.equal(sA3.json.inbox_events.length, 0);
  assert.equal(sA3.json.updated_peers.length, 0); // Delta pull skipped unchanged Bob
  assert.deepEqual(sA3.json.all_peer_ids, [bobPid]);
});

test("4. Multi-device 409 Conflict, Pull Overwrite, and Force Push", async () => {
  const env = makeEnv();
  const reg = await req(env, "POST", "/auth/register", {
    body: { username: "dualuser", password: "pw123", invite_code: "TETSUIGA-2026", device_id: "phone1" },
  });
  const token1 = reg.json.token;

  const login2 = await req(env, "POST", "/auth/login", {
    body: { username: "dualuser", password: "pw123", device_id: "tablet2" },
  });
  assert.equal(login2.status, 200);
  const token2 = login2.json.token;

  // Phone1 pushes rev 1 -> rev 2
  await req(env, "POST", "/sync", {
    token: token1,
    body: {
      base_rev: 0,
      device_id: "phone1",
      save_hash: "h1",
      save_gzip_b64: "SAVE_V1",
      snapshot: { name: "Dual", lv: 20, fap: 50000 },
    },
  });
  const p2 = await req(env, "POST", "/sync", {
    token: token1,
    body: {
      base_rev: 1,
      device_id: "phone1",
      save_hash: "h2",
      save_gzip_b64: "SAVE_V2",
      snapshot: { name: "Dual", lv: 25, fap: 65000 },
    },
  });
  assert.equal(p2.json.sync_rev, 2);

  // Tablet2 tries to push with stale base_rev=1 -> 409 Conflict
  const conflict = await req(env, "POST", "/sync", {
    token: token2,
    body: {
      base_rev: 1,
      device_id: "tablet2",
      save_hash: "h-tablet",
      save_gzip_b64: "SAVE_TABLET",
      snapshot: { name: "Dual", lv: 22, fap: 55000 },
    },
  });
  assert.equal(conflict.status, 409);
  assert.equal(conflict.json.error, "conflict");
  assert.equal(conflict.json.server_summary.sync_rev, 2);
  assert.equal(conflict.json.server_summary.lv, 25);

  // Tablet2 can pull the latest cloud save
  const pulled = await req(env, "GET", "/sync/pull_save", { token: token2 });
  assert.equal(pulled.status, 200);
  assert.equal(pulled.json.save_gzip_b64, "SAVE_V2");
  assert.equal(pulled.json.sync_rev, 2);

  // Or Tablet2 can force_push to overwrite
  const forced = await req(env, "POST", "/sync", {
    token: token2,
    body: {
      base_rev: 1,
      device_id: "tablet2",
      force_push: true,
      save_hash: "h-tablet",
      save_gzip_b64: "SAVE_TABLET",
      snapshot: { name: "Dual", lv: 22, fap: 55000 },
    },
  });
  assert.equal(forced.status, 200);
  assert.equal(forced.json.sync_rev, 3);
});

test("5. Change password revokes other sessions, Admin ban blocks access, and 413 size cap works", async () => {
  const env = makeEnv();
  const r1 = await req(env, "POST", "/auth/register", {
    body: { username: "charlie", password: "oldpw", invite_code: "TETSUIGA-2026", device_id: "d1" },
  });
  const l2 = await req(env, "POST", "/auth/login", {
    body: { username: "charlie", password: "oldpw", device_id: "d2" },
  });

  // Change password on d1 -> d2 session revoked
  const cp = await req(env, "POST", "/auth/change_password", {
    token: r1.json.token,
    body: { old_password: "oldpw", new_password: "newpw" },
  });
  assert.equal(cp.status, 200);

  const d2Sync = await req(env, "POST", "/sync", { token: l2.json.token, body: {} });
  assert.equal(d2Sync.status, 401);

  // Admin rejects bad token
  const badAdmin = await req(env, "GET", "/admin/accounts", {
    headers: { "X-Admin-Token": "wrong" },
  });
  assert.equal(badAdmin.status, 403);

  // Admin lists & bans charlie
  const listRes = await req(env, "GET", "/admin/accounts", {
    headers: { "X-Admin-Token": "super-secret-admin-token" },
  });
  assert.equal(listRes.status, 200);
  assert.equal(listRes.json.accounts.length, 1);

  const banRes = await req(env, "POST", "/admin/ban", {
    headers: { "X-Admin-Token": "super-secret-admin-token" },
    body: { username: "charlie", banned: true },
  });
  assert.equal(banRes.status, 200);

  const bannedLogin = await req(env, "POST", "/auth/login", {
    body: { username: "charlie", password: "newpw", device_id: "d3" },
  });
  assert.equal(bannedLogin.status, 403);

  // Oversized body -> 413
  const big = "x".repeat(260 * 1024);
  const bigRes = await req(env, "POST", "/auth/login", {
    body: JSON.stringify({ username: "a", password: big }),
  });
  assert.equal(bigRes.status, 413);
});
