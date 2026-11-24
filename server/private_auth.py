#!/usr/bin/env python3
"""Authentication, session management, and config for Small Private Server (R8.1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
from typing import Any

from event_runtime import EventRuntime, build_default_event_registry

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")
_EMPTY_GUILD_ID = "00000000-0000-0000-0000-000000000000"
_PBKDF2_ITERS = 120_000


class AuthError(Exception):
    """Domain error carrying an HTTP status code and user-facing message."""

    def __init__(self, message: str, http_status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.http_status = int(http_status)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


@dataclass
class PrivateServerConfig:
    """Persistent configuration governing a private server instance."""

    server_name: str = "S1 InuYasha Private"
    notice: str = "Chào mừng đến với Server Private InuYasha (R7.40)!\nChúc anh em chơi vui vẻ."
    allow_registration: bool = True
    max_accounts: int = 100
    allow_free_recharge: bool = True
    allow_instant_1m_recharge: bool = True
    max_free_recharge_per_day: int = 0
    expose_debug_server: bool = False
    require_session_auth: bool = True
    chat_port: int = 8081
    public_base_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> PrivateServerConfig:
        if not isinstance(raw, dict):
            return cls()
        defaults = asdict(cls())
        merged: dict[str, Any] = {}
        for key, def_val in defaults.items():
            val = raw.get(key, def_val)
            if isinstance(def_val, bool):
                merged[key] = bool(val)
            elif isinstance(def_val, int):
                try:
                    merged[key] = int(val)
                except (TypeError, ValueError):
                    merged[key] = def_val
            else:
                merged[key] = str(val) if val is not None else def_val
        return cls(**merged)

    @classmethod
    def load(cls, path: Path, *, persist: bool = True) -> PrivateServerConfig:
        if persist and path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                cfg = cls.from_dict(raw)
                return cfg
            except (ValueError, OSError):
                pass
        cfg = cls()
        if persist:
            cfg.save(path)
        return cfg

    def save(self, path: Path) -> None:
        _write_json_atomic(path, self.to_dict())


class PrivateAuthManager:
    """Manages per-player accounts, PBKDF2 credentials, and single-device game sessions."""

    def __init__(self, data_dir: Path, emu: Any) -> None:
        self.data_dir = Path(data_dir)
        self.emu = emu
        self._lock = threading.RLock()
        self._rate_lock = threading.Lock()
        self._rate_buckets: dict[str, list[float]] = {}
        self.accounts_path = self.data_dir / "private_accounts.json"
        self.sessions_path = self.data_dir / "private_sessions.json"
        self.accounts: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self._uname_to_aid: dict[str, str] = {}
        self._uid_to_aid: dict[str, str] = {}
        self._pid_to_aid: dict[str, str] = {}
        self._load_state()

    @property
    def cfg(self) -> PrivateServerConfig:
        return self.emu.private_config

    def _rebuild_indexes(self) -> None:
        self._uname_to_aid = {
            str(a.get("username_lower", "")): aid
            for aid, a in self.accounts.items()
            if a.get("username_lower")
        }
        self._uid_to_aid = {
            str(a.get("user_id", "")): aid
            for aid, a in self.accounts.items()
            if a.get("user_id")
        }
        self._pid_to_aid = {
            str(a.get("player_id", "")): aid
            for aid, a in self.accounts.items()
            if a.get("player_id")
        }

    def _save_accounts(self) -> None:
        if not self.emu.persist:
            return
        ordered = [
            self.accounts[aid]
            for aid in sorted(self.accounts, key=lambda k: int(self.accounts[k].get("slot", 0)))
        ]
        _write_json_atomic(
            self.accounts_path,
            {"schema_version": 1, "accounts": ordered, "updated_at": int(time.time())},
        )

    def _save_sessions(self) -> None:
        if not self.emu.persist:
            return
        _write_json_atomic(
            self.sessions_path,
            {"schema_version": 1, "sessions": self.sessions, "updated_at": int(time.time())},
        )

    def _materialize_store(self, acct: dict[str, Any], *, reset: bool = False) -> Any:
        from emulator import ProfileStore  # Local import avoids circular import at module load time

        aid = str(acct["account_id"])
        slot = int(acct["slot"])
        save_rel = str(acct["save_file"])
        def_pid = str(acct["player_id"])
        used_ranks = {
            int(p.state.get("pvp", {}).get("rank", 1500))
            for k, p in self.emu.s1_accounts.items()
            if k != aid
        }
        cand_rank = max(100, 1500 - (slot - 1) * 7)
        while cand_rank in used_ranks and cand_rank > 50:
            cand_rank -= 7
        store = ProfileStore(
            aid,
            self.emu.game_data,
            self.emu.ledger,
            state_path=self.data_dir / save_rel,
            persist=self.emu.persist,
            reset=reset,
            trace_path=self.emu.trace_path if self.emu.persist else None,
            clock=self.emu.clock,
            default_player_id=def_pid,
            default_arena_rank=cand_rank,
            peer_profiles_fn=self.emu.get_s1_peer_profiles,
            account_manager=self.emu,
        )
        if str(store.state.get("player", {}).get("PlayerId", "")) != def_pid:
            store.state["player"]["PlayerId"] = def_pid
            store.save()
        self.emu.s1_accounts[aid] = store
        self.emu.profiles[aid] = store
        return store

    def _load_state(self) -> None:
        if self.emu.persist and self.accounts_path.exists():
            try:
                raw = json.loads(self.accounts_path.read_text(encoding="utf-8"))
                for entry in raw.get("accounts", []):
                    aid = str(entry.get("account_id", "")).strip()
                    if not aid:
                        continue
                    self.accounts[aid] = dict(entry)
                    self._materialize_store(self.accounts[aid])
            except (ValueError, OSError):
                pass
        if self.emu.persist and self.sessions_path.exists():
            try:
                raw_s = json.loads(self.sessions_path.read_text(encoding="utf-8"))
                sess = raw_s.get("sessions", {})
                if isinstance(sess, dict):
                    self.sessions = {
                        str(k): dict(v) for k, v in sess.items() if k in self.accounts and isinstance(v, dict)
                    }
            except (ValueError, OSError):
                pass
        self._rebuild_indexes()

    def _check_rate_limit(
        self, ip: str, *, limit: int = 30, window_sec: float = 60.0
    ) -> tuple[bool, str | None]:
        key = str(ip or "").strip() or "local"
        now = time.monotonic()
        cutoff = now - window_sec
        with self._rate_lock:
            bucket = [ts for ts in self._rate_buckets.get(key, []) if ts >= cutoff]
            if len(bucket) >= limit:
                self._rate_buckets[key] = bucket
                return False, "Quá nhiều yêu cầu, vui lòng thử lại sau 1 phút"
            bucket.append(now)
            self._rate_buckets[key] = bucket
            return True, None

    @staticmethod
    def _hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
        salt = salt_hex or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERS
        ).hex()
        return salt, digest

    @staticmethod
    def _verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
        if not salt_hex or not expected_hash:
            return False
        _, actual = PrivateAuthManager._hash_password(password, salt_hex=salt_hex)
        return hmac.compare_digest(actual, expected_hash)

    @staticmethod
    def _validate_credentials(username: str, password: str) -> tuple[str, str]:
        uname = str(username or "").strip()
        pwd = str(password or "")
        if not _USERNAME_RE.match(uname):
            raise AuthError("Tên tài khoản phải từ 3–24 ký tự (chỉ gồm chữ, số, _, ., -)", 400)
        if not (4 <= len(pwd) <= 64):
            raise AuthError("Mật khẩu phải từ 4–64 ký tự", 400)
        return uname, pwd

    def _auth_payload(self, acct: dict[str, Any], auth_token: str) -> dict[str, Any]:
        aid = acct["account_id"]
        store = self.emu.s1_accounts[aid]
        p = store.state.get("player", {})
        return {
            "ok": True,
            "AccountId": aid,
            "UserID": str(acct["user_id"]),
            "PlayerId": str(acct["player_id"]),
            "Username": str(acct["username"]),
            "Role": str(acct.get("role", "player")),
            "AuthToken": auth_token,
            "ServerName": self.cfg.server_name,
            "Notice": self.cfg.notice,
            "PlayerName": str(p.get("PlayerName", "")),
            "Lv": int(p.get("Lv", 1)),
            "Vip": int(p.get("Vip", 0)),
            "IsNewPlayer": int(p.get("IsNewPlayer", 1)),
        }

    def register(self, username: str, password: str, *, ip: str = "") -> dict[str, Any]:
        allowed, err = self._check_rate_limit(ip)
        if not allowed:
            raise AuthError(err or "Quá nhiều yêu cầu", 429)
        uname, pwd = self._validate_credentials(username, password)
        uname_low = uname.lower()

        with self._lock:
            if not self.cfg.allow_registration:
                raise AuthError("Máy chủ đang tạm khóa đăng ký tài khoản mới", 403)
            if self.cfg.max_accounts > 0 and len(self.accounts) >= int(self.cfg.max_accounts):
                raise AuthError("Máy chủ đã đạt giới hạn số tài khoản tối đa", 403)
            if uname_low in self._uname_to_aid:
                raise AuthError("Tên tài khoản đã tồn tại", 409)

            next_slot = max((int(a.get("slot", 0)) for a in self.accounts.values()), default=0) + 1
            aid = f"u_{next_slot}"
            uid = str(100000 + next_slot)
            pid = str(200000 + next_slot)
            salt_hex, hash_hex = self._hash_password(pwd)
            now = int(time.time())
            acct = {
                "account_id": aid,
                "slot": next_slot,
                "username": uname,
                "username_lower": uname_low,
                "user_id": uid,
                "player_id": pid,
                "save_file": f"players/u_{next_slot}.json",
                "password_salt": salt_hex,
                "password_hash": hash_hex,
                "role": "gm" if next_slot == 1 else "player",
                "banned": False,
                "created_at": now,
                "last_login_at": now,
                "last_login_ip": str(ip or ""),
            }
            self.accounts[aid] = acct
            self._rebuild_indexes()
            self._materialize_store(acct, reset=False)
            auth_token = secrets.token_hex(24)
            self.sessions[aid] = {
                "auth_token": auth_token,
                "game_session": "",
                "updated_at": now,
            }
            self._save_accounts()
            self._save_sessions()
            return self._auth_payload(acct, auth_token)

    def login(self, username: str, password: str, *, ip: str = "") -> dict[str, Any]:
        allowed, err = self._check_rate_limit(ip)
        if not allowed:
            raise AuthError(err or "Quá nhiều yêu cầu", 429)
        uname = str(username or "").strip()
        pwd = str(password or "")
        if not uname or not pwd:
            raise AuthError("Vui lòng nhập tài khoản và mật khẩu", 400)

        with self._lock:
            aid = self._uname_to_aid.get(uname.lower())
            acct = self.accounts.get(aid) if aid else None
            if not acct or not self._verify_password(pwd, acct.get("password_salt", ""), acct.get("password_hash", "")):
                raise AuthError("Sai tài khoản hoặc mật khẩu", 401)
            if acct.get("banned"):
                raise AuthError("Tài khoản đã bị khóa", 403)

            now = int(time.time())
            auth_token = secrets.token_hex(24)
            acct["last_login_at"] = now
            acct["last_login_ip"] = str(ip or "")
            cur_sess = self.sessions.setdefault(aid, {})
            cur_sess["auth_token"] = auth_token
            cur_sess["updated_at"] = now
            self._save_accounts()
            self._save_sessions()
            return self._auth_payload(acct, auth_token)

    def change_password(
        self, username: str, old_password: str, new_password: str, *, ip: str = ""
    ) -> dict[str, Any]:
        allowed, err = self._check_rate_limit(ip)
        if not allowed:
            raise AuthError(err or "Quá nhiều yêu cầu", 429)
        uname = str(username or "").strip()
        if not uname or not old_password:
            raise AuthError("Thiếu tên tài khoản hoặc mật khẩu cũ", 400)
        if not (4 <= len(str(new_password or "")) <= 64):
            raise AuthError("Mật khẩu mới phải từ 4–64 ký tự", 400)

        with self._lock:
            aid = self._uname_to_aid.get(uname.lower())
            acct = self.accounts.get(aid) if aid else None
            if not acct or not self._verify_password(
                str(old_password), acct.get("password_salt", ""), acct.get("password_hash", "")
            ):
                raise AuthError("Sai tài khoản hoặc mật khẩu cũ", 401)
            if acct.get("banned"):
                raise AuthError("Tài khoản đã bị khóa", 403)

            salt_hex, hash_hex = self._hash_password(str(new_password))
            acct["password_salt"] = salt_hex
            acct["password_hash"] = hash_hex
            new_auth_token = secrets.token_hex(24)
            self.sessions[aid] = {
                "auth_token": new_auth_token,
                "game_session": "",
                "updated_at": int(time.time()),
            }
            store = self.emu.s1_accounts.get(aid)
            if store is not None:
                store.state["player"]["Session"] = ""
                store.save()
            self._save_accounts()
            self._save_sessions()
            return {
                "ok": True,
                "AccountId": aid,
                "Username": acct["username"],
                "UserID": acct["user_id"],
                "AuthToken": new_auth_token,
            }

    @staticmethod
    def _extract_token_and_uid(user_id: str, login_info_raw: Any) -> tuple[str, str]:
        uid = str(user_id or "").strip()
        raw = str(login_info_raw or "").strip()
        token = raw
        if raw.startswith("{"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    token = str(
                        parsed.get("auth_token")
                        or parsed.get("sessionId")
                        or parsed.get("token")
                        or ""
                    ).strip()
                    if not uid and parsed.get("uid"):
                        uid = str(parsed["uid"]).strip()
            except ValueError:
                pass
        return uid, token

    def verify_auth_token(self, user_id: str, login_info_raw: Any) -> tuple[int, dict[str, Any] | None]:
        uid, token = self._extract_token_and_uid(user_id, login_info_raw)
        if not token:
            return -1101, None
        with self._lock:
            acct: dict[str, Any] | None = None
            aid = self._uid_to_aid.get(uid) if uid else None
            if aid:
                acct = self.accounts.get(aid)
            else:
                for cand_aid, sess in self.sessions.items():
                    exp = str(sess.get("auth_token") or "")
                    if exp and hmac.compare_digest(exp, token):
                        acct = self.accounts.get(cand_aid)
                        break
            if not acct:
                return -1101, None
            if acct.get("banned"):
                return -1102, None
            expected = str(self.sessions.get(acct["account_id"], {}).get("auth_token") or "")
            if not expected or not hmac.compare_digest(expected, token):
                return -1101, None
            return 0, acct

    def issue_game_session(self, account_id: str) -> str:
        with self._lock:
            if account_id not in self.accounts:
                raise KeyError(f"Unknown account_id: {account_id}")
            game_session = secrets.token_hex(24)
            sess = self.sessions.setdefault(account_id, {})
            sess["game_session"] = game_session
            sess["updated_at"] = int(time.time())
            store = self.emu.s1_accounts[account_id]
            store.state["player"]["Session"] = game_session
            self._save_sessions()
            store.save()
            return game_session

    def resolve_by_game_session(
        self, player_id: str, session_token: str
    ) -> tuple[int, dict[str, Any] | None, Any]:
        pid = str(player_id or "").strip()
        tok = str(session_token or "").strip()
        if not pid:
            return -1101, None, None
        with self._lock:
            aid = self._pid_to_aid.get(pid)
            acct = self.accounts.get(aid) if aid else None
            if not acct:
                return -1101, None, None
            if acct.get("banned"):
                return -1102, None, None
            if self.cfg.require_session_auth:
                expected = str(self.sessions.get(aid, {}).get("game_session") or "")
                if not tok or not expected or not hmac.compare_digest(expected, tok):
                    return -1101, None, None
            store = self.emu.s1_accounts.get(aid)
            if store is None:
                return -1101, None, None
            return 0, acct, store

    def resolve_store_by_identifier(self, identifier: str) -> Any | None:
        key = str(identifier or "").strip()
        if not key:
            return None
        with self._lock:
            for aid in (
                key if key in self.accounts else None,
                self._uname_to_aid.get(key.lower()),
                self._uid_to_aid.get(key),
                self._pid_to_aid.get(key),
            ):
                if aid and aid in self.emu.s1_accounts:
                    return self.emu.s1_accounts[aid]
        return None

    def active_session_count(self) -> int:
        with self._lock:
            return sum(1 for s in self.sessions.values() if s.get("game_session"))

    def list_accounts(self) -> list[dict[str, Any]]:
        with self._lock:
            out: list[dict[str, Any]] = []
            for aid in sorted(self.accounts, key=lambda k: int(self.accounts[k].get("slot", 0))):
                acct = self.accounts[aid]
                store = self.emu.s1_accounts.get(aid)
                p = store.state.get("player", {}) if store else {}
                rank = int(store.state.get("pvp", {}).get("rank", 1500)) if store else 1500
                sess = self.sessions.get(aid, {})
                out.append(
                    {
                        "account_id": aid,
                        "username": acct["username"],
                        "user_id": acct["user_id"],
                        "player_id": acct["player_id"],
                        "role": acct.get("role", "player"),
                        "banned": bool(acct.get("banned", False)),
                        "PlayerName": str(p.get("PlayerName", "")),
                        "Lv": int(p.get("Lv", 1)),
                        "Vip": int(p.get("Vip", 0)),
                        "Diamond": int(p.get("Diamond", 0)),
                        "FAP": int(p.get("FAP", 0)),
                        "ArenaRank": rank,
                        "IsNewPlayer": int(p.get("IsNewPlayer", 1)),
                        "created_at": int(acct.get("created_at", 0)),
                        "last_login_at": int(acct.get("last_login_at", 0)),
                        "has_active_session": bool(sess.get("game_session")),
                    }
                )
            return out

    def _get_acct_by_username_or_id(self, identifier: str) -> dict[str, Any]:
        key = str(identifier or "").strip()
        aid = (
            key
            if key in self.accounts
            else self._uname_to_aid.get(key.lower())
            or self._uid_to_aid.get(key)
            or self._pid_to_aid.get(key)
        )
        acct = self.accounts.get(aid) if aid else None
        if not acct:
            raise AuthError(f"Không tìm thấy tài khoản: {identifier}", 404)
        return acct

    def set_banned(self, username: str, banned: bool) -> dict[str, Any]:
        with self._lock:
            acct = self._get_acct_by_username_or_id(username)
            aid = acct["account_id"]
            acct["banned"] = bool(banned)
            if acct["banned"]:
                self.sessions[aid] = {"auth_token": "", "game_session": "", "updated_at": int(time.time())}
                store = self.emu.s1_accounts.get(aid)
                if store is not None:
                    store.state["player"]["Session"] = ""
                    store.save()
                self._save_sessions()
            self._save_accounts()
            return {"ok": True, "username": acct["username"], "account_id": aid, "banned": acct["banned"]}

    def set_role(self, username: str, role: str) -> dict[str, Any]:
        norm_role = str(role or "player").strip().lower()
        if norm_role not in ("player", "gm"):
            raise AuthError("Role chỉ hỗ trợ 'player' hoặc 'gm'", 400)
        with self._lock:
            acct = self._get_acct_by_username_or_id(username)
            acct["role"] = norm_role
            self._save_accounts()
            return {"ok": True, "username": acct["username"], "account_id": acct["account_id"], "role": norm_role}

    def reset_password_admin(self, username: str, new_password: str) -> dict[str, Any]:
        if not (4 <= len(str(new_password or "")) <= 64):
            raise AuthError("Mật khẩu mới phải từ 4–64 ký tự", 400)
        with self._lock:
            acct = self._get_acct_by_username_or_id(username)
            aid = acct["account_id"]
            salt_hex, hash_hex = self._hash_password(str(new_password))
            acct["password_salt"] = salt_hex
            acct["password_hash"] = hash_hex
            self.sessions[aid] = {"auth_token": "", "game_session": "", "updated_at": int(time.time())}
            store = self.emu.s1_accounts.get(aid)
            if store is not None:
                store.state["player"]["Session"] = ""
                store.save()
            self._save_accounts()
            self._save_sessions()
            return {"ok": True, "username": acct["username"], "account_id": aid}

    def import_offline_save(
        self,
        username: str,
        *,
        bundle_path: str | Path | None = None,
        state_path: str | Path | None = None,
        bundle_data: dict[str, Any] | None = None,
        source_account_id: str = "acct_1",
    ) -> dict[str, Any]:
        with self._lock:
            acct = self._get_acct_by_username_or_id(username)
            aid = acct["account_id"]
            store = self.emu.s1_accounts[aid]

            raw_obj: dict[str, Any] | None = bundle_data
            if raw_obj is None:
                src = Path(bundle_path or state_path or "")
                if not str(src) or not src.is_file():
                    raise AuthError("Không tìm thấy tệp dữ liệu nguồn để import", 400)
                raw_obj = json.loads(src.read_text(encoding="utf-8"))

            if not isinstance(raw_obj, dict):
                raise AuthError("Dữ liệu import phải là JSON object", 400)

            if raw_obj.get("bundle_format") == "inuyasha_seek_jade_standalone_save_v1":
                accts = raw_obj.get("accounts") or {}
                entry = accts.get(source_account_id)
                if not isinstance(entry, dict) or not isinstance(entry.get("state"), dict):
                    raise AuthError(f"Bản sao lưu không có tài khoản nguồn '{source_account_id}'", 400)
                state_obj = dict(entry["state"])
            elif "player" in raw_obj:
                state_obj = dict(raw_obj)
            else:
                raise AuthError("Định dạng save nguồn không hợp lệ", 400)

            # Safety backup before mutating the target private account
            safety_dir = self.data_dir / "backups"
            safety_dir.mkdir(parents=True, exist_ok=True)
            safety_path = safety_dir / f"pre_import_{aid}_{int(time.time())}.json"
            if self.emu.persist:
                _write_json_atomic(safety_path, store.state)

            with store._lock:
                cur_sess = str(store.state.get("player", {}).get("Session") or "")
                norm = store._normalize_loaded_state(state_obj)
                norm["player"]["PlayerId"] = str(acct["player_id"])
                norm["player"]["Session"] = cur_sess

                # Ensure imported guild membership references an existing guild on this private server
                g_state = norm.setdefault("guild", {})
                imported_gid = str(g_state.get("guild_id") or _EMPTY_GUILD_ID)
                valid_gids: set[str] = set()
                guilds_path = self.data_dir / "s1_guilds.json"
                if guilds_path.exists():
                    try:
                        g_reg = json.loads(guilds_path.read_text(encoding="utf-8"))
                        valid_gids = set((g_reg.get("guilds") or {}).keys())
                    except (ValueError, OSError):
                        valid_gids = set()
                if imported_gid != _EMPTY_GUILD_ID and imported_gid not in valid_gids:
                    g_state["guild_id"] = _EMPTY_GUILD_ID
                    g_state["share_id"] = ""
                    norm["player"]["GuildId"] = {
                        "Id": _EMPTY_GUILD_ID,
                        "Name": "",
                        "ExtendInfo": {},
                    }

                # Avoid Arena rank collision with existing private accounts
                used_ranks = {
                    int(peer.state.get("pvp", {}).get("rank", 1500))
                    for k, peer in self.emu.s1_accounts.items()
                    if k != aid
                }
                pvp_st = norm.setdefault("pvp", {})
                cand_rank = int(pvp_st.get("rank", store.default_arena_rank) or store.default_arena_rank)
                while cand_rank in used_ranks and cand_rank > 50:
                    cand_rank -= 7
                while cand_rank in used_ranks:
                    cand_rank += 1
                pvp_st["rank"] = cand_rank

                store.state = norm
                store.event_runtime = EventRuntime(
                    self.emu.clock,
                    build_default_event_registry(self.emu.game_data),
                    store.state,
                )
                store._recalc_all_slots_and_fap()
                store.save()

            p_out = store.state.get("player", {})
            return {
                "ok": True,
                "username": acct["username"],
                "account_id": aid,
                "PlayerId": str(p_out.get("PlayerId", "")),
                "PlayerName": str(p_out.get("PlayerName", "")),
                "Lv": int(p_out.get("Lv", 1)),
                "Vip": int(p_out.get("Vip", 0)),
                "FAP": int(p_out.get("FAP", 0)),
                "ArenaRank": int(store.state.get("pvp", {}).get("rank", 1500)),
                "SafetyBackupPath": str(safety_path) if self.emu.persist else "",
            }
