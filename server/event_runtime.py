#!/usr/bin/env python3
"""Reusable Event Clock, Event Runtime, and Event Archive core for InuYasha R7.5+."""

from __future__ import annotations

import copy
import datetime as _dt
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

DEFAULT_VN_TZ_OFFSET_HOURS = 7


class EventClock:
    """Configurable, thread-safe game event clock decoupled from OS time.

    Supports three modes:
    - ``realtime``: wall-clock ``time.time()``
    - ``offset``: wall-clock ``time.time() + offset_sec``
    - ``fixed``: deterministic fixed Unix timestamp ``fixed_ts``
    """

    def __init__(
        self,
        *,
        mode: str = "realtime",
        offset_sec: int = 0,
        fixed_ts: int | None = None,
        tz_offset_hours: int = DEFAULT_VN_TZ_OFFSET_HOURS,
    ) -> None:
        self._lock = threading.RLock()
        self.tz_offset_hours = int(tz_offset_hours)
        self.mode = mode if mode in ("realtime", "offset", "fixed") else "realtime"
        self.offset_sec = int(offset_sec)
        self.fixed_ts = int(fixed_ts) if fixed_ts is not None else int(time.time())

    def tz(self) -> _dt.timezone:
        return _dt.timezone(_dt.timedelta(hours=self.tz_offset_hours))

    def now(self) -> int:
        with self._lock:
            if self.mode == "fixed":
                return int(self.fixed_ts)
            if self.mode == "offset":
                return int(time.time()) + int(self.offset_sec)
            return int(time.time())

    def dt(self, ts: int | None = None) -> _dt.datetime:
        val = self.now() if ts is None else int(ts)
        return _dt.datetime.fromtimestamp(val, tz=self.tz())

    def today_str(self, ts: int | None = None) -> str:
        return self.dt(ts).strftime("%Y-%m-%d")

    def week_str(self, ts: int | None = None) -> str:
        iso = self.dt(ts).isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    def weekday(self, ts: int | None = None) -> int:
        """Return ISO weekday 1 (Monday) .. 7 (Sunday) in configured timezone."""
        return self.dt(ts).isoweekday()

    def seconds_since_midnight(self, ts: int | None = None) -> int:
        d = self.dt(ts)
        return d.hour * 3600 + d.minute * 60 + d.second

    def time_of_day_fraction(self, ts: int | None = None) -> float:
        return self.seconds_since_midnight(ts) / 86400.0

    def midnight_ts(self, ts: int | None = None) -> int:
        d = self.dt(ts)
        mid = _dt.datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=self.tz())
        return int(mid.timestamp())

    def next_midnight_ts(self, ts: int | None = None) -> int:
        return self.midnight_ts(ts) + 86400

    def set_realtime(self) -> dict[str, Any]:
        with self._lock:
            self.mode = "realtime"
            self.offset_sec = 0
            return self.to_dict()

    def set_offset(self, offset_sec: int) -> dict[str, Any]:
        with self._lock:
            self.mode = "offset"
            self.offset_sec = int(offset_sec)
            return self.to_dict()

    def set_fixed(self, fixed_ts: int) -> dict[str, Any]:
        with self._lock:
            self.mode = "fixed"
            self.fixed_ts = int(fixed_ts)
            return self.to_dict()

    def advance(self, delta_sec: int) -> dict[str, Any]:
        with self._lock:
            delta = int(delta_sec)
            if self.mode == "fixed":
                self.fixed_ts += delta
            elif self.mode == "offset":
                self.offset_sec += delta
            else:
                self.mode = "offset"
                self.offset_sec = delta
            return self.to_dict()

    def set_tz_offset(self, tz_offset_hours: int) -> dict[str, Any]:
        with self._lock:
            self.tz_offset_hours = int(tz_offset_hours)
            return self.to_dict()

    def apply_config(self, cfg: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if "tz_offset_hours" in cfg:
                self.tz_offset_hours = int(cfg["tz_offset_hours"])
            mode = str(cfg.get("mode", self.mode))
            if mode == "fixed":
                self.mode = "fixed"
                self.fixed_ts = int(cfg.get("fixed_ts", self.now()))
            elif mode == "offset":
                self.mode = "offset"
                self.offset_sec = int(cfg.get("offset_sec", self.offset_sec))
            else:
                self.mode = "realtime"
                self.offset_sec = 0
            return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            cur = self.now()
            return {
                "mode": self.mode,
                "offset_sec": int(self.offset_sec),
                "fixed_ts": int(self.fixed_ts),
                "tz_offset_hours": int(self.tz_offset_hours),
                "now": cur,
                "local_iso": self.dt(cur).isoformat(),
                "today": self.today_str(cur),
            }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EventClock":
        if not isinstance(data, dict):
            return cls()
        return cls(
            mode=str(data.get("mode", "realtime")),
            offset_sec=int(data.get("offset_sec", 0)),
            fixed_ts=data.get("fixed_ts"),
            tz_offset_hours=int(data.get("tz_offset_hours", DEFAULT_VN_TZ_OFFSET_HOURS)),
        )


STATUS_UPCOMING = "upcoming"
STATUS_ACTIVE = "active"
STATUS_ENDED = "ended"


@dataclass
class EventDefinition:
    """Static / config-driven definition of a recoverable activity or event."""

    event_id: str
    module_sub: int
    name: str
    schedule_type: str  # "permanent" | "daily" | "weekly" | "timed"
    open_lv: int = 1
    need_vip: int = 0
    source_origin: str = "verified_original"
    time_windows: list[tuple[float, float]] = field(default_factory=list)
    weekdays: list[int] = field(default_factory=list)
    default_start_ts: int | None = None
    default_end_ts: int | None = None
    duration_sec: int = 259200  # 3 days default for timed/archive periods
    archive_eligible: bool = False
    timed_open_info: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventEvaluation:
    """Resolved live status & active instance metadata for an event."""

    event_id: str
    module_sub: int
    status: str  # STATUS_UPCOMING | STATUS_ACTIVE | STATUS_ENDED
    unlocked: bool
    eligible: bool  # status == STATUS_ACTIVE and unlocked
    instance_id: str | None
    start_ts: int | None
    end_ts: int | None
    remaining_sec: int
    active_window_idx: int | None = None
    archive_mode: str = "scheduled"
    reason: str = ""


def _parse_module_open_lv(game_data: dict[str, Any], module_sub: int, default_lv: int = 1) -> int:
    ms = game_data.get("module_subs", {}).get(str(module_sub), {})
    return int(ms.get("openLv", default_lv) or default_lv)


def build_default_event_registry(game_data: dict[str, Any]) -> dict[str, EventDefinition]:
    """Construct config-driven event definitions from extracted VN Config tables."""
    vit_cfg = game_data.get("vit_config", {})
    dinner_windows: list[tuple[float, float]] = []
    for prefix in ("firstReceive", "secondReceive", "dinner"):
        b = float(vit_cfg.get(f"{prefix}BeginTime", 0.0) or 0.0)
        e = float(vit_cfg.get(f"{prefix}EndTime", 0.0) or 0.0)
        if e > b:
            dinner_windows.append((b, e))
    if not dinner_windows:
        dinner_windows = [
            (0.5, 0.583333333333),
            (0.75, 0.833333333333),
            (0.875, 0.958333333333),
        ]

    xxbz_models = game_data.get("xxbz_model", {})
    xxbz_lvs = [int(v.get("needLv", 28)) for v in xxbz_models.values() if int(v.get("needLv", 0)) > 0]
    xxbz_open_lv = max(_parse_module_open_lv(game_data, 4600, 28), min(xxbz_lvs, default=28))

    registry: dict[str, EventDefinition] = {
        "daily_dinner": EventDefinition(
            event_id="daily_dinner",
            module_sub=2706,
            name="Tiệc Hào Hoa (Thể Lực/Hoạt Lực Hằng Ngày)",
            schedule_type="daily",
            open_lv=_parse_module_open_lv(game_data, 2706, 1),
            source_origin="verified_original",
            time_windows=dinner_windows,
            duration_sec=86400,
        ),
        "daily_task": EventDefinition(
            event_id="daily_task",
            module_sub=3000,
            name="Nhiệm Vụ Ngày",
            schedule_type="daily",
            open_lv=_parse_module_open_lv(game_data, 3000, 25),
            source_origin="verified_original",
            duration_sec=86400,
        ),
        "xxbz": EventDefinition(
            event_id="xxbz",
            module_sub=4600,
            name="Kho Báu Bí Ẩn",
            schedule_type="daily",
            open_lv=xxbz_open_lv,
            source_origin="verified_original",
            duration_sec=86400,
        ),
        "lucky_cat": EventDefinition(
            event_id="lucky_cat",
            module_sub=2711,
            name="Chiêu Tài Miêu",
            schedule_type="daily",
            open_lv=_parse_module_open_lv(game_data, 2711, 21),
            source_origin="verified_original",
            duration_sec=86400,
        ),
        "goddess_kiss": EventDefinition(
            event_id="goddess_kiss",
            module_sub=2303,
            name="Hứa Nguyện (Goddess Kiss)",
            schedule_type="daily",
            open_lv=_parse_module_open_lv(game_data, 2303, 30),
            source_origin="verified_original",
            duration_sec=86400,
        ),
        "online_reward": EventDefinition(
            event_id="online_reward",
            module_sub=3700,
            name="Quà Online Đếm Ngược",
            schedule_type="daily",
            open_lv=1,
            source_origin="verified_original",
            duration_sec=86400,
        ),
        "month_sign": EventDefinition(
            event_id="month_sign",
            module_sub=2712,
            name="Điểm Danh Tháng",
            schedule_type="daily",
            open_lv=1,
            source_origin="verified_original",
            duration_sec=86400,
        ),
        "timed_critical_tasks": EventDefinition(
            event_id="timed_critical_tasks",
            module_sub=4700,
            name="Nhiệm Vụ Bạo Kích Hạn Giờ",
            schedule_type="daily",
            open_lv=1,
            source_origin="cross_region_tw_1.4_adapted",
            duration_sec=86400,
        ),
        "time_spike": EventDefinition(
            event_id="time_spike",
            module_sub=6800,
            name="Giờ Vàng Flash Sale",
            schedule_type="daily",
            open_lv=1,
            source_origin="verified_original",
            duration_sec=86400,
        ),
        "time_miaosha": EventDefinition(
            event_id="time_miaosha",
            module_sub=7000,
            name="Vua Giờ Vàng (MiaoSha)",
            schedule_type="daily",
            open_lv=1,
            source_origin="server_modeled_preset",
            duration_sec=86400,
        ),
        "random_red_bag": EventDefinition(
            event_id="random_red_bag",
            module_sub=5501,
            name="Lì Xì Liên Server",
            schedule_type="daily",
            open_lv=1,
            source_origin="server_modeled_preset",
            duration_sec=86400,
        ),
        "yiyuan_duobao": EventDefinition(
            event_id="yiyuan_duobao",
            module_sub=7800,
            name="Di Tích Đoạt Bảo",
            schedule_type="daily",
            open_lv=1,
            source_origin="server_modeled_preset",
            duration_sec=86400,
        ),
        "open_contest": EventDefinition(
            event_id="open_contest",
            module_sub=7900,
            name="Đua Top Chiến Lực Mở Server 7 Ngày",
            schedule_type="daily",
            open_lv=1,
            source_origin="verified_original",
            duration_sec=86400,
        ),
        "shiwan_diamond": EventDefinition(
            event_id="shiwan_diamond",
            module_sub=8200,
            name="Mười Vạn Kim Cương",
            schedule_type="permanent",
            open_lv=1,
            source_origin="verified_original",
            duration_sec=86400,
        ),
        "early_task": EventDefinition(
            event_id="early_task",
            module_sub=2600,
            name="Nhiệm Vụ Mở Server (Earlytask)",
            schedule_type="permanent",
            open_lv=1,
            source_origin="cross_region_tw_1.4_adapted",
            duration_sec=86400,
        ),
        "limit_trader": EventDefinition(
            event_id="limit_trader",
            module_sub=4300,
            name="Thương Nhân Hạn Giờ",
            schedule_type="daily",
            open_lv=1,
            source_origin="cross_region_tw_1.4_adapted",
            duration_sec=86400,
        ),
    }

    # TimedActivityScene (4400) sub-modules (4401..4432)
    timed_scene_specs: list[tuple[str, int, str, str, dict[str, Any]]] = [
        ("timed_charge_single", 4401, "Nạp Đơn Nhận Quà", "server_modeled_preset", {}),
        ("timed_charge_total", 4402, "Nạp Tích Lũy", "server_modeled_preset", {}),
        ("timed_use_total", 4403, "Tiêu Phí Tích Lũy", "server_modeled_preset", {}),
        ("timed_accum_days", 4405, "Ngày Nạp Liên Tục", "server_modeled_preset", {}),
        ("timed_exchange", 4406, "Đổi Thưởng Hạn Giờ", "server_modeled_preset", {}),
        ("timed_double_diamond", 4407, "Nạp Nhân Đôi", "server_modeled_preset", {}),
        ("timed_pray_tree", 4409, "Cây Ước Nguyện", "server_modeled_preset", {}),
        ("timed_xssb", 4410, "Thần Binh Giới Hạn", "cross_region_tw_1.4_adapted", {}),
        ("timed_slot", 4412, "Kho Báu Quay Thưởng", "server_modeled_preset", {}),
        ("timed_welfare_dwdh", 4414, "Phúc Lợi Đấu Võ Đại Hội", "verified_original", {"RefNum": 2}),
        ("timed_welfare_ycjk", 4415, "Phúc Lợi Kho Vàng", "verified_original", {"RefNum": 2}),
        ("timed_welfare_equip", 4416, "Phúc Lợi Trang Bị 80%", "verified_original", {"RefNum": 80}),
        ("timed_welfare_hero", 4417, "Phúc Lợi Chiêu Mộ 80%", "verified_original", {"RefNum": 80}),
        ("timed_welfare_equip_crit", 4419, "Bạo Kích Triệu Hồi Trang Bị", "verified_original", {"RefNum": 100}),
        ("timed_recharge_rank", 4421, "BXH Nạp Kim Cương", "server_modeled_preset", {}),
        ("timed_consume_rank", 4422, "BXH Tiêu Kim Cương", "server_modeled_preset", {}),
        ("timed_smash_egg", 4426, "Đập Trứng Vàng", "server_modeled_preset", {}),
        ("timed_day_login", 4427, "Đăng Nhập Tích Lũy", "server_modeled_preset", {}),
        ("timed_points_mall", 4428, "Shop Điểm Nạp", "server_modeled_preset", {}),
        ("timed_charge_gift", 4429, "Quà Nạp Tự Chọn", "server_modeled_preset", {}),
        ("timed_active_rank", 4430, "BXH Năng Động", "verified_original", {}),
        ("timed_money_tree", 4432, "Cây Tiền May Mắn", "server_modeled_preset", {}),
    ]
    for ev_id, mod_sub, title, origin, extra_info in timed_scene_specs:
        registry[ev_id] = EventDefinition(
            event_id=ev_id,
            module_sub=mod_sub,
            name=title,
            schedule_type="timed",
            open_lv=1,
            source_origin=origin,
            duration_sec=259200,
            archive_eligible=True,
            timed_open_info={
                "ActivityId": mod_sub,
                "Name": title,
                "ExtraInfo": extra_info,
            },
            metadata={
                "activity_id": mod_sub,
                "extra_info": extra_info,
                "assets_complete": True,
            },
        )

    # Verified TimedRecruit banners from TimedRecruitModel (9300).
    # 81, 82, and 83 (with supplemented VN/ZH/TH assets) have 100% UI/combat/icon assets.
    tr_names = {
        81: "Sesshomaru Thần Tướng",
        82: "InuYasha Thức Tỉnh",
        83: "Tứ Đấu Thần / Inu Kimi",
        84: "Giới Hạn 84 (Thiếu icon)",
        85: "Giới Hạn 85 (Thiếu icon)",
        86: "Giới Hạn 86 (Thiếu icon)",
    }
    tr_complete_assets = {81, 82, 83}
    tr_models = game_data.get("timed_recruit_model", {})
    tr_open_lv = _parse_module_open_lv(game_data, 9300, 1)
    for key in sorted(tr_models, key=lambda x: int(x)):
        act_id = int(key)
        row = tr_models[key]
        btn_pic = str(row.get("btnPic", "") or "")
        gold_hero_box = int(row.get("goldHeroModelID", 16060008))
        has_assets = act_id in tr_complete_assets and bool(btn_pic)
        ev_id = f"timed_recruit:{act_id}"
        registry[ev_id] = EventDefinition(
            event_id=ev_id,
            module_sub=9300,
            name=f"Chiêu Mộ Thần Tướng: {tr_names.get(act_id, str(act_id))}",
            schedule_type="timed",
            open_lv=tr_open_lv,
            source_origin="verified_original" if has_assets else "partial_assets",
            duration_sec=259200,  # 3 days
            archive_eligible=has_assets,
            timed_open_info={
                "ActivityId": act_id,
                "Name": tr_names.get(act_id, f"TimedRecruit {act_id}"),
                "ExtraInfo": "",
            },
            metadata={
                "activity_id": act_id,
                "gold_hero_model_id": gold_hero_box,
                "btn_pic": btn_pic,
                "assets_complete": has_assets,
            },
        )
    return registry


class EventRuntime:
    """Manages event schedules, Event Archive modes, instances, progress, and claim locks."""

    DEFAULT_ROTATION_ANCHOR_TS = 1767200400  # 2026-01-01 00:00:00 UTC+7
    DEFAULT_CONCURRENT_EVENTS: list[str] = [
        "timed_recruit:81",
        "timed_recruit:82",
        "timed_recruit:83",
        "timed_money_tree",
        "timed_pray_tree",
        "timed_smash_egg",
        "timed_slot",
        "timed_xssb",
        "timed_charge_single",
        "timed_charge_total",
        "timed_use_total",
        "timed_accum_days",
        "timed_exchange",
        "timed_double_diamond",
        "timed_welfare_equip",
        "timed_welfare_hero",
        "timed_recharge_rank",
        "timed_consume_rank",
        "timed_day_login",
        "timed_points_mall",
        "timed_charge_gift",
        "timed_active_rank",
    ]

    def __init__(
        self,
        clock: EventClock,
        registry: dict[str, EventDefinition],
        state_container: dict[str, Any] | None = None,
    ) -> None:
        self.clock = clock
        self.registry = registry
        self._state = state_container if state_container is not None else {}
        self.ensure_state(self._state)

    def bind_state(self, state_container: dict[str, Any]) -> None:
        self._state = state_container
        self.ensure_state(self._state)

    @classmethod
    def ensure_state(cls, state: dict[str, Any]) -> dict[str, Any]:
        rt = state.setdefault("event_runtime", {})
        ac = rt.setdefault("archive_config", {})
        ac.setdefault("mode", "concurrent")  # R7.6+ default: concurrent multi-banner + 00:00 UTC+7 daily reset
        ac.setdefault("r76_migrated", True)
        ac.setdefault("concurrent_events", list(cls.DEFAULT_CONCURRENT_EVENTS))
        if not ac.get("r79_migrated"):
            cur_list = [str(x) for x in ac.get("concurrent_events", [])]
            for eid in cls.DEFAULT_CONCURRENT_EVENTS:
                if eid not in cur_list:
                    cur_list.append(eid)
            ac["concurrent_events"] = cur_list
            ac["r79_migrated"] = True
        ac.setdefault("rotation_pool", ["timed_recruit:81", "timed_recruit:82", "timed_recruit:83"])
        if not ac.get("r7181_migrated"):
            cur_list = [str(x) for x in ac.get("concurrent_events", [])]
            if "timed_recruit:83" not in cur_list:
                if "timed_recruit:82" in cur_list:
                    cur_list.insert(cur_list.index("timed_recruit:82") + 1, "timed_recruit:83")
                else:
                    cur_list.append("timed_recruit:83")
            ac["concurrent_events"] = cur_list
            rot_pool = [str(x) for x in ac.get("rotation_pool", [])]
            if "timed_recruit:83" not in rot_pool:
                rot_pool.append("timed_recruit:83")
            ac["rotation_pool"] = rot_pool
            ac["r7181_migrated"] = True
        ac.setdefault("period_mode", "daily_utc7")
        ac.setdefault("period_sec", 86400)
        ac.setdefault("period_anchor_ts", cls.DEFAULT_ROTATION_ANCHOR_TS)
        ac.setdefault("period_overrides", {})
        ac.setdefault("carry_over_pity", False)
        ac.setdefault("carry_over_policy", {})
        ac.setdefault("manual_reset_seq", {})
        ac.setdefault("rotation_duration_sec", 259200)
        ac.setdefault("rotation_anchor_ts", cls.DEFAULT_ROTATION_ANCHOR_TS)
        ac.setdefault("manual_active", None)
        ac.setdefault("manual_seq", 0)
        ac.setdefault("scheduled_windows", {})
        rt.setdefault("instances", {})
        rt.setdefault("active_instance_by_event", {})
        rt.setdefault("archive_history", [])
        return rt

    @property
    def rt(self) -> dict[str, Any]:
        return self.ensure_state(self._state)

    @property
    def archive_cfg(self) -> dict[str, Any]:
        return self.rt["archive_config"]

    def _finalize_instance_to_history(self, instance_id: str, reason: str, ended_at: int) -> None:
        instances = self.rt["instances"]
        inst = instances.get(instance_id)
        if not inst or inst.get("archived"):
            return
        inst["archived"] = True
        inst["archived_at"] = int(ended_at)
        inst["archive_reason"] = reason
        snap = copy.deepcopy(inst)
        history = self.rt["archive_history"]
        history.append(snap)
        if len(history) > 200:
            self.rt["archive_history"] = history[-200:]

    def _get_or_create_instance(
        self,
        event_id: str,
        instance_id: str,
        start_ts: int | None,
        end_ts: int | None,
        *,
        mode: str = "scheduled",
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Return active instance for instance_id and list of newly ended old instances."""
        rt = self.rt
        instances = rt["instances"]
        active_map = rt["active_instance_by_event"]
        now = self.clock.now()
        ended_previous: list[dict[str, Any]] = []
        initial_progress: dict[str, Any] = {}

        prev_id = active_map.get(event_id)
        if prev_id and prev_id != instance_id and prev_id in instances:
            self._finalize_instance_to_history(prev_id, "period_rotated", now)
            previous = instances[prev_id]
            ended_previous.append(previous)
            if event_id.startswith("timed_recruit:") and self.is_carry_over_pity(event_id):
                progress = previous.get("progress", {})
                initial_progress = {
                    key: progress[key]
                    for key in ("out_zi_count", "bless_num", "bless_r", "bless_unlocked")
                    if key in progress
                }

        # Only close other same-module events in exclusive single-banner archive modes
        ev_def = self.registry.get(event_id)
        if ev_def and ev_def.schedule_type == "timed" and mode in ("rotating", "manual"):
            for other_ev, other_iid in list(active_map.items()):
                if other_ev != event_id and other_iid != instance_id:
                    other_def = self.registry.get(other_ev)
                    if other_def and other_def.module_sub == ev_def.module_sub:
                        other_inst = instances.get(other_iid)
                        if other_inst and not other_inst.get("archived"):
                            self._finalize_instance_to_history(other_iid, "replaced_by_archive_event", now)
                            ended_previous.append(other_inst)

        if instance_id not in instances:
            instances[instance_id] = {
                "instance_id": instance_id,
                "event_id": event_id,
                "module_sub": ev_def.module_sub if ev_def else 0,
                "mode": mode,
                "started_at": int(start_ts if start_ts is not None else now),
                "end_at": int(end_ts) if end_ts is not None else None,
                "created_at": now,
                "progress": initial_progress,
                "claimed": [],
                "claim_meta": {},
                "settled": False,
                "archived": False,
            }
        else:
            if start_ts is not None:
                instances[instance_id]["started_at"] = int(start_ts)
            if end_ts is not None:
                instances[instance_id]["end_at"] = int(end_ts)

        active_map[event_id] = instance_id
        return instances[instance_id], ended_previous

    def _resolve_timed_window(self, event_id: str, ev_def: EventDefinition, now: int) -> tuple[str, str | None, int | None, int | None, str]:
        ac = self.archive_cfg
        mode = str(ac.get("mode", "concurrent"))
        reset_seq = int(ac.get("manual_reset_seq", {}).get(event_id, 0))
        seq_suffix = f":r{reset_seq}" if reset_seq > 0 else ""

        if mode == "concurrent":
            active_list = [str(eid) for eid in ac.get("concurrent_events", ["timed_recruit:81", "timed_recruit:82"])]
            if event_id not in active_list:
                prev_iid = self.rt["active_instance_by_event"].get(event_id)
                return STATUS_ENDED, prev_iid, None, None, "concurrent"
            overrides = ac.get("period_overrides", {})
            period_mode = str(ac.get("period_mode", "daily_utc7"))
            custom_dur = overrides.get(event_id)
            if custom_dur is None and period_mode == "fixed_sec":
                custom_dur = ac.get("period_sec", 86400)
            if custom_dur is not None:
                dur = max(60, int(custom_dur))
                anchor = int(ac.get("period_anchor_ts", self.DEFAULT_ROTATION_ANCHOR_TS))
                slot_idx = max(0, (now - anchor) // dur) if now >= anchor else 0
                s_ts = anchor + slot_idx * dur
                e_ts = s_ts + dur
                iid = f"{event_id}:p{dur}:{slot_idx}{seq_suffix}"
            else:
                day_str = self.clock.today_str(now)
                s_ts = self.clock.midnight_ts(now)
                e_ts = self.clock.next_midnight_ts(now)
                iid = f"{event_id}:d:{day_str}{seq_suffix}"
            return STATUS_ACTIVE, iid, s_ts, e_ts, "concurrent"

        if mode == "manual":
            manual = ac.get("manual_active")
            if isinstance(manual, dict) and manual.get("event_id") == event_id:
                s_ts = int(manual.get("start_ts", 0))
                e_ts = int(manual.get("end_ts", 0))
                iid = str(manual.get("instance_id", ""))
                if now < s_ts:
                    return STATUS_UPCOMING, iid, s_ts, e_ts, "manual"
                if e_ts > 0 and now >= e_ts:
                    return STATUS_ENDED, iid, s_ts, e_ts, "manual"
                return STATUS_ACTIVE, iid, s_ts, e_ts, "manual"
            # Check if there is an existing manual instance for this event that ended
            cur_iid = self.rt["active_instance_by_event"].get(event_id)
            if cur_iid and cur_iid in self.rt["instances"]:
                inst = self.rt["instances"][cur_iid]
                return STATUS_ENDED, cur_iid, inst.get("started_at"), inst.get("end_at"), "manual"
            return STATUS_ENDED, None, None, None, "manual"

        if mode == "rotating":
            pool = [str(eid) for eid in ac.get("rotation_pool", []) if str(eid) in self.registry]
            if not pool or event_id not in pool:
                return STATUS_ENDED, None, None, None, "rotating"
            dur = max(60, int(ac.get("rotation_duration_sec", ev_def.duration_sec or 259200)))
            anchor = int(ac.get("rotation_anchor_ts", self.DEFAULT_ROTATION_ANCHOR_TS))
            if now < anchor:
                slot_idx = 0
                slot_start = anchor
                slot_end = anchor + dur
                if pool[0] == event_id:
                    return STATUS_UPCOMING, f"{event_id}:rot:0{seq_suffix}", slot_start, slot_end, "rotating"
                return STATUS_ENDED, None, None, None, "rotating"
            slot_idx = (now - anchor) // dur
            active_eid = pool[slot_idx % len(pool)]
            slot_start = anchor + slot_idx * dur
            slot_end = slot_start + dur
            iid = f"{event_id}:rot:{slot_idx}{seq_suffix}"
            if active_eid == event_id:
                return STATUS_ACTIVE, iid, slot_start, slot_end, "rotating"
            # Not currently the active slot
            prev_iid = self.rt["active_instance_by_event"].get(event_id)
            return STATUS_ENDED, prev_iid, slot_start, slot_end, "rotating"

        # Default: "scheduled"
        win = ac.get("scheduled_windows", {}).get(event_id)
        if isinstance(win, dict) and win.get("enabled", True):
            s_ts = int(win.get("start_ts", 0))
            e_ts = int(win.get("end_ts", 0))
            iid = str(win.get("instance_id") or f"{event_id}:sched:{s_ts}:{e_ts}") + seq_suffix
            if now < s_ts:
                return STATUS_UPCOMING, iid, s_ts, e_ts, "scheduled"
            if e_ts > 0 and now >= e_ts:
                return STATUS_ENDED, iid, s_ts, e_ts, "scheduled"
            return STATUS_ACTIVE, iid, s_ts, e_ts, "scheduled"
        if ev_def.default_start_ts is not None and ev_def.default_end_ts is not None:
            s_ts = int(ev_def.default_start_ts)
            e_ts = int(ev_def.default_end_ts)
            iid = f"{event_id}:sched:{s_ts}:{e_ts}{seq_suffix}"
            if now < s_ts:
                return STATUS_UPCOMING, iid, s_ts, e_ts, "scheduled"
            if now >= e_ts:
                return STATUS_ENDED, iid, s_ts, e_ts, "scheduled"
            return STATUS_ACTIVE, iid, s_ts, e_ts, "scheduled"
        return STATUS_ENDED, None, None, None, "scheduled"

    def evaluate(self, event_id: str, player: dict[str, Any] | None = None) -> EventEvaluation:
        ev_def = self.registry.get(event_id)
        if not ev_def:
            return EventEvaluation(
                event_id=event_id,
                module_sub=0,
                status=STATUS_ENDED,
                unlocked=False,
                eligible=False,
                instance_id=None,
                start_ts=None,
                end_ts=None,
                remaining_sec=0,
                reason="unknown_event",
            )

        now = self.clock.now()
        p_lv = int((player or {}).get("Lv", 1))
        p_vip = int((player or {}).get("VipLv", 0))
        unlocked = p_lv >= ev_def.open_lv and p_vip >= ev_def.need_vip
        mode = str(self.archive_cfg.get("mode", "rotating"))

        if ev_def.schedule_type == "permanent":
            iid = f"{event_id}:perm"
            disabled = (
                self.archive_cfg.get("scheduled_windows", {}).get(event_id, {}).get("enabled") is False
            )
            st = STATUS_ENDED if disabled else STATUS_ACTIVE
            if st == STATUS_ACTIVE:
                self._get_or_create_instance(event_id, iid, now, None, mode=mode)
            return EventEvaluation(
                event_id=event_id,
                module_sub=ev_def.module_sub,
                status=st,
                unlocked=unlocked,
                eligible=(st == STATUS_ACTIVE and unlocked),
                instance_id=iid,
                start_ts=None,
                end_ts=None,
                remaining_sec=0,
                archive_mode=mode,
                reason="" if unlocked else "level_or_vip_locked",
            )

        if ev_def.schedule_type == "daily":
            day_str = self.clock.today_str(now)
            s_ts = self.clock.midnight_ts(now)
            e_ts = self.clock.next_midnight_ts(now)
            reset_seq = int(self.archive_cfg.get("manual_reset_seq", {}).get(event_id, 0))
            iid = f"{event_id}:{day_str}" + (f":r{reset_seq}" if reset_seq > 0 else "")
            self._get_or_create_instance(event_id, iid, s_ts, e_ts, mode=mode)

            win_idx: int | None = None
            status = STATUS_ACTIVE
            rem = max(0, e_ts - now)
            if ev_def.time_windows:
                frac = self.clock.time_of_day_fraction(now)
                status = STATUS_ENDED
                for idx, (wb, we) in enumerate(ev_def.time_windows):
                    if wb <= frac <= we:
                        status = STATUS_ACTIVE
                        win_idx = idx
                        rem = max(0, s_ts + int(we * 86400) - now)
                        break
                if status == STATUS_ENDED:
                    for idx, (wb, _we) in enumerate(ev_def.time_windows):
                        if frac < wb:
                            status = STATUS_UPCOMING
                            rem = max(0, s_ts + int(wb * 86400) - now)
                            break

            return EventEvaluation(
                event_id=event_id,
                module_sub=ev_def.module_sub,
                status=status,
                unlocked=unlocked,
                eligible=(status == STATUS_ACTIVE and unlocked),
                instance_id=iid,
                start_ts=s_ts,
                end_ts=e_ts,
                remaining_sec=rem,
                active_window_idx=win_idx,
                archive_mode=mode,
                reason="" if status == STATUS_ACTIVE else "outside_time_window",
            )

        if ev_def.schedule_type == "weekly":
            week_str = self.clock.week_str(now)
            iso_wd = self.clock.weekday(now)
            s_ts = self.clock.midnight_ts(now) - (iso_wd - 1) * 86400
            e_ts = s_ts + 7 * 86400
            iid = f"{event_id}:{week_str}"
            self._get_or_create_instance(event_id, iid, s_ts, e_ts, mode=mode)
            active_days = set(ev_def.weekdays) if ev_def.weekdays else {1, 2, 3, 4, 5, 6, 7}
            if iso_wd in active_days:
                st = STATUS_ACTIVE
            elif any(d > iso_wd for d in active_days):
                st = STATUS_UPCOMING
            else:
                st = STATUS_ENDED
            return EventEvaluation(
                event_id=event_id,
                module_sub=ev_def.module_sub,
                status=st,
                unlocked=unlocked,
                eligible=(st == STATUS_ACTIVE and unlocked),
                instance_id=iid,
                start_ts=s_ts,
                end_ts=e_ts,
                remaining_sec=max(0, e_ts - now) if st == STATUS_ACTIVE else 0,
                archive_mode=mode,
            )

        # Timed / Archive events
        st, iid, s_ts, e_ts, used_mode = self._resolve_timed_window(event_id, ev_def, now)
        if st == STATUS_ACTIVE and iid:
            self._get_or_create_instance(event_id, iid, s_ts, e_ts, mode=used_mode)
        rem = max(0, (e_ts - now)) if (st == STATUS_ACTIVE and e_ts) else 0
        return EventEvaluation(
            event_id=event_id,
            module_sub=ev_def.module_sub,
            status=st,
            unlocked=unlocked,
            eligible=(st == STATUS_ACTIVE and unlocked),
            instance_id=iid,
            start_ts=s_ts,
            end_ts=e_ts,
            remaining_sec=rem,
            archive_mode=used_mode,
        )

    def get_instance(self, instance_id: str) -> dict[str, Any] | None:
        return self.rt["instances"].get(instance_id)

    def get_active_timed_events(self, module_sub: int, player: dict[str, Any] | None = None) -> list[tuple[EventDefinition, EventEvaluation]]:
        out: list[tuple[EventDefinition, EventEvaluation]] = []
        for ev_id, ev_def in self.registry.items():
            if ev_def.module_sub != module_sub:
                continue
            ev = self.evaluate(ev_id, player)
            if ev.status == STATUS_ACTIVE and ev.unlocked:
                out.append((ev_def, ev))
        return out

    def _record_archived_settlement(self, inst: dict[str, Any], on_ended: Callable[[dict[str, Any]], None] | None) -> None:
        iid = str(inst.get("instance_id", ""))
        if not inst.get("settled"):
            if on_ended is not None:
                on_ended(inst)
            inst["settled"] = True
            for snap in self.rt["archive_history"]:
                if snap.get("instance_id") == iid:
                    snap["settled"] = True
                    if "settlement" in inst:
                        snap["settlement"] = copy.deepcopy(inst["settlement"])

    def check_and_finalize_ended_timed(self, on_ended: Callable[[dict[str, Any]], None] | None = None) -> list[dict[str, Any]]:
        """Evaluate timed events so ended/expired periods transition cleanly and settle once."""
        now = self.clock.now()
        ended_now: list[dict[str, Any]] = []
        # Trigger evaluation for all active-mapped timed events first
        for ev_id in list(self.rt["active_instance_by_event"].keys()):
            ev_def = self.registry.get(ev_id)
            if ev_def and ev_def.schedule_type == "timed":
                self.evaluate(ev_id)

        for iid, inst in list(self.rt["instances"].items()):
            ev_def = self.registry.get(str(inst.get("event_id", "")))
            if not ev_def or ev_def.schedule_type != "timed":
                continue
            e_at = inst.get("end_at")
            ev = self.evaluate(ev_def.event_id)
            is_expired = (e_at is not None and now >= int(e_at)) or (ev.instance_id != iid) or (ev.status == STATUS_ENDED)
            if is_expired:
                if not inst.get("archived"):
                    self._finalize_instance_to_history(iid, "expired", now)
                if not inst.get("settled"):
                    self._record_archived_settlement(inst, on_ended)
                    ended_now.append(inst)
                elif any(s.get("instance_id") == iid and not s.get("settled") for s in self.rt["archive_history"]):
                    for snap in self.rt["archive_history"]:
                        if snap.get("instance_id") == iid:
                            snap["settled"] = True
        return ended_now

    def is_carry_over_pity(self, event_id: str) -> bool:
        ac = self.archive_cfg
        policy = ac.get("carry_over_policy", {}).get(event_id, {})
        if isinstance(policy, dict) and "pity" in policy:
            return bool(policy["pity"])
        return bool(ac.get("carry_over_pity", False))

    def manual_reset_event(
        self,
        event_id: str,
        *,
        confirm: bool = False,
        on_ended: Callable[[dict[str, Any]], None] | None = None,
        player: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Reset ONLY the chosen event/banner after explicit confirmation, preserving history & other events."""
        if confirm is not True:
            raise ValueError("Manual reset requires explicit confirmation (confirm=True)")
        ev_def = self.registry.get(event_id)
        if not ev_def:
            raise KeyError(f"Unknown event_id: {event_id}")

        now = self.clock.now()
        active_map = self.rt["active_instance_by_event"]
        old_iid = active_map.get(event_id)
        old_inst = self.rt["instances"].get(old_iid) if old_iid else None

        if old_inst is not None:
            if not old_inst.get("archived"):
                self._finalize_instance_to_history(str(old_iid), "manual_reset", now)
            self._record_archived_settlement(old_inst, on_ended)

        seqs = self.archive_cfg.setdefault("manual_reset_seq", {})
        seqs[event_id] = int(seqs.get(event_id, 0)) + 1

        if self.archive_cfg.get("mode") == "manual":
            manual = self.archive_cfg.get("manual_active")
            if isinstance(manual, dict) and manual.get("event_id") == event_id:
                dur = int(ev_def.duration_sec or 86400)
                seq = int(self.archive_cfg.get("manual_seq", 0)) + 1
                self.archive_cfg["manual_seq"] = seq
                new_iid = f"{event_id}:manual:{seq}:{now}"
                self.archive_cfg["manual_active"] = {
                    "event_id": event_id,
                    "instance_id": new_iid,
                    "start_ts": now,
                    "end_ts": now + dur,
                }

        return self.describe_archive(player)

    # ------------------------- Milestone Claim Guard -------------------------

    def is_claimed(self, instance_id: str, milestone_key: str) -> bool:
        inst = self.get_instance(instance_id)
        if not inst:
            return False
        return str(milestone_key) in inst.get("claimed", [])

    def claim_milestone(
        self,
        event_id: str,
        milestone_key: str,
        grant_fn: Callable[[str], Any],
        *,
        player: dict[str, Any] | None = None,
        allow_ended: bool = False,
    ) -> tuple[bool, Any, str]:
        """Claim a milestone inside an event instance with strict anti-duplicate protection."""
        ev = self.evaluate(event_id, player)
        if not ev.unlocked:
            return False, None, "locked"
        if ev.status != STATUS_ACTIVE and not allow_ended:
            return False, None, f"event_{ev.status}"
        if not ev.instance_id:
            return False, None, "no_instance"
        inst = self.get_instance(ev.instance_id)
        if not inst:
            return False, None, "missing_instance"
        mkey = str(milestone_key)
        claimed = inst.setdefault("claimed", [])
        if mkey in claimed:
            return False, None, "already_claimed"

        idem_key = f"evt:{ev.instance_id}:claim:{mkey}"
        result = grant_fn(idem_key)
        claimed.append(mkey)
        inst.setdefault("claim_meta", {})[mkey] = {
            "claimed_at": self.clock.now(),
            "idempotency_key": idem_key,
        }
        return True, result, "ok"

    # ------------------------- Event Archive Controls -------------------------

    def configure_archive_mode(self, mode: str, **kwargs: Any) -> dict[str, Any]:
        if mode not in ("concurrent", "scheduled", "rotating", "manual"):
            raise ValueError(f"Invalid archive mode: {mode}")
        ac = self.archive_cfg
        ac["mode"] = mode
        if "period_mode" in kwargs and str(kwargs["period_mode"]) in ("daily_utc7", "fixed_sec"):
            ac["period_mode"] = str(kwargs["period_mode"])
        if "period_sec" in kwargs:
            ac["period_sec"] = max(60, int(kwargs["period_sec"]))
        if "period_anchor_ts" in kwargs:
            ac["period_anchor_ts"] = int(kwargs["period_anchor_ts"])
        if "period_overrides" in kwargs and isinstance(kwargs["period_overrides"], dict):
            ov = ac.setdefault("period_overrides", {})
            for eid, dur in kwargs["period_overrides"].items():
                if dur is None:
                    ov.pop(str(eid), None)
                else:
                    ov[str(eid)] = max(60, int(dur))
        if "carry_over_pity" in kwargs:
            ac["carry_over_pity"] = bool(kwargs["carry_over_pity"])
        if "carry_over_policy" in kwargs and isinstance(kwargs["carry_over_policy"], dict):
            ac.setdefault("carry_over_policy", {}).update(kwargs["carry_over_policy"])
        if isinstance(kwargs.get("settle_unclaimed_credit"), bool):
            ac["settle_unclaimed_credit"] = kwargs["settle_unclaimed_credit"]

        if mode == "concurrent":
            if "concurrent_events" in kwargs and isinstance(kwargs["concurrent_events"], list):
                ac["concurrent_events"] = [str(x) for x in kwargs["concurrent_events"] if str(x) in self.registry]
            elif "events" in kwargs and isinstance(kwargs["events"], list):
                ac["concurrent_events"] = [str(x) for x in kwargs["events"] if str(x) in self.registry]
        elif mode == "rotating":
            if "rotation_pool" in kwargs and isinstance(kwargs["rotation_pool"], list):
                ac["rotation_pool"] = [str(x) for x in kwargs["rotation_pool"] if str(x) in self.registry]
            if "rotation_duration_sec" in kwargs:
                ac["rotation_duration_sec"] = max(60, int(kwargs["rotation_duration_sec"]))
            if "rotation_anchor_ts" in kwargs:
                ac["rotation_anchor_ts"] = int(kwargs["rotation_anchor_ts"])
        elif mode == "scheduled" and "scheduled_windows" in kwargs:
            sw = ac.setdefault("scheduled_windows", {})
            for eid, w in dict(kwargs["scheduled_windows"]).items():
                sw[str(eid)] = {
                    "start_ts": int(w.get("start_ts", self.clock.now())),
                    "end_ts": int(w.get("end_ts", self.clock.now() + 259200)),
                    "enabled": bool(w.get("enabled", True)),
                    "instance_id": w.get("instance_id") or f"{eid}:sched:{int(w.get('start_ts', self.clock.now()))}:{uuid.uuid4().hex[:6]}",
                }
        elif mode == "manual" and "event_id" in kwargs:
            return self.activate_manual_event(
                str(kwargs["event_id"]),
                duration_sec=int(kwargs.get("duration_sec", 259200)),
            )
        return self.describe_archive()

    def set_scheduled_window(
        self,
        event_id: str,
        start_ts: int,
        end_ts: int,
        *,
        enabled: bool = True,
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        if event_id not in self.registry:
            raise KeyError(f"Unknown event_id: {event_id}")
        ac = self.archive_cfg
        ac["mode"] = "scheduled"
        sw = ac.setdefault("scheduled_windows", {})
        iid = instance_id or f"{event_id}:sched:{int(start_ts)}:{int(end_ts)}"
        sw[event_id] = {
            "start_ts": int(start_ts),
            "end_ts": int(end_ts),
            "enabled": bool(enabled),
            "instance_id": iid,
        }
        return self.describe_archive()

    def activate_manual_event(self, event_id: str, *, duration_sec: int | None = None) -> dict[str, Any]:
        """Start a fresh replay period in Manual Event Archive mode.

        Creates a distinct ``instance_id`` so historical periods & claimed rewards
        remain untouched while the new period starts cleanly with zero rewards unlocked.
        """
        ev_def = self.registry.get(event_id)
        if not ev_def:
            raise KeyError(f"Unknown event_id: {event_id}")
        now = self.clock.now()
        ac = self.archive_cfg
        prev = ac.get("manual_active")
        if isinstance(prev, dict) and prev.get("instance_id"):
            self._finalize_instance_to_history(str(prev["instance_id"]), "manual_replaced", now)

        seq = int(ac.get("manual_seq", 0)) + 1
        ac["manual_seq"] = seq
        dur = int(duration_sec) if duration_sec is not None else int(ev_def.duration_sec or 259200)
        new_iid = f"{event_id}:manual:{seq}:{now}"
        ac["mode"] = "manual"
        ac["manual_active"] = {
            "event_id": event_id,
            "instance_id": new_iid,
            "start_ts": now,
            "end_ts": now + max(60, dur),
        }
        self._get_or_create_instance(event_id, new_iid, now, now + max(60, dur), mode="manual")
        return self.describe_archive()

    def describe_archive(self, player: dict[str, Any] | None = None) -> dict[str, Any]:
        events_summary: dict[str, Any] = {}
        for eid in sorted(self.registry):
            ev = self.evaluate(eid, player)
            ev_def = self.registry[eid]
            events_summary[eid] = {
                "event_id": eid,
                "module_sub": ev_def.module_sub,
                "name": ev_def.name,
                "schedule_type": ev_def.schedule_type,
                "open_lv": ev_def.open_lv,
                "source_origin": ev_def.source_origin,
                "archive_eligible": ev_def.archive_eligible,
                "status": ev.status,
                "unlocked": ev.unlocked,
                "eligible": ev.eligible,
                "instance_id": ev.instance_id,
                "start_ts": ev.start_ts,
                "end_ts": ev.end_ts,
                "remaining_sec": ev.remaining_sec,
                "active_window_idx": ev.active_window_idx,
            }
        return {
            "clock": self.clock.to_dict(),
            "archive_config": copy.deepcopy(self.archive_cfg),
            "events": events_summary,
            "active_instances": copy.deepcopy(self.rt["active_instance_by_event"]),
            "history_count": len(self.rt["archive_history"]),
            "history": copy.deepcopy(self.rt["archive_history"]),
        }
