"""
VIGILANT FHIR Layer — Client + Resource Builders + SHARP Context.

Part 1: FHIR Client — loads patient data from local JSON or remote FHIR server
Part 2: FHIR Resource Builders — creates Task and CarePlan resources
Part 3: SHARP Context — parses SMART on FHIR launch context
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


# =============================================================================
#  PART 1: FHIR CLIENT
#  Loads patient data from local JSON files or a remote FHIR server.
# =============================================================================

def _load_local_json(filename: str) -> list:
    """Load a local JSON data file."""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_mothers(fhir_server: str = "", fhir_token: str = "") -> list:
    """Get all mother Patient resources."""
    if fhir_server and HAS_HTTPX:
        return _fetch_fhir_patients(fhir_server, fhir_token, category="mother")
    return _load_local_json("mothers.json")


def get_newborns(fhir_server: str = "", fhir_token: str = "") -> list:
    """Get all newborn Patient resources."""
    if fhir_server and HAS_HTTPX:
        return _fetch_fhir_patients(fhir_server, fhir_token, category="newborn")
    return _load_local_json("newborns.json")


def get_patient_by_id(patient_id: str, fhir_server: str = "",
                      fhir_token: str = "") -> Optional[dict]:
    """Get a single Patient resource by ID."""
    if fhir_server and HAS_HTTPX:
        return _fetch_fhir_resource(fhir_server, fhir_token, "Patient", patient_id)
    for dataset in ["mothers.json", "newborns.json"]:
        for patient in _load_local_json(dataset):
            if patient.get("id") == patient_id:
                return patient
    return None


def _patient_display_name(patient: dict) -> str:
    """Return a single display string for a patient."""
    name_block = patient.get("name", [{}])[0]
    given = " ".join(name_block.get("given", []))
    family = name_block.get("family", "")
    return f"{given} {family}".strip()


def find_patient_by_name_or_id(query: str, datasets: list[str],
                               fhir_server: str = "",
                               fhir_token: str = "") -> Optional[dict]:
    """Find a patient by UUID or by case-insensitive name substring.

    datasets: list of filenames to search, e.g. ['newborns.json'] or ['mothers.json']
    Returns the first match, or None.
    """
    query = query.strip()
    query_lower = query.lower()

    # Try exact ID first (UUIDs contain hyphens)
    for dataset in datasets:
        if fhir_server and HAS_HTTPX:
            p = get_patient_by_id(query, fhir_server, fhir_token)
            if p:
                return p
        else:
            for patient in _load_local_json(dataset):
                if patient.get("id") == query:
                    return patient

    # Fall back to name substring match
    for dataset in datasets:
        candidates = _load_local_json(dataset)
        for patient in candidates:
            full_name = _patient_display_name(patient).lower()
            if query_lower in full_name:
                return patient

    return None


def _fetch_fhir_patients(fhir_server: str, fhir_token: str,
                         category: str = "") -> list:
    """Fetch Patient resources from a remote FHIR server."""
    headers = {"Accept": "application/fhir+json"}
    if fhir_token:
        headers["Authorization"] = f"Bearer {fhir_token}"
    try:
        url = f"{fhir_server.rstrip('/')}/Patient"
        response = httpx.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        bundle = response.json()
        return [entry["resource"] for entry in bundle.get("entry", [])]
    except Exception as e:
        print(f"[FHIRClient] Error fetching patients: {e}")
        return _load_local_json(
            "mothers.json" if category == "mother" else "newborns.json"
        )


def _fetch_fhir_resource(fhir_server: str, fhir_token: str,
                         resource_type: str, resource_id: str) -> Optional[dict]:
    """Fetch a single FHIR resource by type and ID."""
    headers = {"Accept": "application/fhir+json"}
    if fhir_token:
        headers["Authorization"] = f"Bearer {fhir_token}"
    try:
        url = f"{fhir_server.rstrip('/')}/{resource_type}/{resource_id}"
        response = httpx.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[FHIRClient] Error fetching {resource_type}/{resource_id}: {e}")
        return None


# =============================================================================
#  PART 2: FHIR RESOURCE BUILDERS
#  Creates FHIR Task and CarePlan resources from Bridge Summaries.
# =============================================================================

def create_fhir_task(bridge_summary):
    """Generate a FHIR Task resource from a BridgeSummary."""
    return {
        "resourceType": "Task",
        "id": str(uuid.uuid4()),
        "status": "requested",
        "intent": "order",
        "priority": "urgent" if bridge_summary.risk_level == "HIGH" else "routine",
        "description": bridge_summary.recommended_action,
        "for": {
            "display": bridge_summary.infant_name,
        },
        "requester": {
            "display": "VIGILANT System",
        },
        "owner": {
            "display": "Attending Clinician",
        },
        "input": [
            {
                "type": {"text": "risk_level"},
                "valueString": bridge_summary.risk_level,
            },
            {
                "type": {"text": "mother_name"},
                "valueString": bridge_summary.mother_name,
            },
            {
                "type": {"text": "art_id"},
                "valueString": bridge_summary.art_id,
            },
            {
                "type": {"text": "confidence"},
                "valueString": f"{bridge_summary.confidence:.0%}",
            },
            {
                "type": {"text": "viral_load"},
                "valueString": str(bridge_summary.viral_load),
            },
        ],
    }


def create_fhir_care_plan(bridge_summary, birth_date: str = ""):
    """Generate a FHIR CarePlan with 12-month follow-up schedule."""
    activities = []

    if not birth_date:
        birth_date = datetime.now().strftime("%Y-%m-%d")

    try:
        dob = datetime.strptime(birth_date, "%Y-%m-%d")
    except ValueError:
        dob = datetime.now()

    # PCR tests at 6 weeks, 6 months, 12 months
    pcr_schedule = [
        (42, "PCR Test #1 — 6 weeks"),
        (180, "PCR Test #2 — 6 months"),
        (365, "PCR Test #3 — 12 months (final)"),
    ]
    for days, desc in pcr_schedule:
        test_date = dob + timedelta(days=days)
        activities.append({
            "detail": {
                "description": desc,
                "status": "scheduled",
                "scheduledPeriod": {
                    "start": test_date.strftime("%Y-%m-%d"),
                    "end": (test_date + timedelta(days=7)).strftime("%Y-%m-%d"),
                },
            }
        })

    # Bactrim prophylaxis from 6 weeks
    bactrim_start = dob + timedelta(days=42)
    activities.append({
        "detail": {
            "description": "Start Bactrim (co-trimoxazole) prophylaxis",
            "status": "scheduled",
            "scheduledPeriod": {
                "start": bactrim_start.strftime("%Y-%m-%d"),
                "end": (dob + timedelta(days=365)).strftime("%Y-%m-%d"),
            },
        }
    })

    return {
        "resourceType": "CarePlan",
        "id": str(uuid.uuid4()),
        "status": "active",
        "intent": "plan",
        "title": f"HIV-Exposed Infant Follow-Up — {bridge_summary.infant_name}",
        "subject": {"display": bridge_summary.infant_name},
        "period": {
            "start": birth_date,
            "end": (dob + timedelta(days=365)).strftime("%Y-%m-%d"),
        },
        "activity": activities,
    }


# =============================================================================
#  PART 3: SHARP CONTEXT
#  Parses SMART on FHIR / SHARP launch context for healthcare data access.
# =============================================================================

def parse_sharp_context(raw_context: dict) -> dict:
    """Parse and normalize a SHARP launch context.
    Expected fields: patientId, fhirBaseUrl, accessToken, role, userId, facilityId, organization.
    """
    return {
        "patient_id": raw_context.get("patientId", raw_context.get("patient_id", "")),
        "fhir_server": raw_context.get("fhirBaseUrl", raw_context.get("fhir_server", "")),
        "fhir_token": raw_context.get("accessToken", raw_context.get("fhir_token", "")),
        "role": raw_context.get("role", "unauthorized"),
        "user_id": raw_context.get("userId", raw_context.get("user_id", "unknown")),
        "facility_id": raw_context.get("facilityId", raw_context.get("facility_id", "")),
        "organization": raw_context.get("organization", ""),
        "token": raw_context.get("accessToken", raw_context.get("token", "")),
    }


def has_valid_token(context: dict) -> bool:
    """Check if the SHARP context contains a valid FHIR token."""
    token = context.get("fhir_token", "")
    return bool(token and token != "not-set")


def get_patient_id(context: dict) -> str:
    """Extract the patient ID from SHARP context."""
    return context.get("patient_id", "")
