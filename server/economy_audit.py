#!/usr/bin/env python3
"""
Resource Transaction & Audit Ledger Foundation for InuYasha: Seek Jade Revival.

Provides:
  - Idempotent, validated resource mutations (Gold, Diamond, HeroEXP, HeroCoin, VIT, STA, VipEXP, Items/Heroes/Equips).
  - Append-only JSONL audit log with tx_id, account_id, profile, resource_type, amount, balance_after, source, timestamp.
  - VIP level derivation from VipEXP using extracted VipModel (no arbitrary stat/multiplier overrides).
  - Read-only/local-only admin inspection & grant helpers (no public exposure, no combat stat tampering).
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_PLAYER_RESOURCES = {
    "Gold": "Gold",
    "Diamond": "Diamond",
    "HeroEXP": "HeroEXP",
    "HeroCoin": "HeroCoin",
    "VIT": "VIT",
    "STA": "STA",
    "VipEXP": "VipEXP",
    "EXP": "EXP",
    "PVPCoin": "PVPCoin",
    "BossCoin": "BossCoin",
    "Contribution": "Contribution",
    "Merit": "Merit",
    "GDDHCoin": "GDDHCoin",
    "RebornCoin": "RebornCoin",
    "PetSoul": "PetSoul",
    "PetCoin": "PetCoin",
}

DISALLOWED_BALANCE_KEYS = {"HP", "AP", "DEF", "DAM", "DAMADD", "DAMADDR", "DAMCUT", "DAMCUTR"}


@dataclass(frozen=True)
class ResourceTransaction:
    """Immutable audit record for a single resource delta."""

    tx_id: str
    account_id: str
    profile: str
    resource_type: str
    amount: int
    balance_after: int
    source: str
    idempotency_key: str
    timestamp_unix: int
    timestamp_iso: str
    actor: str = "system"
    metadata: dict[str, Any] | None = None


class ResourceTransactionError(ValueError):
    """Raised when a resource mutation fails validation or violates balance invariants."""


class DuplicateTransactionError(ResourceTransactionError):
    """Raised when an idempotency_key has already been applied."""


class ResourceLedger:
    """Validates, applies, deduplicates, and audits economy transactions."""

    def __init__(self, audit_log_path: Path | None = None, vip_model: dict[str, Any] | None = None) -> None:
        self.audit_log_path = audit_log_path
        self.vip_model = vip_model or {}
        self._lock = threading.RLock()
        self._debit_capture = threading.local()
        self._applied_keys: set[tuple[str, str]] = set()
        self._memory_log: list[dict[str, Any]] = []
        if self.audit_log_path and self.audit_log_path.exists():
            for line in self.audit_log_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("account_id") and rec.get("idempotency_key"):
                        self._applied_keys.add((str(rec["account_id"]), rec["idempotency_key"]))
                except json.JSONDecodeError:
                    continue

    @contextmanager
    def capture_diamond_debits(self):
        """Measure actual Diamond costs during one RPC, independently of its rewards."""
        previous = getattr(self._debit_capture, "accounts", None)
        accounts: dict[str, int] = {}
        self._debit_capture.accounts = accounts
        try:
            yield accounts
        finally:
            self._debit_capture.accounts = previous

    def derive_vip_level(self, vip_exp: int) -> int:
        """Compute VIP level strictly from cumulative VipEXP and VipModel thresholds."""
        if not self.vip_model:
            return 0
        best_lv = 0
        for row in self.vip_model.values():
            lv = int(row.get("LV", 0))
            req = int(row.get("expTotal", 0))
            if vip_exp >= req and lv > best_lv:
                best_lv = lv
        return best_lv

    def apply_player_delta(
        self,
        player: dict[str, Any],
        profile: str,
        resource_type: str,
        amount: int,
        source: str,
        idempotency_key: str | None = None,
        actor: str = "system",
        allow_duplicate_noop: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ResourceTransaction | None:
        """Apply a validated signed delta to a player's currency/resource and append an audit entry."""
        if resource_type in DISALLOWED_BALANCE_KEYS:
            raise ResourceTransactionError(f"Direct mutation of combat stat {resource_type!r} is forbidden")
        if resource_type not in ALLOWED_PLAYER_RESOURCES:
            raise ResourceTransactionError(f"Unsupported player resource_type: {resource_type!r}")
        if not isinstance(amount, int) or isinstance(amount, bool):
            raise ResourceTransactionError(f"Amount must be integer, got {amount!r}")
        if not source or not source.strip():
            raise ResourceTransactionError("Transaction source/reason is required")

        account_id = str(player.get("PlayerId", ""))
        if not account_id:
            raise ResourceTransactionError("PlayerId missing from player state")

        with self._lock:
            idem_key = idempotency_key or f"auto:{uuid.uuid4()}"
            if (account_id, idem_key) in self._applied_keys:
                if allow_duplicate_noop:
                    return None
                raise DuplicateTransactionError(f"Duplicate idempotency_key: {idem_key}")

            current = int(player.get(resource_type, 0))
            new_val = current + amount
            if new_val < 0:
                raise ResourceTransactionError(
                    f"Insufficient {resource_type}: balance={current}, delta={amount}"
                )

            player[resource_type] = new_val
            if resource_type == "VipEXP" and self.vip_model:
                vip_lv = self.derive_vip_level(new_val)
                player["Vip"] = vip_lv
                player["VIPLv"] = vip_lv

            transaction = self._record(
                account_id=account_id,
                profile=profile,
                resource_type=resource_type,
                amount=amount,
                balance_after=new_val,
                source=source.strip(),
                idempotency_key=idem_key,
                actor=actor,
                metadata=metadata,
            )
            capture = getattr(self._debit_capture, "accounts", None)
            if capture is not None and resource_type == "Diamond" and amount < 0:
                capture[account_id] = capture.get(account_id, 0) - amount
            return transaction

    def record_grant_event(
        self,
        account_id: str,
        profile: str,
        resource_type: str,
        amount: int,
        balance_after: int,
        source: str,
        idempotency_key: str | None = None,
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> ResourceTransaction | None:
        """Record an item/hero/equip grant transaction in the audit ledger."""
        with self._lock:
            idem_key = idempotency_key or f"auto:{uuid.uuid4()}"
            if (str(account_id), idem_key) in self._applied_keys:
                raise DuplicateTransactionError(f"Duplicate idempotency_key: {idem_key}")
            return self._record(
                account_id=account_id,
                profile=profile,
                resource_type=resource_type,
                amount=amount,
                balance_after=balance_after,
                source=source.strip(),
                idempotency_key=idem_key,
                actor=actor,
                metadata=metadata,
            )

    def _record(
        self,
        *,
        account_id: str,
        profile: str,
        resource_type: str,
        amount: int,
        balance_after: int,
        source: str,
        idempotency_key: str,
        actor: str,
        metadata: dict[str, Any] | None,
    ) -> ResourceTransaction:
        now_unix = int(time.time())
        now_iso = datetime.fromtimestamp(now_unix, tz=timezone.utc).isoformat()
        tx = ResourceTransaction(
            tx_id=str(uuid.uuid4()),
            account_id=account_id,
            profile=profile,
            resource_type=resource_type,
            amount=amount,
            balance_after=balance_after,
            source=source,
            idempotency_key=idempotency_key,
            timestamp_unix=now_unix,
            timestamp_iso=now_iso,
            actor=actor,
            metadata=metadata,
        )
        self._applied_keys.add((str(account_id), idempotency_key))
        entry = asdict(tx)
        self._memory_log.append(entry)
        if self.audit_log_path:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return tx

    def list_transactions(self, account_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent audit transactions, optionally filtered by account_id."""
        if self.audit_log_path and self.audit_log_path.exists():
            rows = [
                json.loads(ln)
                for ln in self.audit_log_path.read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
        else:
            rows = list(self._memory_log)
        if account_id is not None:
            rows = [r for r in rows if str(r.get("account_id")) == str(account_id)]
        return rows[-limit:]
