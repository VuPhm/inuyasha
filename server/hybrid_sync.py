#!/usr/bin/env python3
"""
InuYasha: Seek Jade — Hybrid Local-First Cloud Sync Client & Peer Proxy (R8.2).

Architecture:
  - Game always runs locally on embedded Python (127.0.0.1:18082).
  - Syncs asynchronously with the Cloudflare Workers + D1 Sync Hub (100% Free tier).
  - Guilds remain 100% local (never synced).
  - Remote friends' teams are materialized as lightweight ReadOnlyPeerProxy objects
    fed into ProfileStore.peer_profiles_fn, seamlessly powering LeaderBoard, Arena PvP,
    Friends, and Formation Inspection even while offline.
  - Smart throttled triggers:
      * Background auto-sync cadence: 30 min (1800s)
      * Smart zone entry (LeaderBoard / Friend / PVP / PvpInter): 3 min (180s) cooldown
      * Outgoing social event debounce: 20s batching
      * Manual "Sync Now" button: 15s cooldown
"""

from __future__ import annotations

import base64
import copy
import gzip
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
import threading
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
import uuid

DEFAULT_SYNC_HUB_URL = "https://inuyasha-sync-hub.vuphamletruong.workers.dev"
SYNC_USER_AGENT = "InuYashaHybridSync/1.0"

ZONE_SYNC_MODULES = frozenset({
    "LeaderBoard",
    "Friend",
    "FriendMessage",
    "PVP",
    "PvpInter",
})

DEFAULT_SYNC_POLICY: dict[str, int] = {
    "auto_sync_interval_sec": 1800,
    "zone_trigger_cooldown_sec": 180,
    "manual_sync_cooldown_sec": 15,
    "outgoing_debounce_sec": 20,
    "request_timeout_sec": 4,
}


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _normalize_url(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return DEFAULT_SYNC_HUB_URL
    if not s.startswith(("http://", "https://")):
        s = "https://" + s
    return s.rstrip("/")


def _build_ssl_context() -> ssl.SSLContext:
    """Build a verified TLS context that works on macOS, Linux, and Android embedded Python."""
    bundled = Path(__file__).resolve().parent / "sync_ca_bundle.pem"
    if bundled.exists():
        try:
            ctx = ssl.create_default_context(cafile=str(bundled))
            return ctx
        except (ssl.SSLError, OSError):
            pass
    android_cacerts = Path("/system/etc/security/cacerts")
    if android_cacerts.is_dir():
        try:
            return ssl.create_default_context(capath=str(android_cacerts))
        except (ssl.SSLError, OSError):
            pass
    return ssl.create_default_context()


class _NullEventRuntime:
    """Read-only stub for r79_event_handlers peer inspection."""

    @staticmethod
    def get_instance(_instance_id: str) -> dict[str, Any]:
        return {}


class ReadOnlyPeerProxy:
    """
    Lightweight read-only ProfileStore-compatible view of a synced friend.
    Supplied to GameEmulatorState.get_s1_peer_profiles() so LeaderBoard, Arena,
    Friends, and Formation inspection work identically offline and online.
    """

    is_remote_peer: bool = True

    def __init__(self, record: dict[str, Any]) -> None:
        self._lock = threading.RLock()
        self.event_runtime = _NullEventRuntime()
        pid = str(record.get("player_id") or "")
        snap = record.get("snapshot") if isinstance(record.get("snapshot"), dict) else {}
        player_snap = snap.get("player") if isinstance(snap.get("player"), dict) else {}
        name = str(record.get("name") or player_snap.get("PlayerName") or "Bạn bè")
        lv = max(1, int(record.get("lv") or player_snap.get("Lv") or 1))
        fap = max(0, int(record.get("fap") or player_snap.get("FAP") or 0))
        arena_score = max(0, int(record.get("arena_score") or snap.get("arena_score") or 1000))
        arena_rank = int(snap.get("arena_rank") or 1500)

        self.profile_name = f"cloud:{pid}"
        self._slot_formations_view: dict[str, Any] = (
            copy.deepcopy(snap["slot_formations"])
            if isinstance(snap.get("slot_formations"), dict)
            else {}
        )
        self._ally_fight_objs: list[dict[str, Any]] = (
            copy.deepcopy(snap["ally_fight_objs"])
            if isinstance(snap.get("ally_fight_objs"), list)
            else []
        )

        # Build minimal compatible state dictionary
        player_dict = {
            "PlayerId": pid,
            "PlayerName": name,
            "IsNewPlayer": 0,
            "Lv": lv,
            "FAP": fap,
            "Vip": int(player_snap.get("Vip", 0)),
            "HeadImageId": int(player_snap.get("HeadImageId", 0)),
            "FashionModelId": int(player_snap.get("FashionModelId", 0)),
            "HeroModelId": int(player_snap.get("HeroModelId", 12011002)),
            "GuildName": "",  # Guilds are strictly local
            "GuildId": "00000000-0000-0000-0000-000000000000",
        }
        slots = snap.get("slots") if isinstance(snap.get("slots"), list) else []
        embattle = (
            snap.get("embattle")
            if isinstance(snap.get("embattle"), dict)
            else {f"Formation{i}": i for i in range(1, 7)}
        )
        self.state: dict[str, Any] = {
            "player": player_dict,
            "slots": copy.deepcopy(slots),
            "heroes": copy.deepcopy(snap.get("heroes", [])) if isinstance(snap.get("heroes"), list) else [],
            "embattle": copy.deepcopy(embattle),
            "pvp": {
                "rank": arena_rank,
                "arena_score": arena_score,
            },
            "leaderboard": {
                "praised_date": "",
                "praised_types": [],
                "praise_counts": {},
                "received_praises": copy.deepcopy(snap.get("received_praises", {}))
                if isinstance(snap.get("received_praises"), dict)
                else {},
            },
            "social": {
                "friends": [],
                "enemies": [],
                "sta_inbox": [],
                "friend_messages": [],
                "unread": {"system": False, "battle": False, "friend": False},
            },
        }

    def _own_slot_formations_view(self) -> dict[str, Any]:
        if self._slot_formations_view:
            sf = copy.deepcopy(self._slot_formations_view)
            if "SlotInfos" in sf and "SlotInfo" not in sf:
                sf["SlotInfo"] = copy.deepcopy(sf["SlotInfos"])
            return sf
        return {
            "PlayerId": self.state["player"]["PlayerId"],
            "SlotInfo": copy.deepcopy(self.state["slots"]),
            "SlotInfos": copy.deepcopy(self.state["slots"]),
            "MateInfos": [],
            "SlotFormationInfo": copy.deepcopy(self.state["embattle"]),
            "SkillInfos": [],
            "CombatPet": None,
        }

    def _build_ally_fight_objs(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._ally_fight_objs)

    def _social_state(self) -> dict[str, Any]:
        return self.state["social"]

    @staticmethod
    def _friend_max_for_lv(lv: int) -> int:
        return max(30, min(100, 20 + int(lv)))

    def _push_player_email(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def save(self) -> None:
        return None


_CORE_PROP_KEYS = ("HP", "AP", "DEF", "SPD", "FSP", "FAP")


def _compact_property(prop: Any) -> dict[str, Any]:
    """Keep core stats and drop redundant zero-valued padding fields."""
    if not isinstance(prop, dict):
        return {}
    out: dict[str, Any] = {}
    for k, v in prop.items():
        if v is None:
            continue
        if k in _CORE_PROP_KEYS:
            out[k] = v
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if v != 0:
                out[k] = v
        elif v:
            out[k] = v
    return out


def _snap_json_bytes(obj: dict[str, Any]) -> int:
    return len(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def build_public_snapshot(store: Any) -> dict[str, Any]:
    """
    Build a compact public peer snapshot (<= 28 KB) from a local ProfileStore.
    Contains everything needed by friends for LeaderBoard, Arena PvP, and Formation view.
    Excludes Guild info (guilds stay 100% local).
    """
    p = store.state.get("player", {})
    pvp = store.state.get("pvp", {})
    slots = store.state.get("slots", [])
    embattle = store.state.get("embattle", {})
    lb = store.state.get("leaderboard", {})

    compact_slots: list[dict[str, Any]] = []
    for sl in slots[:6]:
        if not isinstance(sl, dict):
            continue
        compact_slots.append(
            {
                "SlotId": int(sl.get("SlotId", 0)),
                "HeroId": sl.get("HeroId", ""),
                "HeroModelId": int(sl.get("HeroModelId", 0)),
                "Lv": int(sl.get("Lv", 1)),
                "Step": int(sl.get("Step", 0)),
                "FAP": int(sl.get("FAP", 0)),
                "Property": _compact_property(sl.get("Property", {})),
            }
        )

    slot_formations = store._own_slot_formations_view()
    if isinstance(slot_formations, dict):
        # SlotInfo duplicates SlotInfos; ReadOnlyPeerProxy reconstructs SlotInfo on read.
        slot_formations.pop("SlotInfo", None)
    ally_fight_objs = store._build_ally_fight_objs()

    snap: dict[str, Any] = {
        "name": str(p.get("PlayerName") or "Adventurer")[:40],
        "lv": max(1, int(p.get("Lv", 1))),
        "fap": max(0, int(p.get("FAP", 0))),
        "arena_score": max(0, int(pvp.get("arena_score", 1000))),
        "arena_rank": int(pvp.get("rank", 1500)),
        "player": {
            "PlayerId": str(p.get("PlayerId", "")),
            "PlayerName": str(p.get("PlayerName") or "Adventurer")[:40],
            "Lv": max(1, int(p.get("Lv", 1))),
            "FAP": max(0, int(p.get("FAP", 0))),
            "Vip": int(p.get("Vip", 0)),
            "HeadImageId": int(p.get("HeadImageId", 0)),
            "FashionModelId": int(p.get("FashionModelId", 0)),
            "HeroModelId": int(p.get("HeroModelId", 12011002)),
        },
        "slots": compact_slots,
        "embattle": copy.deepcopy(embattle),
        "received_praises": copy.deepcopy(lb.get("received_praises", {}))
        if isinstance(lb.get("received_praises"), dict)
        else {},
        "slot_formations": slot_formations,
        "ally_fight_objs": ally_fight_objs,
    }

    budget_bytes = 28 * 1024
    sf = snap.get("slot_formations")
    slot_infos = sf.get("SlotInfos") if isinstance(sf, dict) and isinstance(sf.get("SlotInfos"), list) else []

    # Tier 1: compact per-slot Property & strip bulky socket lists when > 28 KB
    if _snap_json_bytes(snap) > budget_bytes:
        for sinfo in slot_infos:
            if isinstance(sinfo, dict):
                if isinstance(sinfo.get("Property"), dict):
                    sinfo["Property"] = _compact_property(sinfo["Property"])
                for key in ("Gem", "Warfarespirit", "GemList", "ExtraAttrs"):
                    sinfo.pop(key, None)

    # Tier 2: shrink equip/treasure/pet sub-dicts and duplicated slot Property when still > 28 KB
    if _snap_json_bytes(snap) > budget_bytes:
        keep_eq_keys = ("Id", "ModelId", "Lv", "Step", "Quality")
        for sinfo in slot_infos:
            if not isinstance(sinfo, dict):
                continue
            for eq_key in ("Weapon", "Helmet", "Clothes", "Necklace", "Book", "Badge", "Pet"):
                sub = sinfo.get(eq_key)
                if isinstance(sub, dict):
                    sinfo[eq_key] = {k: sub[k] for k in keep_eq_keys if k in sub}
        for cs in snap.get("slots", []):
            if isinstance(cs, dict):
                cs.pop("Property", None)

    # Tier 3: shrink Mate/Skill/Hero details & fallback slots list when still > 28 KB
    if _snap_json_bytes(snap) > budget_bytes:
        if isinstance(sf, dict):
            sf["MateInfos"] = []
            sf["SkillInfos"] = []
        keep_hero_keys = ("Id", "ModelId", "Lv", "Step", "Quality", "FAP")
        for sinfo in slot_infos:
            if isinstance(sinfo, dict) and isinstance(sinfo.get("Hero"), dict):
                hero = sinfo["Hero"]
                sinfo["Hero"] = {k: hero[k] for k in keep_hero_keys if k in hero}
        if _snap_json_bytes(snap) > budget_bytes:
            snap["slots"] = []

    return snap


def compress_save_state(state: dict[str, Any]) -> tuple[str, str]:
    """Return (sha256_hex, gzip_base64_str) of a ProfileStore state dict."""
    raw = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    gz_b64 = base64.b64encode(gzip.compress(raw, compresslevel=6)).decode("ascii")
    return digest, gz_b64


def decompress_save_state(save_gzip_b64: str) -> dict[str, Any]:
    raw = gzip.decompress(base64.b64decode(save_gzip_b64.encode("ascii")))
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict) or "player" not in parsed:
        raise ValueError("Invalid cloud save payload")
    return parsed


class HybridSyncManager:
    """
    Manages Local-First Cloud Sync against the Cloudflare Workers + D1 Sync Hub.
    Safe to run both embedded on Android and on macOS/Linux desktop or tests.
    """

    def __init__(
        self,
        data_dir: Path,
        emu: Any,
        *,
        persist: bool = True,
        default_url: str = DEFAULT_SYNC_HUB_URL,
        http_opener: Any = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.emu = emu
        self.persist = persist
        self._http_opener = http_opener  # Optional injectable mock for unit tests
        self._ssl_ctx = _build_ssl_context()
        self._resolved_ip_cache: dict[str, tuple[str, float]] = {}
        self._lock = threading.RLock()
        self._sync_in_flight = False
        self._last_attempt_mono = 0.0
        self._last_zone_trigger_mono = 0.0
        self._last_manual_mono = 0.0
        self._outgoing_dirty_since_mono = 0.0

        self.state_path = self.data_dir / "hybrid_sync_state.json"
        self.peers_path = self.data_dir / "hybrid_peers.json"

        self.cfg: dict[str, Any] = {
            "server_url": _normalize_url(default_url),
            "enabled": False,
            "account_id": "",
            "player_id": "",
            "local_account_id": "",
            "username": "",
            "token": "",
            "device_id": f"dev-{uuid.uuid4().hex[:12]}",
            "sync_rev": 0,
            "last_pushed_hash": "",
            "last_sync_at": 0,
            "peers_since_ts": 0,
            "last_error": "",
            "conflict": None,
            "outgoing_events": [],
            "pending_ack_ids": [],
            "applied_inbox_ids": [],
            "sync_policy": dict(DEFAULT_SYNC_POLICY),
        }
        self._peers_raw: dict[str, dict[str, Any]] = {}
        self._peer_proxies: dict[str, ReadOnlyPeerProxy] = {}
        self._load_state()

    # -------------------- Persistence --------------------

    def _load_state(self) -> None:
        if self.persist and self.state_path.exists():
            try:
                raw = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for k, v in raw.items():
                        if k in self.cfg:
                            self.cfg[k] = v
                    if not isinstance(self.cfg.get("sync_policy"), dict):
                        self.cfg["sync_policy"] = dict(DEFAULT_SYNC_POLICY)
                    else:
                        merged = dict(DEFAULT_SYNC_POLICY)
                        merged.update(self.cfg["sync_policy"])
                        self.cfg["sync_policy"] = merged
            except (ValueError, OSError):
                pass
        if self.persist and self.peers_path.exists():
            try:
                raw_p = json.loads(self.peers_path.read_text(encoding="utf-8"))
                peers = raw_p.get("peers", {}) if isinstance(raw_p, dict) else {}
                if isinstance(peers, dict):
                    self._peers_raw = {str(k): dict(v) for k, v in peers.items() if isinstance(v, dict)}
                    self._rebuild_peer_proxies()
            except (ValueError, OSError):
                pass

    def _save_cfg(self) -> None:
        if not self.persist:
            return
        _write_json_atomic(self.state_path, self.cfg)

    def _save_peers(self) -> None:
        if not self.persist:
            return
        _write_json_atomic(
            self.peers_path,
            {"schema_version": 1, "peers": self._peers_raw, "updated_at": int(time.time())},
        )

    def _rebuild_peer_proxies(self) -> None:
        my_pid = str(self.cfg.get("player_id") or "")
        proxies: dict[str, ReadOnlyPeerProxy] = {}
        for pid, rec in self._peers_raw.items():
            if not pid or pid == my_pid:
                continue
            proxies[pid] = ReadOnlyPeerProxy(rec)
        # Recompute deterministic Arena ranks among remote peers sorted by arena_score desc, fap desc
        ranked = sorted(
            proxies.values(),
            key=lambda pr: (
                -int(pr.state.get("pvp", {}).get("arena_score", 1000)),
                -int(pr.state.get("player", {}).get("FAP", 0)),
                str(pr.state.get("player", {}).get("PlayerId", "")),
            ),
        )
        # Assign distinct ranks in top-500 band so friends appear cleanly in Arena & RankList
        used_ranks: set[int] = set()
        for idx, pr in enumerate(ranked):
            cand = int(pr.state.get("pvp", {}).get("rank", 1500))
            if cand < 1 or cand > 2000 or cand in used_ranks:
                cand = max(1, min(1999, 50 + idx * 5))
                while cand in used_ranks and cand < 2000:
                    cand += 1
            used_ranks.add(cand)
            pr.state["pvp"]["rank"] = cand
        self._peer_proxies = proxies

    def get_peer_proxies(self, exclude_player_id: str = "") -> list[ReadOnlyPeerProxy]:
        with self._lock:
            return [
                pr
                for pid, pr in self._peer_proxies.items()
                if pid != exclude_player_id
            ]

    # -------------------- Active Local Profile Helpers --------------------

    def _active_store(self) -> Any:
        aid = getattr(self.emu, "active_account_id", "acct_1")
        s1 = getattr(self.emu, "s1_accounts", {})
        if aid in s1:
            return s1[aid]
        if "acct_1" in s1:
            return s1["acct_1"]
        return self.emu.profiles.get(self.emu.default_profile)

    def _find_slot_by_player_id(self, pid: str) -> str | None:
        target = str(pid or "").strip()
        if not target or self.emu is None:
            return None
        s1 = getattr(self.emu, "s1_accounts", {})
        matches: list[tuple[tuple[int, int, int, str], str]] = []
        for aid, st in s1.items():
            p = st.state.get("player", {})
            if str(p.get("PlayerId", "")).strip() == target:
                score = (
                    0 if int(p.get("IsNewPlayer", 1)) == 1 else 1,
                    int(p.get("Lv", 1)),
                    int(p.get("FAP", 0)),
                    aid,
                )
                matches.append((score, aid))
        if not matches:
            return None
        matches.sort(reverse=True)
        return matches[0][1]

    def _bound_account_id(self) -> str:
        s1 = getattr(self.emu, "s1_accounts", {})
        bound = str(self.cfg.get("local_account_id") or "").strip()
        if bound and bound in s1:
            return bound
        cloud_pid = str(self.cfg.get("player_id") or "").strip()
        if cloud_pid:
            matched = self._find_slot_by_player_id(cloud_pid)
            if matched and matched in s1:
                self.cfg["local_account_id"] = matched
                return matched
        return getattr(self.emu, "active_account_id", "acct_1")

    def _bound_store(self) -> Any:
        s1 = getattr(self.emu, "s1_accounts", {})
        aid = self._bound_account_id()
        if aid in s1:
            return s1[aid]
        return self._active_store()

    def _account_user_id_and_display(self, aid: str) -> tuple[str, str]:
        if self.emu is not None and hasattr(self.emu, "_summarize_s1_account"):
            try:
                summary = self.emu._summarize_s1_account(aid)
                return str(summary.get("user_id") or "100001"), str(summary.get("display") or aid)
            except Exception:
                pass
        meta = getattr(self.emu, "s1_meta", {}).get(aid, {})
        uid = str(meta.get("user_id") or "100001")
        label = str(meta.get("label") or aid)
        return uid, label

    def _bind_local_player_id(self, cloud_pid: str, account_id: str | None = None) -> None:
        s1 = getattr(self.emu, "s1_accounts", {})
        target_aid = str(account_id or "").strip() or self._bound_account_id()
        store = s1.get(target_aid) if target_aid in s1 else self._bound_store()
        if store is None or not cloud_pid:
            return
        for other_aid, other_st in s1.items():
            if other_aid != target_aid and str(other_st.state.get("player", {}).get("PlayerId", "")).strip() == cloud_pid:
                if hasattr(self.emu, "_deduplicate_s1_player_ids"):
                    self.emu._deduplicate_s1_player_ids()
                return
        with store._lock:
            cur_pid = str(store.state.get("player", {}).get("PlayerId", ""))
            if cur_pid != cloud_pid:
                store.state["player"]["PlayerId"] = cloud_pid
                store.save()

    # -------------------- HTTP Transport --------------------

    _DOH_ENDPOINTS: tuple[tuple[str, str], ...] = (
        ("1.1.1.1", "/dns-query"),
        ("1.0.0.1", "/dns-query"),
        ("8.8.8.8", "/resolve"),
    )

    @staticmethod
    def _is_dns_resolution_error(exc: BaseException) -> bool:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.gaierror):
            return True
        if getattr(reason, "errno", None) in (7, -2, -3, -5, 11001, 11002):
            return True
        msg = f"{exc} {reason}".lower()
        return any(
            needle in msg
            for needle in (
                "no address associated with hostname",
                "name or service not known",
                "nodename nor servname",
                "temporary failure in name resolution",
                "getaddrinfo failed",
                "errno 7",
            )
        )

    @classmethod
    def _format_network_error(cls, exc: BaseException) -> str:
        reason = getattr(exc, "reason", exc)
        if cls._is_dns_resolution_error(exc):
            return (
                "Không kết nối được Sync Hub: Thiết bị đang ngoại tuyến hoặc "
                "không phân giải được tên miền máy chủ (kiểm tra Wi-Fi/4G)."
            )
        if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(exc).lower():
            return "Không kết nối được Sync Hub: Kết nối quá thời gian (kiểm tra mạng Wi-Fi/4G)."
        if isinstance(reason, ssl.SSLError) or "certificate" in str(exc).lower() or "ssl" in str(exc).lower():
            return "Không kết nối được Sync Hub: Lỗi xác thực bảo mật TLS."
        if isinstance(reason, OSError) and getattr(reason, "errno", None) in (
            51, 61, 65, 101, 111, 113, 10051, 10061, 10065
        ):
            return (
                "Không kết nối được Sync Hub: Thiết bị đang ngoại tuyến hoặc "
                "không có đường truyền mạng (kiểm tra Wi-Fi/4G)."
            )
        return "Không kết nối được Sync Hub: Không thể kết nối tới máy chủ (kiểm tra kết nối mạng)."

    def _cache_host_ip(self, host: str) -> None:
        if not host:
            return
        now = time.time()
        cached = self._resolved_ip_cache.get(host)
        if cached and (now - cached[1]) < 300.0:
            return
        try:
            infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
            if infos:
                ip_str = str(infos[0][4][0])
                ipaddress.IPv4Address(ip_str)
                self._resolved_ip_cache[host] = (ip_str, now)
        except (OSError, ValueError):
            pass

    def _resolve_host_via_doh(self, host: str, timeout: float) -> str | None:
        if not host:
            return None
        try:
            ipaddress.ip_address(host)
            return host
        except ValueError:
            pass

        qname = urllib.parse.quote(host, safe="")
        doh_timeout = min(max(1.5, timeout), 3.0)
        for doh_ip, doh_path in self._DOH_ENDPOINTS:
            doh_url = f"https://{doh_ip}{doh_path}?name={qname}&type=A"
            req = urllib.request.Request(
                doh_url,
                headers={"Accept": "application/dns-json", "User-Agent": SYNC_USER_AGENT},
                method="GET",
            )
            try:
                with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=doh_timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8", "replace"))
                for ans in body.get("Answer") or []:
                    if not isinstance(ans, dict) or int(ans.get("type", 0)) != 1:
                        continue
                    cand = str(ans.get("data") or "").strip()
                    try:
                        ipaddress.IPv4Address(cand)
                    except ValueError:
                        continue
                    self._resolved_ip_cache[host] = (cand, time.time())
                    return cand
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
                continue
        return None

    def _http_json_via_ip(
        self,
        method: str,
        url: str,
        target_ip: str,
        headers: dict[str, str],
        data_bytes: bytes | None,
        timeout: float,
    ) -> tuple[int, dict[str, Any]]:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        req_headers = dict(headers)
        req_headers["Host"] = parsed.netloc or host

        if parsed.scheme == "https":
            ssl_ctx = self._ssl_ctx

            class _SNIHTTPSConnection(http.client.HTTPSConnection):
                def connect(self_conn) -> None:
                    sock = socket.create_connection(
                        (target_ip, self_conn.port),
                        self_conn.timeout,
                        self_conn.source_address,
                    )
                    if getattr(self_conn, "_tunnel_host", None):
                        self_conn.sock = sock
                        self_conn._tunnel()
                    self_conn.sock = ssl_ctx.wrap_socket(sock, server_hostname=host)

            conn: http.client.HTTPConnection = _SNIHTTPSConnection(
                host, port=port, timeout=timeout, context=ssl_ctx
            )
        else:
            conn = http.client.HTTPConnection(target_ip, port=port, timeout=timeout)

        try:
            conn.request(method, path, body=data_bytes, headers=req_headers)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8", "replace")
            status = int(resp.status)
        finally:
            conn.close()

        try:
            body_json = json.loads(raw) if raw else {}
        except ValueError:
            body_json = {"ok": False, "error": raw or f"HTTP {status}"}
        return status, body_json

    def _http_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        *,
        token: str | None = None,
        timeout: float | None = None,
    ) -> tuple[int, dict[str, Any]]:
        headers = {
            "User-Agent": SYNC_USER_AGENT,
            "Accept": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data_bytes: bytes | None = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

        req_timeout = float(timeout or self.cfg["sync_policy"].get("request_timeout_sec", 4))

        if callable(self._http_opener):
            return self._http_opener(method, url, headers, data_bytes, req_timeout)

        host = urllib.parse.urlsplit(url).hostname or ""
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=req_timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
                self._cache_host_ip(host)
                return int(resp.status), json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except ValueError:
                parsed = {"ok": False, "error": raw or f"HTTP {exc.code}"}
            return int(exc.code), parsed
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if self._is_dns_resolution_error(exc) and host:
                now = time.time()
                cached = self._resolved_ip_cache.get(host)
                tried: set[str] = set()
                last_exc: BaseException = exc

                def _try_ip(ip_addr: str) -> tuple[int, dict[str, Any]] | None:
                    nonlocal last_exc
                    tried.add(ip_addr)
                    try:
                        st, body = self._http_json_via_ip(
                            method, url, ip_addr, headers, data_bytes, req_timeout
                        )
                        self._resolved_ip_cache[host] = (ip_addr, time.time())
                        return st, body
                    except (OSError, TimeoutError, http.client.HTTPException) as ip_exc:
                        last_exc = ip_exc
                        return None

                if cached and (now - cached[1]) < 300.0:
                    res = _try_ip(cached[0])
                    if res is not None:
                        return res

                doh_ip = self._resolve_host_via_doh(host, req_timeout)
                if doh_ip and doh_ip not in tried:
                    res = _try_ip(doh_ip)
                    if res is not None:
                        return res

                if cached and cached[0] not in tried:
                    res = _try_ip(cached[0])
                    if res is not None:
                        return res

                return 0, {"ok": False, "error": self._format_network_error(last_exc)}

            return 0, {"ok": False, "error": self._format_network_error(exc)}

    # -------------------- Public Auth & Status APIs --------------------

    def status(self) -> dict[str, Any]:
        with self._lock:
            is_enabled = bool(self.cfg.get("enabled"))
            active_aid = str(getattr(self.emu, "active_account_id", "acct_1") or "acct_1")
            active_uid, _ = self._account_user_id_and_display(active_aid)
            bound_aid = self._bound_account_id() if is_enabled else active_aid
            _, bound_display = self._account_user_id_and_display(bound_aid)
            store = self._bound_store() if is_enabled else self._active_store()
            local_p = store.state.get("player", {}) if store else {}
            return {
                "ok": True,
                "enabled": is_enabled,
                "server_url": str(self.cfg.get("server_url") or DEFAULT_SYNC_HUB_URL),
                "username": str(self.cfg.get("username") or ""),
                "account_id": str(self.cfg.get("account_id") or ""),
                "player_id": str(self.cfg.get("player_id") or ""),
                "bound_account_id": bound_aid,
                "bound_display": bound_display,
                "active_account_id": active_aid,
                "active_user_id": active_uid,
                "device_id": str(self.cfg.get("device_id") or ""),
                "sync_rev": int(self.cfg.get("sync_rev") or 0),
                "last_sync_at": int(self.cfg.get("last_sync_at") or 0),
                "peer_count": len(self._peer_proxies),
                "pending_events": len(self.cfg.get("outgoing_events", [])),
                "conflict": copy.deepcopy(self.cfg.get("conflict")),
                "last_error": str(self.cfg.get("last_error") or ""),
                "syncing": bool(self._sync_in_flight),
                "sync_policy": copy.deepcopy(self.cfg.get("sync_policy", DEFAULT_SYNC_POLICY)),
                "local_summary": {
                    "name": str(local_p.get("PlayerName") or ""),
                    "lv": int(local_p.get("Lv", 1)),
                    "fap": int(local_p.get("FAP", 0)),
                    "is_new": int(local_p.get("IsNewPlayer", 1)),
                },
            }

    def test_connection(self, server_url: str | None = None) -> dict[str, Any]:
        url = _normalize_url(server_url or self.cfg.get("server_url") or DEFAULT_SYNC_HUB_URL)
        t0 = time.perf_counter()
        code, body = self._http_json("GET", f"{url}/health", timeout=6.0)
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        if code == 200 and body.get("ok"):
            with self._lock:
                self.cfg["server_url"] = url
                if isinstance(body.get("sync_policy"), dict):
                    self.cfg["sync_policy"].update(body["sync_policy"])
                self._save_cfg()
            return {"ok": True, "latency_ms": latency_ms, "server_url": url, "info": body}
        return {
            "ok": False,
            "status": code,
            "latency_ms": latency_ms,
            "error": str(body.get("error") or f"HTTP {code}"),
        }

    def register(
        self,
        username: str,
        password: str,
        invite_code: str = "",
        server_url: str | None = None,
    ) -> dict[str, Any]:
        url = _normalize_url(server_url or self.cfg.get("server_url") or DEFAULT_SYNC_HUB_URL)
        with self._lock:
            device_id = str(self.cfg["device_id"])
        code, body = self._http_json(
            "POST",
            f"{url}/auth/register",
            {
                "username": str(username or "").strip(),
                "password": str(password or ""),
                "invite_code": str(invite_code or "").strip(),
                "device_id": device_id,
            },
            timeout=8.0,
        )
        if code not in (200, 201) or not body.get("ok"):
            return {"ok": False, "status": code, "error": str(body.get("error") or f"HTTP {code}")}

        active_aid = str(getattr(self.emu, "active_account_id", "acct_1") or "acct_1")
        with self._lock:
            self.cfg["server_url"] = url
            self.cfg["enabled"] = True
            self.cfg["account_id"] = str(body["account_id"])
            self.cfg["player_id"] = str(body["player_id"])
            self.cfg["local_account_id"] = active_aid
            self.cfg["username"] = str(body["username"])
            self.cfg["token"] = str(body["token"])
            self.cfg["sync_rev"] = int(body.get("sync_rev", 0))
            self.cfg["last_pushed_hash"] = ""
            self.cfg["peers_since_ts"] = 0
            self.cfg["conflict"] = None
            self.cfg["last_error"] = ""
            if isinstance(body.get("sync_policy"), dict):
                self.cfg["sync_policy"].update(body["sync_policy"])
            self._bind_local_player_id(self.cfg["player_id"], active_aid)
            self._save_cfg()

        # Immediately push initial snapshot + pull friends
        sync_res = self.sync_now(ignore_cooldown=True)
        return {
            "ok": True,
            "username": self.cfg["username"],
            "player_id": self.cfg["player_id"],
            "sync_result": sync_res,
        }

    def login(
        self,
        username: str,
        password: str,
        server_url: str | None = None,
    ) -> dict[str, Any]:
        url = _normalize_url(server_url or self.cfg.get("server_url") or DEFAULT_SYNC_HUB_URL)
        with self._lock:
            device_id = str(self.cfg["device_id"])
        code, body = self._http_json(
            "POST",
            f"{url}/auth/login",
            {
                "username": str(username or "").strip(),
                "password": str(password or ""),
                "device_id": device_id,
            },
            timeout=8.0,
        )
        if code != 200 or not body.get("ok"):
            return {"ok": False, "status": code, "error": str(body.get("error") or f"HTTP {code}")}

        cloud_pid = str(body["player_id"])
        cloud_rev = int(body.get("sync_rev", 0))
        has_cloud_save = bool(body.get("has_cloud_save"))
        switched_account = False
        existing_aid = self._find_slot_by_player_id(cloud_pid)
        cur_active_aid = str(getattr(self.emu, "active_account_id", "acct_1") or "acct_1")
        target_aid = existing_aid or cur_active_aid

        with self._lock:
            same_acct = self.cfg.get("account_id") == str(body["account_id"])
            self.cfg["server_url"] = url
            self.cfg["enabled"] = True
            self.cfg["account_id"] = str(body["account_id"])
            self.cfg["player_id"] = cloud_pid
            self.cfg["local_account_id"] = target_aid
            self.cfg["username"] = str(body["username"])
            self.cfg["token"] = str(body["token"])
            if not same_acct:
                self.cfg["sync_rev"] = 0
                self.cfg["last_pushed_hash"] = ""
                self.cfg["peers_since_ts"] = 0
            self.cfg["conflict"] = None
            self.cfg["last_error"] = ""
            if isinstance(body.get("sync_policy"), dict):
                self.cfg["sync_policy"].update(body["sync_policy"])
            if not existing_aid:
                self._bind_local_player_id(cloud_pid, target_aid)
            self._save_cfg()

        if existing_aid and cur_active_aid != target_aid and hasattr(self.emu, "switch_s1_account"):
            self.emu.switch_s1_account(target_aid)
            switched_account = True

        store = self._bound_store()
        local_is_new = int(store.state.get("player", {}).get("IsNewPlayer", 1)) == 1 if store else True
        auto_pulled = False
        if has_cloud_save and local_is_new:
            pull_res = self.pull_cloud_save()
            auto_pulled = bool(pull_res.get("ok"))

        bound_uid, bound_display = self._account_user_id_and_display(target_aid)
        return {
            "ok": True,
            "username": self.cfg["username"],
            "player_id": self.cfg["player_id"],
            "cloud_rev": cloud_rev,
            "has_cloud_save": has_cloud_save,
            "cloud_summary": body.get("cloud_summary", {}),
            "auto_pulled": auto_pulled,
            "needs_choice": bool(has_cloud_save and not local_is_new and not auto_pulled and self.cfg["sync_rev"] < cloud_rev),
            "bound_account_id": target_aid,
            "bound_user_id": bound_uid,
            "bound_display": bound_display,
            "switched_account": switched_account,
        }

    def logout(self) -> dict[str, Any]:
        with self._lock:
            self.cfg["enabled"] = False
            self.cfg["token"] = ""
            self.cfg["local_account_id"] = ""
            self.cfg["conflict"] = None
            self.cfg["last_error"] = ""
            self._save_cfg()
        return {"ok": True}

    # -------------------- Outgoing Events Queue --------------------

    def enqueue_event(self, to_player_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        to_pid = str(to_player_id or "").strip()
        if not to_pid:
            return
        with self._lock:
            if not self.cfg.get("enabled"):
                return
            if to_pid == str(self.cfg.get("player_id") or ""):
                return
            queue = self.cfg.setdefault("outgoing_events", [])
            if len(queue) >= 100:
                queue.pop(0)
            queue.append(
                {
                    "to_player_id": to_pid,
                    "event_type": str(event_type),
                    "payload": copy.deepcopy(payload) if isinstance(payload, dict) else {},
                    "queued_at": int(time.time()),
                }
            )
            if self._outgoing_dirty_since_mono == 0.0:
                self._outgoing_dirty_since_mono = time.monotonic()
            self._save_cfg()

    # -------------------- Core Push + Pull Sync --------------------

    def sync_now(
        self,
        *,
        force_push: bool = False,
        ignore_cooldown: bool = False,
        reason: str = "manual",
    ) -> dict[str, Any]:
        now_m = time.monotonic()
        with self._lock:
            if not self.cfg.get("enabled") or not self.cfg.get("token"):
                return {"ok": False, "error": "Chưa đăng nhập tài khoản Đồng bộ Cloud"}
            if self._sync_in_flight:
                return {"ok": False, "busy": True, "error": "Đang đồng bộ, vui lòng đợi..."}
            if not ignore_cooldown and not force_push:
                cd = float(self.cfg["sync_policy"].get("manual_sync_cooldown_sec", 15))
                if reason == "manual" and self._last_manual_mono > 0 and (now_m - self._last_manual_mono) < cd:
                    wait_s = max(1, int(cd - (now_m - self._last_manual_mono)))
                    return {"ok": False, "throttled": True, "error": f"Vui lòng đợi {wait_s}s trước khi đồng bộ tiếp"}
            self._sync_in_flight = True
            self._last_attempt_mono = now_m
            if reason == "manual":
                self._last_manual_mono = now_m

        try:
            return self._do_sync_locked_flow(force_push=force_push)
        finally:
            with self._lock:
                self._sync_in_flight = False

    def _do_sync_locked_flow(self, *, force_push: bool) -> dict[str, Any]:
        store = self._bound_store()
        if store is None:
            return {"ok": False, "error": "Không tìm thấy hồ sơ cục bộ"}

        with store._lock:
            # Ensure local PlayerId stays bound to Cloud player_id
            cloud_pid = str(self.cfg.get("player_id") or "")
            if cloud_pid and str(store.state.get("player", {}).get("PlayerId", "")) != cloud_pid:
                store.state["player"]["PlayerId"] = cloud_pid
                store.save()
            is_new = int(store.state.get("player", {}).get("IsNewPlayer", 1)) == 1
            save_copy = copy.deepcopy(store.state)
            snapshot = build_public_snapshot(store) if not is_new else None

        save_hash, save_gzip_b64 = compress_save_state(save_copy)

        with self._lock:
            url = str(self.cfg["server_url"])
            token = str(self.cfg["token"])
            base_rev = int(self.cfg.get("sync_rev") or 0)
            device_id = str(self.cfg["device_id"])
            last_hash = str(self.cfg.get("last_pushed_hash") or "")
            outgoing_batch = list(self.cfg.get("outgoing_events", [])[:50])
            ack_batch = list(self.cfg.get("pending_ack_ids", [])[:100])
            peers_since_ts = int(self.cfg.get("peers_since_ts") or 0)

        should_push = (not is_new) and (force_push or save_hash != last_hash or base_rev == 0)
        req_body: dict[str, Any] = {
            "base_rev": base_rev,
            "device_id": device_id,
            "force_push": bool(force_push),
            "peers_since_ts": peers_since_ts,
            "outgoing_events": [
                {
                    "to_player_id": e["to_player_id"],
                    "event_type": e["event_type"],
                    "payload": e.get("payload", {}),
                }
                for e in outgoing_batch
            ],
            "ack_inbox_ids": ack_batch,
        }
        if should_push and snapshot is not None:
            req_body["save_hash"] = save_hash
            req_body["save_gzip_b64"] = save_gzip_b64
            req_body["snapshot"] = snapshot

        code, resp = self._http_json("POST", f"{url}/sync", req_body, token=token)

        if code == 409:
            summary = resp.get("server_summary", {})
            with self._lock:
                self.cfg["conflict"] = summary
                self.cfg["last_error"] = str(resp.get("message") or "Xung đột dữ liệu 2 thiết bị")
                self._save_cfg()
            return {
                "ok": False,
                "conflict": True,
                "status": 409,
                "error": self.cfg["last_error"],
                "server_summary": summary,
                "local_summary": {
                    "name": str(save_copy.get("player", {}).get("PlayerName") or ""),
                    "lv": int(save_copy.get("player", {}).get("Lv", 1)),
                    "fap": int(save_copy.get("player", {}).get("FAP", 0)),
                },
            }

        if code != 200 or not resp.get("ok"):
            err_msg = str(resp.get("error") or f"Đồng bộ thất bại (HTTP {code})")
            with self._lock:
                self.cfg["last_error"] = err_msg
                self._save_cfg()
            return {"ok": False, "status": code, "error": err_msg}

        # Apply returned peers & inbox events
        updated_peers = resp.get("updated_peers") or []
        all_peer_ids = set(str(x) for x in (resp.get("all_peer_ids") or []))
        inbox_events = resp.get("inbox_events") or []
        server_time = int(resp.get("server_time") or time.time())

        applied_ids = self._apply_inbox_events(store, inbox_events)

        with self._lock:
            self.cfg["sync_rev"] = int(resp.get("sync_rev", base_rev))
            if should_push:
                self.cfg["last_pushed_hash"] = save_hash
            self.cfg["last_sync_at"] = server_time
            self.cfg["conflict"] = None
            self.cfg["last_error"] = ""
            # Remove sent outgoing events & acknowledged inbox IDs
            if outgoing_batch:
                self.cfg["outgoing_events"] = self.cfg.get("outgoing_events", [])[len(outgoing_batch):]
                if not self.cfg["outgoing_events"]:
                    self._outgoing_dirty_since_mono = 0.0
            if ack_batch:
                ack_set = set(ack_batch)
                self.cfg["pending_ack_ids"] = [
                    x for x in self.cfg.get("pending_ack_ids", []) if x not in ack_set
                ]
            if applied_ids:
                existing_pending = set(self.cfg.get("pending_ack_ids", []))
                for eid in applied_ids:
                    if eid not in existing_pending:
                        self.cfg.setdefault("pending_ack_ids", []).append(eid)

            # Merge delta peers and prune removed/banned peers
            max_peer_ts = peers_since_ts
            for p_rec in updated_peers:
                pid = str(p_rec.get("player_id") or "")
                if not pid or pid == str(self.cfg.get("player_id") or ""):
                    continue
                self._peers_raw[pid] = p_rec
                pts = int(p_rec.get("updated_at") or 0)
                if pts > max_peer_ts:
                    max_peer_ts = pts
            if all_peer_ids or len(self._peers_raw) > 0:
                # Only prune if server returned explicit all_peer_ids list
                if "all_peer_ids" in resp:
                    self._peers_raw = {
                        pid: rec for pid, rec in self._peers_raw.items() if pid in all_peer_ids
                    }
            self.cfg["peers_since_ts"] = max_peer_ts
            self._rebuild_peer_proxies()
            self._save_peers()
            self._save_cfg()
            peer_count = len(self._peer_proxies)

        return {
            "ok": True,
            "pushed": bool(resp.get("pushed")),
            "sync_rev": int(self.cfg["sync_rev"]),
            "peer_count": peer_count,
            "updated_peers_count": len(updated_peers),
            "inbox_applied": len(applied_ids),
            "server_time": server_time,
        }

    def pull_cloud_save(self) -> dict[str, Any]:
        """Download full save from Cloud, create local safety backup, and apply into active profile."""
        with self._lock:
            if not self.cfg.get("enabled") or not self.cfg.get("token"):
                return {"ok": False, "error": "Chưa đăng nhập tài khoản Đồng bộ Cloud"}
            url = str(self.cfg["server_url"])
            token = str(self.cfg["token"])

        code, resp = self._http_json("GET", f"{url}/sync/pull_save", token=token, timeout=8.0)
        if code != 200 or not resp.get("ok"):
            return {"ok": False, "status": code, "error": str(resp.get("error") or f"HTTP {code}")}

        try:
            restored_state = decompress_save_state(str(resp["save_gzip_b64"]))
        except Exception as exc:
            return {"ok": False, "error": f"Giải nén bản lưu Cloud thất bại: {exc}"}

        store = self._bound_store()
        if store is None:
            return {"ok": False, "error": "Không tìm thấy hồ sơ cục bộ"}

        # Preserve local Guild binding (guilds stay 100% local, never overwritten by Cloud)
        with store._lock:
            if self.persist and getattr(store, "state_path", None) is not None and store.state_path.exists():
                bak_path = store.state_path.with_name(f"{store.state_path.name}.pre_cloud_pull.bak")
                try:
                    bak_path.write_bytes(store.state_path.read_bytes())
                except OSError:
                    pass
            local_player = store.state.get("player", {})
            local_guild_id = local_player.get("GuildId")
            local_guild_name = local_player.get("GuildName")
            local_guild_state = copy.deepcopy(store.state.get("guild"))

            store.state = restored_state
            store.state.setdefault("player", {})["PlayerId"] = str(resp["player_id"])
            if local_guild_id is not None:
                store.state["player"]["GuildId"] = local_guild_id
            if local_guild_name is not None:
                store.state["player"]["GuildName"] = local_guild_name
            if local_guild_state is not None:
                store.state["guild"] = local_guild_state
            store.save()
            new_hash, _ = compress_save_state(store.state)

        with self._lock:
            self.cfg["sync_rev"] = int(resp.get("sync_rev", 0))
            self.cfg["last_pushed_hash"] = new_hash
            self.cfg["conflict"] = None
            self.cfg["last_error"] = ""
            self._save_cfg()

        # Also pull peers right away
        self.sync_now(ignore_cooldown=True, reason="post_pull")
        bound_aid = self._bound_account_id()
        bound_uid, _ = self._account_user_id_and_display(bound_aid)
        return {
            "ok": True,
            "sync_rev": int(resp.get("sync_rev", 0)),
            "summary": resp.get("summary", {}),
            "active_account_id": bound_aid,
            "active_user_id": bound_uid,
        }

    # -------------------- Inbox Event Application --------------------

    def _apply_inbox_events(self, store: Any, events: list[dict[str, Any]]) -> list[int]:
        if not events:
            return []
        applied_ids: list[int] = []
        with self._lock:
            already_seen = set(int(x) for x in self.cfg.get("applied_inbox_ids", []))

        with store._lock:
            social = store._social_state()
            changed = False
            now_ts = int(time.time())
            for ev in events:
                eid = int(ev.get("id") or 0)
                if eid <= 0:
                    continue
                if eid in already_seen:
                    applied_ids.append(eid)
                    continue

                from_pid = str(ev.get("from_player_id") or "")
                ev_type = str(ev.get("event_type") or "")
                payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}

                if ev_type == "friend_req":
                    if from_pid not in {str(x) for x in social.get("friends", [])}:
                        sender_card = {
                            "PlayerId": from_pid,
                            "Name": str(payload.get("from_name") or "Bạn bè"),
                            "Lv": int(payload.get("from_lv") or 1),
                            "FAP": int(payload.get("from_fap") or 0),
                            "HeadImageId": int(payload.get("from_head") or 12011002),
                            "FashionModelId": int(payload.get("from_fashion") or 0),
                        }
                        store._push_friend_mail_message(
                            social,
                            msg_type=1,
                            sender_card=sender_card,
                            content=str(payload.get("content") or "Hãy kết bạn cùng phiêu lưu nhé!"),
                            now=int(ev.get("created_at") or now_ts),
                        )
                        changed = True
                elif ev_type == "friend_accept":
                    if from_pid and from_pid not in {str(x) for x in social.get("friends", [])}:
                        social.setdefault("friends", []).append(from_pid)
                        social["enemies"] = [x for x in social.get("enemies", []) if str(x) != from_pid]
                        changed = True
                elif ev_type == "friend_remove":
                    before = len(social.get("friends", []))
                    social["friends"] = [x for x in social.get("friends", []) if str(x) != from_pid]
                    if len(social["friends"]) != before:
                        changed = True
                elif ev_type == "send_sta":
                    store._social_push_sta_gift(social, from_pid, int(ev.get("created_at") or now_ts))
                    changed = True
                elif ev_type == "friend_msg":
                    sender_card = {
                        "PlayerId": from_pid,
                        "Name": str(payload.get("from_name") or "Bạn bè"),
                        "Lv": int(payload.get("from_lv") or 1),
                        "FAP": int(payload.get("from_fap") or 0),
                        "HeadImageId": int(payload.get("from_head") or 12011002),
                        "FashionModelId": int(payload.get("from_fashion") or 0),
                    }
                    store._push_friend_mail_message(
                        social,
                        msg_type=2,
                        sender_card=sender_card,
                        content=str(payload.get("content") or ""),
                        now=int(ev.get("created_at") or now_ts),
                    )
                    changed = True
                elif ev_type == "pvp_challenge_log":
                    att_name = str(payload.get("attacker_name") or "Đối thủ")
                    att_fap = int(payload.get("attacker_fap") or 0)
                    store._push_player_email(
                        2,
                        "Chiến báo Đấu Trường Cloud",
                        f"{att_name} (Lực chiến {att_fap:,}) đã thách đấu và đánh bại đội hình của bạn!",
                        send_player_id=from_pid,
                        send_player_name=att_name,
                        sub_module_id=2502,
                        head_image_id=0,
                        fashion_model_id=0,
                    )
                    changed = True

                already_seen.add(eid)
                applied_ids.append(eid)

            if changed:
                store.save()

        with self._lock:
            # Keep bounded ring buffer of last 500 applied inbox IDs to prevent duplicate application
            merged_seen = sorted(already_seen)[-500:]
            self.cfg["applied_inbox_ids"] = merged_seen
        return applied_ids

    # -------------------- Smart Throttled Background Triggers --------------------

    def maybe_trigger_async_sync(self, module_name: str, method_name: str = "") -> bool:
        """
        Called after RPC execution in standalone/hybrid mode.
        Spawns a non-blocking background sync ONLY when appropriate cooldowns allow:
          1. On Player.Login: sync if never synced or > auto_sync_interval_sec (30m) elapsed.
          2. On Social/LeaderBoard/PVP zone RPCs: sync if > zone_trigger_cooldown_sec (3m) elapsed.
          3. On pending outgoing events: flush after outgoing_debounce_sec (20s) batch window.
          4. General background cadence: > auto_sync_interval_sec (30m) elapsed.
        """
        now_m = time.monotonic()
        with self._lock:
            if not self.cfg.get("enabled") or not self.cfg.get("token"):
                return False
            bound_aid = str(self.cfg.get("local_account_id") or "").strip()
            if bound_aid and str(getattr(self.emu, "active_account_id", "") or "") != bound_aid:
                return False
            if self._sync_in_flight or self.cfg.get("conflict"):
                return False

            pol = self.cfg.get("sync_policy", DEFAULT_SYNC_POLICY)
            auto_cd = float(pol.get("auto_sync_interval_sec", 1800))
            zone_cd = float(pol.get("zone_trigger_cooldown_sec", 180))
            out_debounce = float(pol.get("outgoing_debounce_sec", 20))

            since_attempt = (now_m - self._last_attempt_mono) if self._last_attempt_mono > 0 else 1e9
            since_zone = (now_m - self._last_zone_trigger_mono) if self._last_zone_trigger_mono > 0 else 1e9

            should_fire = False
            reason = "auto"

            if module_name == "Player" and method_name in ("Login", "Login_ForTest"):
                if int(self.cfg.get("last_sync_at") or 0) == 0 or since_attempt >= auto_cd:
                    should_fire = True
                    reason = "login"
            elif module_name in ZONE_SYNC_MODULES:
                if since_zone >= zone_cd and since_attempt >= zone_cd:
                    should_fire = True
                    reason = f"zone:{module_name}"
                    self._last_zone_trigger_mono = now_m
            elif self.cfg.get("outgoing_events") and self._outgoing_dirty_since_mono > 0:
                if (now_m - self._outgoing_dirty_since_mono) >= out_debounce and since_attempt >= out_debounce:
                    should_fire = True
                    reason = "outgoing_flush"
            elif since_attempt >= auto_cd:
                should_fire = True
                reason = "periodic"

            if not should_fire:
                return False

        t = threading.Thread(
            target=self.sync_now,
            kwargs={"force_push": False, "ignore_cooldown": True, "reason": reason},
            name=f"hybrid-sync-{reason}",
            daemon=True,
        )
        t.start()
        return True
