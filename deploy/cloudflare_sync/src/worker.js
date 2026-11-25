/**
 * InuYasha: Seek Jade — Hybrid Sync Hub (Cloudflare Workers + D1)
 *
 * Local-First architecture:
 * - Players always play offline on embedded Python (127.0.0.1:18082).
 * - This Worker acts as a lightweight 24/7 Sync Hub on Cloudflare Free Tier:
 *   - Account auth (PBKDF2-SHA256 via native WebCrypto + opaque session tokens)
 *   - Optional invite_code gate (set via Worker secret INVITE_CODE)
 *   - Single-request Push+Pull (/sync) with optimistic revision check (409 Conflict)
 *   - Public peer snapshots for LeaderBoard, Friends & Async PvP
 *   - Append-only social_inbox for friend requests, STA gifts, messages & PvP logs
 *   - Guilds remain 100% local (not synced)
 */

const USERNAME_RE = /^[A-Za-z0-9_.-]{3,24}$/;
const PBKDF2_ITERS = 100_000; // Cloudflare Workers WebCrypto native max
const MAX_BODY_BYTES = 512 * 1024; // 512 KB hard cap
const MAX_SAVE_B64_LEN = 384 * 1024;
const MAX_SNAPSHOT_LEN = 128 * 1024;
const MAX_EVENTS_PER_SYNC = 50;
const MAX_EVENT_PAYLOAD_LEN = 2048;

const ALLOWED_EVENT_TYPES = new Set([
  "friend_req",
  "friend_accept",
  "friend_remove",
  "send_sta",
  "friend_msg",
  "pvp_challenge_log",
]);

// Recommended client-side throttling policy (server-configurable via /auth/info)
const DEFAULT_SYNC_POLICY = {
  auto_sync_interval_sec: 1800, // 30 minutes background cadence
  zone_trigger_cooldown_sec: 180, // 3 minutes cooldown when entering Social/BXH/Arena
  manual_sync_cooldown_sec: 15, // 15 seconds cooldown on manual "Sync Now" button
  request_timeout_sec: 4,
};

function nowSec() {
  return Math.floor(Date.now() / 1000);
}

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

function toHex(buf) {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let out = "";
  for (let i = 0; i < bytes.length; i++) {
    out += bytes[i].toString(16).padStart(2, "0");
  }
  return out;
}

function fromHex(hex) {
  const clean = String(hex || "").trim();
  if (clean.length % 2 !== 0) return new Uint8Array(0);
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(clean.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}

function randomHex(byteLen = 24) {
  const bytes = new Uint8Array(byteLen);
  crypto.getRandomValues(bytes);
  return toHex(bytes);
}

async function sha256Hex(text) {
  const data = new TextEncoder().encode(String(text));
  const digest = await crypto.subtle.digest("SHA-256", data);
  return toHex(digest);
}

async function timingSafeEqualStr(a, b) {
  const enc = new TextEncoder();
  const [ha, hb] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(String(a))),
    crypto.subtle.digest("SHA-256", enc.encode(String(b))),
  ]);
  const ua = new Uint8Array(ha);
  const ub = new Uint8Array(hb);
  if (typeof crypto.subtle.timingSafeEqual === "function") {
    return crypto.subtle.timingSafeEqual(ua, ub);
  }
  // Fallback for Node test environments where subtle.timingSafeEqual may not exist
  let diff = 0;
  for (let i = 0; i < ua.length; i++) {
    diff |= ua[i] ^ ub[i];
  }
  return diff === 0;
}

async function hashPassword(password, saltHex = null) {
  const salt = saltHex || randomHex(16);
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(String(password)),
    { name: "PBKDF2" },
    false,
    ["deriveBits"]
  );
  const derived = await crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      salt: fromHex(salt),
      iterations: PBKDF2_ITERS,
      hash: "SHA-256",
    },
    keyMaterial,
    256
  );
  return { salt, hash: toHex(derived) };
}

async function readBoundedJson(request) {
  const contentLen = request.headers.get("content-length");
  if (contentLen && Number(contentLen) > MAX_BODY_BYTES) {
    throw { status: 413, message: "Payload quá lớn (tối đa 512 KB)" };
  }
  const buf = await request.arrayBuffer();
  if (buf.byteLength > MAX_BODY_BYTES) {
    throw { status: 413, message: "Payload quá lớn (tối đa 512 KB)" };
  }
  if (buf.byteLength === 0) {
    return {};
  }
  try {
    const text = new TextDecoder().decode(buf);
    const parsed = JSON.parse(text);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("not an object");
    }
    return parsed;
  } catch {
    throw { status: 400, message: "JSON body không hợp lệ" };
  }
}

function getBearerToken(request) {
  const auth = request.headers.get("authorization") || "";
  if (auth.toLowerCase().startsWith("bearer ")) {
    return auth.slice(7).trim();
  }
  return (request.headers.get("x-sync-token") || "").trim();
}

async function authenticateRequest(request, env) {
  const token = getBearerToken(request);
  if (!token || token.length < 16) {
    throw { status: 401, message: "Thiếu token đăng nhập" };
  }
  const tokenHash = await sha256Hex(token);
  const row = await env.DB.prepare(
    `SELECT s.token_hash, s.device_id AS session_device_id,
            a.account_id, a.username, a.player_id, a.banned
     FROM sessions s
     JOIN accounts a ON a.account_id = s.account_id
     WHERE s.token_hash = ?`
  )
    .bind(tokenHash)
    .first();

  if (!row) {
    throw { status: 401, message: "Phiên đăng nhập không hợp lệ hoặc đã hết hạn" };
  }
  if (Number(row.banned) !== 0) {
    throw { status: 403, message: "Tài khoản đã bị khóa bởi quản trị viên" };
  }
  return row;
}

async function verifyAdmin(request, env) {
  const expected = String(env.ADMIN_TOKEN || "").trim();
  if (!expected) {
    throw { status: 403, message: "Admin API chưa được kích hoạt" };
  }
  const provided = String(request.headers.get("x-admin-token") || "").trim();
  if (!provided || !(await timingSafeEqualStr(provided, expected))) {
    throw { status: 403, message: "Sai X-Admin-Token" };
  }
}

async function handleInfo(env) {
  const countRow = await env.DB.prepare("SELECT COUNT(*) AS cnt FROM accounts").first();
  const inviteRequired = Boolean(String(env.INVITE_CODE || "").trim());
  const allowReg = String(env.ALLOW_REGISTRATION ?? "true").toLowerCase() !== "false";
  const maxAccounts = Math.max(1, Number(env.MAX_ACCOUNTS || 100));
  return jsonResponse({
    ok: true,
    mode: "hybrid_sync_hub",
    version: "r8.2-cf-d1",
    server_name: String(env.SERVER_NAME || "InuYasha Hybrid Sync Hub"),
    allow_registration: allowReg,
    invite_required: inviteRequired,
    max_accounts: maxAccounts,
    account_count: Number(countRow?.cnt || 0),
    guilds_synced: false,
    sync_policy: DEFAULT_SYNC_POLICY,
    server_time: nowSec(),
  });
}

async function handleRegister(request, env) {
  const allowReg = String(env.ALLOW_REGISTRATION ?? "true").toLowerCase() !== "false";
  if (!allowReg) {
    return jsonResponse({ ok: false, error: "Server đang tạm đóng đăng ký mới" }, 403);
  }

  const body = await readBoundedJson(request);
  const username = String(body.username || "").trim();
  const password = String(body.password || "");
  const deviceId = String(body.device_id || "unknown").trim().slice(0, 64);

  if (!USERNAME_RE.test(username)) {
    return jsonResponse(
      { ok: false, error: "Tên tài khoản 3-24 ký tự (chữ, số, _, ., -)" },
      400
    );
  }
  if (password.length < 4 || password.length > 64) {
    return jsonResponse({ ok: false, error: "Mật khẩu phải từ 4 đến 64 ký tự" }, 400);
  }

  const requiredInvite = String(env.INVITE_CODE || "").trim();
  if (requiredInvite) {
    const providedInvite = String(body.invite_code || "").trim();
    if (!providedInvite || !(await timingSafeEqualStr(providedInvite, requiredInvite))) {
      return jsonResponse({ ok: false, error: "Mã mời không đúng" }, 403);
    }
  }

  const maxAccounts = Math.max(1, Number(env.MAX_ACCOUNTS || 100));
  const countRow = await env.DB.prepare("SELECT COUNT(*) AS cnt FROM accounts").first();
  if (Number(countRow?.cnt || 0) >= maxAccounts) {
    return jsonResponse({ ok: false, error: "Server đã đạt giới hạn tài khoản" }, 403);
  }

  const usernameLower = username.toLowerCase();
  const existing = await env.DB.prepare(
    "SELECT account_id FROM accounts WHERE username_lower = ?"
  )
    .bind(usernameLower)
    .first();
  if (existing) {
    return jsonResponse({ ok: false, error: "Tên tài khoản đã tồn tại" }, 409);
  }

  const accountId = `acct_${crypto.randomUUID().replace(/-/g, "").slice(0, 16)}`;
  const playerId = crypto.randomUUID();
  const { salt, hash } = await hashPassword(password);
  const token = randomHex(24);
  const tokenHash = await sha256Hex(token);
  const ts = nowSec();

  await env.DB.batch([
    env.DB.prepare(
      `INSERT INTO accounts (account_id, username, username_lower, password_salt, password_hash, player_id, banned, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)`
    ).bind(accountId, username, usernameLower, salt, hash, playerId, ts, ts),
    env.DB.prepare(
      `INSERT INTO player_saves (account_id, player_id, sync_rev, device_id, save_hash, save_gzip_b64, snapshot_json, name, lv, fap, arena_score, updated_at)
       VALUES (?, ?, 0, ?, '', '', '{}', ?, 1, 0, 1000, ?)`
    ).bind(accountId, playerId, deviceId, username, ts),
    env.DB.prepare(
      `INSERT INTO sessions (token_hash, account_id, device_id, created_at, last_seen_at)
       VALUES (?, ?, ?, ?, ?)`
    ).bind(tokenHash, accountId, deviceId, ts, ts),
  ]);

  return jsonResponse(
    {
      ok: true,
      account_id: accountId,
      player_id: playerId,
      username,
      token,
      sync_rev: 0,
      has_cloud_save: false,
      sync_policy: DEFAULT_SYNC_POLICY,
    },
    201
  );
}

async function handleLogin(request, env) {
  const body = await readBoundedJson(request);
  const username = String(body.username || "").trim();
  const password = String(body.password || "");
  const deviceId = String(body.device_id || "unknown").trim().slice(0, 64);

  if (!username || !password) {
    return jsonResponse({ ok: false, error: "Vui lòng nhập tài khoản và mật khẩu" }, 400);
  }

  const acct = await env.DB.prepare(
    `SELECT a.account_id, a.username, a.password_salt, a.password_hash, a.player_id, a.banned,
            s.sync_rev, s.save_hash, s.lv, s.fap, s.updated_at AS save_updated_at
     FROM accounts a
     LEFT JOIN player_saves s ON s.account_id = a.account_id
     WHERE a.username_lower = ?`
  )
    .bind(username.toLowerCase())
    .first();

  if (!acct) {
    return jsonResponse({ ok: false, error: "Sai tài khoản hoặc mật khẩu" }, 401);
  }
  if (Number(acct.banned) !== 0) {
    return jsonResponse({ ok: false, error: "Tài khoản đã bị khóa" }, 403);
  }

  const { hash } = await hashPassword(password, acct.password_salt);
  const okPwd = await timingSafeEqualStr(hash, acct.password_hash);
  if (!okPwd) {
    return jsonResponse({ ok: false, error: "Sai tài khoản hoặc mật khẩu" }, 401);
  }

  const token = randomHex(24);
  const tokenHash = await sha256Hex(token);
  const ts = nowSec();

  // Keep per-device session clean (replace old token on same device, allow multi-device with 409 conflict guard)
  await env.DB.batch([
    env.DB.prepare("DELETE FROM sessions WHERE account_id = ? AND device_id = ?").bind(
      acct.account_id,
      deviceId
    ),
    env.DB.prepare(
      `INSERT INTO sessions (token_hash, account_id, device_id, created_at, last_seen_at)
       VALUES (?, ?, ?, ?, ?)`
    ).bind(tokenHash, acct.account_id, deviceId, ts, ts),
  ]);

  return jsonResponse({
    ok: true,
    account_id: acct.account_id,
    player_id: acct.player_id,
    username: acct.username,
    token,
    sync_rev: Number(acct.sync_rev || 0),
    has_cloud_save: Number(acct.sync_rev || 0) > 0 && Boolean(acct.save_hash),
    cloud_summary: {
      lv: Number(acct.lv || 1),
      fap: Number(acct.fap || 0),
      updated_at: Number(acct.save_updated_at || 0),
    },
    sync_policy: DEFAULT_SYNC_POLICY,
  });
}

async function handleChangePassword(request, env) {
  const auth = await authenticateRequest(request, env);
  const body = await readBoundedJson(request);
  const oldPassword = String(body.old_password || "");
  const newPassword = String(body.new_password || "");

  if (newPassword.length < 4 || newPassword.length > 64) {
    return jsonResponse({ ok: false, error: "Mật khẩu mới phải từ 4 đến 64 ký tự" }, 400);
  }

  const acct = await env.DB.prepare(
    "SELECT password_salt, password_hash FROM accounts WHERE account_id = ?"
  )
    .bind(auth.account_id)
    .first();

  const { hash: oldHash } = await hashPassword(oldPassword, acct.password_salt);
  if (!(await timingSafeEqualStr(oldHash, acct.password_hash))) {
    return jsonResponse({ ok: false, error: "Mật khẩu cũ không đúng" }, 401);
  }

  const { salt, hash } = await hashPassword(newPassword);
  const ts = nowSec();
  await env.DB.batch([
    env.DB.prepare(
      "UPDATE accounts SET password_salt = ?, password_hash = ?, updated_at = ? WHERE account_id = ?"
    ).bind(salt, hash, ts, auth.account_id),
    env.DB.prepare(
      "DELETE FROM sessions WHERE account_id = ? AND token_hash != ?"
    ).bind(auth.account_id, auth.token_hash),
  ]);

  return jsonResponse({ ok: true });
}

async function handleSync(request, env) {
  const auth = await authenticateRequest(request, env);
  const body = await readBoundedJson(request);
  const ts = nowSec();

  const baseRev = Math.max(0, Math.floor(Number(body.base_rev ?? 0)));
  const deviceId = String(body.device_id || auth.session_device_id || "unknown").slice(0, 64);
  const forcePush = Boolean(body.force_push);
  const saveHash = String(body.save_hash || "").trim().slice(0, 128);
  const saveGzipB64 = typeof body.save_gzip_b64 === "string" ? body.save_gzip_b64 : "";
  const peersSinceTs = Math.max(0, Math.floor(Number(body.peers_since_ts ?? 0)));

  if (saveGzipB64.length > MAX_SAVE_B64_LEN) {
    return jsonResponse({ ok: false, error: "File save quá lớn" }, 413);
  }

  const currentSave = await env.DB.prepare(
    `SELECT sync_rev, device_id, save_hash, name, lv, fap, arena_score, updated_at
     FROM player_saves WHERE account_id = ?`
  )
    .bind(auth.account_id)
    .first();

  const serverRev = Number(currentSave?.sync_rev || 0);
  const serverHash = String(currentSave?.save_hash || "");
  const hasPushPayload = Boolean(saveGzipB64 && saveHash);
  const saveChanged = hasPushPayload && saveHash !== serverHash;

  // Conflict check: client is behind server on a different save
  if (saveChanged && !forcePush && serverRev > 0 && baseRev < serverRev) {
    return jsonResponse(
      {
        ok: false,
        error: "conflict",
        message: "Dữ liệu trên Cloud mới hơn máy này. Vui lòng chọn Đẩy lên (Force Push) hoặc Tải về (Pull Overwrite).",
        server_summary: {
          sync_rev: serverRev,
          device_id: currentSave.device_id,
          save_hash: serverHash,
          name: currentSave.name,
          lv: Number(currentSave.lv || 1),
          fap: Number(currentSave.fap || 0),
          arena_score: Number(currentSave.arena_score || 1000),
          updated_at: Number(currentSave.updated_at || 0),
        },
      },
      409
    );
  }

  const writeStmts = [];
  let newRev = serverRev;

  if (saveChanged) {
    const snapObj = body.snapshot && typeof body.snapshot === "object" ? body.snapshot : {};
    const snapJson = JSON.stringify(snapObj);
    if (snapJson.length > MAX_SNAPSHOT_LEN) {
      return jsonResponse({ ok: false, error: "Snapshot quá lớn" }, 413);
    }
    const name = String(snapObj.name || auth.username).slice(0, 40);
    const lv = Math.max(1, Math.floor(Number(snapObj.lv || 1)));
    const fap = Math.max(0, Math.floor(Number(snapObj.fap || 0)));
    const arenaScore = Math.max(0, Math.floor(Number(snapObj.arena_score ?? 1000)));
    newRev = serverRev + 1;

    writeStmts.push(
      env.DB.prepare(
        `UPDATE player_saves
         SET sync_rev = ?, device_id = ?, save_hash = ?, save_gzip_b64 = ?,
             snapshot_json = ?, name = ?, lv = ?, fap = ?, arena_score = ?, updated_at = ?
         WHERE account_id = ?`
      ).bind(
        newRev,
        deviceId,
        saveHash,
        saveGzipB64,
        snapJson,
        name,
        lv,
        fap,
        arenaScore,
        ts,
        auth.account_id
      )
    );
  }

  // Enqueue outgoing social events (friend requests, STA gifts, messages, PvP challenge logs)
  const outgoing = Array.isArray(body.outgoing_events)
    ? body.outgoing_events.slice(0, MAX_EVENTS_PER_SYNC)
    : [];
  let acceptedEvents = 0;
  for (const ev of outgoing) {
    if (!ev || typeof ev !== "object") continue;
    const toPid = String(ev.to_player_id || "").trim();
    const evType = String(ev.event_type || "").trim();
    if (!toPid || toPid === auth.player_id || !ALLOWED_EVENT_TYPES.has(evType)) continue;
    const payloadStr = JSON.stringify(ev.payload && typeof ev.payload === "object" ? ev.payload : {});
    if (payloadStr.length > MAX_EVENT_PAYLOAD_LEN) continue;
    writeStmts.push(
      env.DB.prepare(
        `INSERT INTO social_inbox (to_player_id, from_player_id, event_type, payload_json, created_at, consumed)
         SELECT ?, ?, ?, ?, ?, 0
         WHERE EXISTS (SELECT 1 FROM accounts WHERE player_id = ? AND banned = 0)`
      ).bind(toPid, auth.player_id, evType, payloadStr, ts, toPid)
    );
    acceptedEvents++;
  }

  // Acknowledge previously received inbox events
  const ackIds = Array.isArray(body.ack_inbox_ids)
    ? body.ack_inbox_ids
      .map((x) => Math.floor(Number(x)))
      .filter((x) => Number.isFinite(x) && x > 0)
      .slice(0, 100)
    : [];
  if (ackIds.length > 0) {
    const placeholders = ackIds.map(() => "?").join(",");
    writeStmts.push(
      env.DB.prepare(
        `UPDATE social_inbox SET consumed = 1
         WHERE to_player_id = ? AND id IN (${placeholders})`
      ).bind(auth.player_id, ...ackIds)
    );
  }

  // Touch session last_seen_at
  writeStmts.push(
    env.DB.prepare("UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?").bind(
      ts,
      auth.token_hash
    )
  );

  if (writeStmts.length > 0) {
    await env.DB.batch(writeStmts);
  }

  // Pull updated peers (delta by updated_at) + full active peer ID list + unconsumed inbox
  const [peersRes, allIdsRes, inboxRes] = await env.DB.batch([
    env.DB.prepare(
      `SELECT player_id, name, lv, fap, arena_score, snapshot_json, updated_at
       FROM player_saves
       WHERE player_id != ? AND sync_rev > 0 AND updated_at > ?
       ORDER BY fap DESC
       LIMIT 200`
    ).bind(auth.player_id, peersSinceTs),
    env.DB.prepare(
      `SELECT p.player_id
       FROM player_saves p
       JOIN accounts a ON a.account_id = p.account_id
       WHERE p.player_id != ? AND p.sync_rev > 0 AND a.banned = 0`
    ).bind(auth.player_id),
    env.DB.prepare(
      `SELECT id, from_player_id, event_type, payload_json, created_at
       FROM social_inbox
       WHERE to_player_id = ? AND consumed = 0
       ORDER BY id ASC
       LIMIT 100`
    ).bind(auth.player_id),
  ]);

  const updatedPeers = (peersRes.results || []).map((row) => {
    let parsed = {};
    try {
      parsed = JSON.parse(row.snapshot_json || "{}");
    } catch {
      parsed = {};
    }
    return {
      player_id: row.player_id,
      name: row.name,
      lv: Number(row.lv || 1),
      fap: Number(row.fap || 0),
      arena_score: Number(row.arena_score || 1000),
      updated_at: Number(row.updated_at || 0),
      snapshot: parsed,
    };
  });

  const allPeerIds = (allIdsRes.results || []).map((r) => r.player_id);

  const inboxEvents = (inboxRes.results || []).map((row) => {
    let payload = {};
    try {
      payload = JSON.parse(row.payload_json || "{}");
    } catch {
      payload = {};
    }
    return {
      id: Number(row.id),
      from_player_id: row.from_player_id,
      event_type: row.event_type,
      payload,
      created_at: Number(row.created_at || 0),
    };
  });

  return jsonResponse({
    ok: true,
    pushed: saveChanged,
    sync_rev: newRev,
    accepted_events: acceptedEvents,
    server_time: ts,
    updated_peers: updatedPeers,
    all_peer_ids: allPeerIds,
    inbox_events: inboxEvents,
  });
}

async function handlePullSave(request, env) {
  const auth = await authenticateRequest(request, env);
  const row = await env.DB.prepare(
    `SELECT sync_rev, device_id, save_hash, save_gzip_b64, name, lv, fap, arena_score, updated_at
     FROM player_saves WHERE account_id = ?`
  )
    .bind(auth.account_id)
    .first();

  if (!row || Number(row.sync_rev || 0) === 0 || !row.save_gzip_b64) {
    return jsonResponse({ ok: false, error: "Chưa có bản lưu trên Cloud" }, 404);
  }

  return jsonResponse({
    ok: true,
    account_id: auth.account_id,
    player_id: auth.player_id,
    sync_rev: Number(row.sync_rev),
    device_id: row.device_id,
    save_hash: row.save_hash,
    save_gzip_b64: row.save_gzip_b64,
    summary: {
      name: row.name,
      lv: Number(row.lv || 1),
      fap: Number(row.fap || 0),
      arena_score: Number(row.arena_score || 1000),
    },
    updated_at: Number(row.updated_at || 0),
  });
}

async function handleAdminAccounts(request, env) {
  await verifyAdmin(request, env);
  const res = await env.DB.prepare(
    `SELECT a.account_id, a.username, a.player_id, a.banned, a.created_at,
            s.sync_rev, s.name, s.lv, s.fap, s.arena_score, s.updated_at AS last_sync_at
     FROM accounts a
     LEFT JOIN player_saves s ON s.account_id = a.account_id
     ORDER BY a.created_at ASC`
  ).all();
  return jsonResponse({ ok: true, accounts: res.results || [] });
}

async function handleAdminBan(request, env) {
  await verifyAdmin(request, env);
  const body = await readBoundedJson(request);
  const username = String(body.username || "").trim().toLowerCase();
  const banned = body.banned ? 1 : 0;
  if (!username) {
    return jsonResponse({ ok: false, error: "Thiếu username" }, 400);
  }
  const acct = await env.DB.prepare(
    "SELECT account_id FROM accounts WHERE username_lower = ?"
  )
    .bind(username)
    .first();
  if (!acct) {
    return jsonResponse({ ok: false, error: "Không tìm thấy tài khoản" }, 404);
  }
  const stmts = [
    env.DB.prepare("UPDATE accounts SET banned = ?, updated_at = ? WHERE account_id = ?").bind(
      banned,
      nowSec(),
      acct.account_id
    ),
  ];
  if (banned) {
    stmts.push(
      env.DB.prepare("DELETE FROM sessions WHERE account_id = ?").bind(acct.account_id)
    );
  }
  await env.DB.batch(stmts);
  return jsonResponse({ ok: true, account_id: acct.account_id, banned: Boolean(banned) });
}

export default {
  async fetch(request, env, _ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method.toUpperCase();

    try {
      if (method === "GET" && (path === "/health" || path === "/auth/info")) {
        return await handleInfo(env);
      }
      if (method === "POST" && path === "/auth/register") {
        return await handleRegister(request, env);
      }
      if (method === "POST" && path === "/auth/login") {
        return await handleLogin(request, env);
      }
      if (method === "POST" && path === "/auth/change_password") {
        return await handleChangePassword(request, env);
      }
      if (method === "POST" && path === "/sync") {
        return await handleSync(request, env);
      }
      if (method === "GET" && path === "/sync/pull_save") {
        return await handlePullSave(request, env);
      }
      if (method === "GET" && path === "/admin/accounts") {
        return await handleAdminAccounts(request, env);
      }
      if (method === "POST" && path === "/admin/ban") {
        return await handleAdminBan(request, env);
      }
      return jsonResponse({ ok: false, error: "Not found" }, 404);
    } catch (err) {
      if (err && typeof err === "object" && "status" in err && "message" in err) {
        return jsonResponse({ ok: false, error: err.message }, Number(err.status) || 400);
      }
      const message = err instanceof Error ? err.message : String(err);
      console.error(
        JSON.stringify({ message: "unhandled_error", path, method, error: message })
      );
      return jsonResponse({ ok: false, error: "Internal server error" }, 500);
    }
  },
};
