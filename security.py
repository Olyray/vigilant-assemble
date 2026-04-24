"""
VIGILANT Security — Audit Logging + Role-Based Access Control.

Part 1: HashChainLogger — Immutable SHA-256 hash-chained audit log (NDPA 2023 compliance)
Part 2: Role-Based Access Gateway (APIN trust model)

Principles: Data minimization, data sovereignty (Nigeria Data Protection Act 2023).
"""

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime


# =============================================================================
#  PART 1: IMMUTABLE HASH-CHAINED AUDIT LOGGER
#  Every linkage, access attempt, and risk classification is logged with
#  SHA-256 hash chaining for tamper-evident auditability.
#  Genesis block uses prev_hash = "0" * 64.
#  Event IDs use UUID v7 (time-ordered) for chronological traceability.
# =============================================================================

GENESIS_HASH = "0" * 64


def _uuid7() -> str:
    """Generate a UUID v7 (time-ordered) identifier.

    UUID v7 encodes a Unix timestamp in the most-significant 48 bits,
    ensuring IDs are naturally sortable by creation time.
    """
    timestamp_ms = int(time.time() * 1000)
    # 48-bit timestamp
    time_hex = f"{timestamp_ms:012x}"
    # Random fill for the remaining bits
    rand_bits = uuid.uuid4().hex[12:]
    raw = time_hex + rand_bits
    # Set version (7) and variant (RFC 4122)
    chars = list(raw)
    chars[12] = "7"                          # version nibble
    chars[16] = hex(0x8 | (int(chars[16], 16) & 0x3))[2:]  # variant
    return (
        "".join(chars[0:8]) + "-"
        + "".join(chars[8:12]) + "-"
        + "".join(chars[12:16]) + "-"
        + "".join(chars[16:20]) + "-"
        + "".join(chars[20:32])
    )


class HashChainLogger:
    """Immutable, SHA-256 hash-chained audit logger.

    Each log entry contains:
      - event_id   : UUID v7 (time-ordered)
      - prev_hash  : SHA-256 hash of the previous entry (genesis = "0" * 64)
      - entry_hash : SHA-256( prev_hash | json(entry) )

    The chain can be verified end-to-end with ``verify_chain()``.
    """

    def __init__(self, log_path: str | None = None):
        self._log_path = log_path or os.environ.get(
            "VIGILANT_AUDIT_LOG",
            os.path.join(os.path.dirname(__file__), "data", "audit_log.jsonl"),
        )
        os.makedirs(os.path.dirname(self._log_path), exist_ok=True)
        self._last_hash: str | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_last_hash(self) -> str:
        """Read the last entry's hash from the log file for chain continuity."""
        if self._last_hash is not None:
            return self._last_hash
        if not os.path.exists(self._log_path):
            return GENESIS_HASH
        last_line = ""
        with open(self._log_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
        if last_line:
            try:
                entry = json.loads(last_line)
                return entry.get("entry_hash", GENESIS_HASH)
            except json.JSONDecodeError:
                pass
        return GENESIS_HASH

    @staticmethod
    def _compute_hash(entry_json: str, prev_hash: str) -> str:
        """Compute SHA-256 hash of (prev_hash | entry_json)."""
        payload = f"{prev_hash}|{entry_json}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _append(self, entry: dict) -> str:
        """Append a single hash-chained audit entry. Returns the event_id."""
        event_id = _uuid7()
        entry["event_id"] = event_id
        entry["timestamp"] = datetime.utcnow().isoformat() + "Z"

        prev_hash = self._read_last_hash()
        entry["prev_hash"] = prev_hash

        entry_json = json.dumps(entry, sort_keys=True, default=str)
        entry["entry_hash"] = self._compute_hash(entry_json, prev_hash)
        self._last_hash = entry["entry_hash"]

        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

        return event_id

    # ------------------------------------------------------------------
    # Public logging methods
    # ------------------------------------------------------------------

    def log_linkage(self, user_id: str, role: str, infant_id: str,
                    mother_id: str, confidence: float, action: str,
                    organization: str = "") -> str:
        """Log a mother-infant linkage event. Returns event_id."""
        return self._append({
            "event": "linkage", "user_id": user_id, "role": role,
            "organization": organization, "infant_id": infant_id,
            "mother_id": mother_id, "confidence": confidence, "action": action,
        })

    def log_access_denied(self, user_id: str, role: str, resource: str,
                          reason: str = "") -> str:
        """Log an unauthorized access attempt. Returns event_id."""
        return self._append({
            "event": "access_denied", "user_id": user_id,
            "role": role, "resource": resource, "reason": reason,
        })

    def log_risk_classification(self, user_id: str, infant_id: str,
                                mother_id: str, risk_level: str,
                                reasons: list, organization: str = "") -> str:
        """Log a risk classification decision. Returns event_id."""
        return self._append({
            "event": "risk_classification", "user_id": user_id,
            "organization": organization, "infant_id": infant_id,
            "mother_id": mother_id, "risk_level": risk_level, "reasons": reasons,
        })

    def log_data_access(self, user_id: str, role: str, resource: str,
                        fields_accessed: list, organization: str = "") -> str:
        """Log what data fields a user accessed. Returns event_id."""
        return self._append({
            "event": "data_access", "user_id": user_id, "role": role,
            "organization": organization, "resource": resource,
            "fields_accessed": fields_accessed,
        })

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_chain(self, limit: int = 0) -> dict:
        """Verify the integrity of the audit log hash chain.

        Iterates through every entry and confirms:
          1. The first entry's prev_hash equals GENESIS_HASH ("0" * 64).
          2. Each subsequent entry's prev_hash matches the previous entry_hash.
          3. Each entry_hash is correctly computed from its contents.

        Returns:
            dict with keys: valid (bool), entries_checked (int), first_broken (int|None).
        """
        if not os.path.exists(self._log_path):
            return {"valid": True, "entries_checked": 0, "first_broken": None}

        entries = []
        with open(self._log_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    try:
                        entries.append(json.loads(stripped))
                    except json.JSONDecodeError:
                        continue

        if limit > 0:
            entries = entries[-limit:]

        expected_prev = GENESIS_HASH if limit == 0 else entries[0].get("prev_hash", "")

        for i, entry in enumerate(entries):
            stored_hash = entry.get("entry_hash", "")
            prev_hash = entry.get("prev_hash", "")

            # Check chain linkage
            if i == 0 and limit == 0 and prev_hash != GENESIS_HASH:
                return {"valid": False, "entries_checked": 1, "first_broken": 0}
            if i > 0 and prev_hash != expected_prev:
                return {"valid": False, "entries_checked": i + 1, "first_broken": i}

            # Recompute hash
            check_entry = {k: v for k, v in entry.items() if k != "entry_hash"}
            check_json = json.dumps(check_entry, sort_keys=True, default=str)
            computed = self._compute_hash(check_json, prev_hash)
            if stored_hash != computed:
                return {"valid": False, "entries_checked": i + 1, "first_broken": i}

            expected_prev = stored_hash

        return {"valid": True, "entries_checked": len(entries), "first_broken": None}

    def get_audit_log(self, limit: int = 100) -> list:
        """Read the last N audit log entries."""
        if not os.path.exists(self._log_path):
            return []
        entries = []
        with open(self._log_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    try:
                        entries.append(json.loads(stripped))
                    except json.JSONDecodeError:
                        continue
        return entries[-limit:]


# Module-level singleton for convenience
_logger = HashChainLogger()

log_linkage = _logger.log_linkage
log_access_denied = _logger.log_access_denied
log_risk_classification = _logger.log_risk_classification
log_data_access = _logger.log_data_access
verify_chain = _logger.verify_chain
get_audit_log = _logger.get_audit_log


def get_last_hash() -> str:
    """Return the most recent entry_hash from the audit chain."""
    return _logger._read_last_hash()


# =============================================================================
#  PART 2: ROLE-BASED ACCESS GATEWAY
#  Implements the APIN Gateway Model for data minimization.
# =============================================================================

@dataclass
class AuthContext:
    """Parsed authorization context from SHARP token."""
    user_id: str
    role: str           # "nurse" | "hiv_specialist" | "facility_manager" | "unauthorized"
    facility_id: str
    organization: str
    token: str = ""


ROLE_ACCESS = {
    "hiv_specialist": {
        "can_view_notes": True, "can_view_mother_identity": True,
        "can_view_viral_load": True, "can_confirm_linkage": True,
        "can_view_adherence_details": True,
    },
    "nurse": {
        "can_view_notes": False, "can_view_mother_identity": False,
        "can_view_viral_load": False, "can_confirm_linkage": False,
        "can_view_adherence_details": False,
    },
    "facility_manager": {
        "can_view_notes": False, "can_view_mother_identity": True,
        "can_view_viral_load": False, "can_confirm_linkage": False,
        "can_view_adherence_details": False,
    },
}


def parse_auth_context(sharp_context: dict) -> AuthContext:
    """Parse SHARP context into an AuthContext object."""
    return AuthContext(
        user_id=sharp_context.get("user_id", "unknown"),
        role=sharp_context.get("role", "unauthorized"),
        facility_id=sharp_context.get("facility_id", ""),
        organization=sharp_context.get("organization", ""),
        token=sharp_context.get("token", ""),
    )


def is_authorized(auth: AuthContext) -> bool:
    """Check if the user has any valid role."""
    return auth.role in ROLE_ACCESS


def get_permissions(auth: AuthContext) -> dict:
    """Get the permission set for a given role."""
    return ROLE_ACCESS.get(auth.role, {})


def filter_output_by_role(bridge_summary, auth: AuthContext) -> dict:
    """Filter the Bridge Summary based on the user's role.
    - Nurses: risk flag + drug action ONLY
    - HIV Specialists: everything
    - Facility Managers: risk flag + mother name
    """
    perms = get_permissions(auth)
    if not perms:
        return {"error": "Unauthorized", "role": auth.role}

    if isinstance(bridge_summary, dict):
        summary = bridge_summary
    elif hasattr(bridge_summary, "__dict__"):
        summary = bridge_summary.__dict__
    else:
        summary = {"raw": str(bridge_summary)}

    if auth.role == "nurse":
        return {
            "infant_name": summary.get("infant_name", ""),
            "risk_level": summary.get("risk_level", ""),
            "prophylaxis_action": summary.get("prophylaxis_action", ""),
            "urgency": summary.get("urgency", ""),
            "data_governance": {
                "role": "nurse",
                "filter": "PII and clinical notes redacted per NDPA 2023 data minimization",
            },
        }
    elif auth.role == "facility_manager":
        return {
            "infant_name": summary.get("infant_name", ""),
            "mother_name": summary.get("mother_name", ""),
            "risk_level": summary.get("risk_level", ""),
            "prophylaxis_action": summary.get("prophylaxis_action", ""),
            "data_governance": {
                "role": "facility_manager",
                "filter": "Clinical notes redacted per NDPA 2023",
            },
        }
    else:
        full = dict(summary)
        full["data_governance"] = {
            "role": auth.role,
            "filter": "Full access — HIV specialist clearance",
        }
        return full
