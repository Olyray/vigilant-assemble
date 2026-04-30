"""
VIGILANT MCP Server — Agents Assemble Hackathon Version.

Exposes 4 MCP tools for the Prompt Opinion platform:
1. link_infant_to_mother — Probabilistic identity matching
2. extract_adherence_risks — AI-powered clinical note analysis (Gemma 4 via Ollama)
3. classify_infant_risk — Rule-based risk classification + FHIR Task
4. run_full_workflow — Complete pipeline: Link → Extract → Classify

Prompt Opinion delivers FHIR context via HTTP request headers:
  X-FHIR-Server-URL   → FHIR server base URL
  X-FHIR-Access-Token → OAuth bearer token
  X-Patient-ID        → Current patient ID

Hackathon: Agents Assemble
AI Backend: Gemma 4 (Local via Ollama)
"""

import asyncio
import json
import os
import socket
import sys
import uuid

sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# ---------------------------------------------------------------------------
# Prompt Opinion FHIR Context Extension
#
# Prompt Opinion reads capabilities.extensions["ai.promptopinion/fhir-context"]
# from the MCP initialize response to decide whether to send FHIR headers.
# WITHOUT this extension, Prompt Opinion will NEVER send X-FHIR-Server-URL,
# X-FHIR-Access-Token, or X-Patient-ID — making real EHR data inaccessible.
#
# fastmcp has no built-in API for capabilities.extensions, so we inject it
# via a Starlette response middleware that patches initialize responses.
# ---------------------------------------------------------------------------

_FHIR_CAPABILITY_EXTENSION = {
    "ai.promptopinion/fhir-context": {
        "scopes": [
            # patient/Patient.rs — required: read mother and infant Patient records
            {"name": "patient/Patient.rs", "required": True},
            # patient/Observation.rs — optional: viral load lab results
            {"name": "patient/Observation.rs"},
            # patient/Condition.rs — optional: HIV diagnosis conditions
            {"name": "patient/Condition.rs"},
            # patient/MedicationRequest.rs — optional: ART prescriptions
            {"name": "patient/MedicationRequest.rs"},
            # patient/DocumentReference.rs — optional: clinical notes
            {"name": "patient/DocumentReference.rs"},
        ]
    }
}


class _FHIRCapabilityMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that injects capabilities.extensions into MCP
    initialize responses so Prompt Opinion will send FHIR context headers."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Only JSON responses need patching (initialize is JSON, SSE streams are text/event-stream)
        content_type = response.headers.get("content-type", "")
        if request.method != "POST" or "application/json" not in content_type:
            return response
        # Buffer body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        try:
            data = json.loads(body)
            result = data.get("result", {})
            if isinstance(result, dict) and "capabilities" in result:
                caps = result["capabilities"]
                if "extensions" not in caps:
                    caps["extensions"] = {}
                caps["extensions"].update(_FHIR_CAPABILITY_EXTENSION)
                body = json.dumps(data).encode()
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        headers = dict(response.headers)
        headers["content-length"] = str(len(body))
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )

from agents import (
    find_mother,
    extract_adherence_risks as _run_adherence_extraction,
    extract_adherence_risks_offline as _run_adherence_extraction_offline,
    HAS_GEMMA, classify_risk, build_bridge_summary,
)
from fhir_layer import (
    create_fhir_task, create_fhir_care_plan,
    get_mothers, get_patient_by_id,
)
from security import (
    parse_auth_context, is_authorized, filter_output_by_role,
    log_linkage, log_risk_classification, log_access_denied, log_data_access,
)

mcp = FastMCP(
    "VIGILANT — Infant HIV Risk Detection",
    instructions=(
        "Three MCP tools for infant HIV exposure risk management under the WHO PMTCT protocol. "
        "Use link_infant_to_mother first to find the mother, then extract_adherence_risks to "
        "surface hidden ART adherence signals, then classify_infant_risk for a risk verdict and "
        "FHIR Task. Or call run_full_workflow to run the complete pipeline in one step."
    ),
)


def _audit_id() -> str:
    """Generate a unique audit log ID for data governance tracking."""
    return f"audit_{uuid.uuid4().hex[:12]}"


def _ctx_from_headers() -> dict:
    """Build a SHARP-compatible context dict from Prompt Opinion FHIR request headers.

    Prompt Opinion sends:  X-FHIR-Server-URL, X-FHIR-Access-Token, X-Patient-ID.
    Role defaults to 'hiv_specialist' so the demo works without an auth header.
    Returns empty-safe values when running outside an HTTP context (local tests).
    """
    headers = get_http_headers()
    fhir_token = headers.get("x-fhir-access-token", "")
    return {
        "patient_id":   headers.get("x-patient-id", ""),
        "fhir_server":  headers.get("x-fhir-server-url", ""),
        "fhir_token":   fhir_token,
        "token":        fhir_token,
        "role":         headers.get("x-role", "hiv_specialist"),
        "user_id":      headers.get("x-user-id", "mcp_client"),
        "facility_id":  headers.get("x-facility-id", ""),
        "organization": headers.get("x-organization", ""),
    }


# --- Health Check (custom HTTP route, not an MCP tool) ---

@mcp.custom_route("/", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({
        "service": "VIGILANT MCP Server — Agents Assemble",
        "status": "running",
        "ai_backend": "Gemma 4 (Local via Ollama)" if HAS_GEMMA else "offline (keyword fallback)",
        "tools": [
            "link_infant_to_mother",
            "extract_adherence_risks",
            "classify_infant_risk",
            "run_full_workflow",
        ],
    })


# --- MCP Tool 1: Link Infant to Mother ---

@mcp.tool
def link_infant_to_mother(infant_id: str) -> dict:
    """Links a newborn to their HIV+ mother across fragmented records using probabilistic identity matching."""
    ctx = _ctx_from_headers()
    auth = parse_auth_context(ctx)

    if not is_authorized(auth):
        log_access_denied(auth.user_id, auth.role, "link_infant_to_mother")
        return {"error": "ACCESS DENIED", "role": auth.role}

    mothers = get_mothers(ctx["fhir_server"], ctx["fhir_token"])
    infant = get_patient_by_id(infant_id, ctx["fhir_server"], ctx["fhir_token"])

    if not infant:
        return {"error": f"Infant {infant_id} not found"}

    candidates = find_mother(infant, mothers)

    if not candidates:
        log_linkage(auth.user_id, auth.role, infant_id, "",
                    0.0, "no_match", auth.organization)
        return {
            "status": "no_match",
            "message": "No confident match found. Flagged for manual review.",
            "infant_id": infant_id,
        }

    linkage = candidates[0]
    log_linkage(auth.user_id, auth.role, infant_id, linkage.mother_id,
                linkage.confidence, "auto_flagged", auth.organization)

    result = {
        "status": "match_found",
        "mother_id": linkage.mother_id,
        "confidence": linkage.confidence,
        "confidence_percent": f"{linkage.confidence:.0%}",
        "candidates_count": len(candidates),
        "data_governance": {
            "audit_log_id": _audit_id(),
            "access_level": "restricted",
            "data_source": "HIV_program (APIN-like)",
        },
    }

    if auth.role == "hiv_specialist":
        result["mother_name"] = linkage.mother_name
        result["art_id"] = linkage.art_id
        result["evidence"] = [
            {"type": e.type, "detail": e.detail, "strength": e.strength}
            for e in linkage.evidence
        ]
        result["all_candidates"] = [
            {
                "mother_id": c.mother_id,
                "mother_name": c.mother_name,
                "confidence": c.confidence,
                "confidence_percent": f"{c.confidence:.0%}",
            }
            for c in candidates
        ]

    return result


# --- MCP Tool 2: Extract Adherence Risks ---

@mcp.tool
def extract_adherence_risks(mother_id: str) -> dict:
    """Extracts hidden ART adherence risk signals from clinical notes using Gemma4."""
    ctx = _ctx_from_headers()
    auth = parse_auth_context(ctx)

    if not is_authorized(auth):
        log_access_denied(auth.user_id, auth.role, "extract_adherence_risks")
        return {"error": "ACCESS DENIED", "role": auth.role}

    mother = get_patient_by_id(mother_id, ctx["fhir_server"], ctx["fhir_token"])
    if not mother:
        return {"error": f"Mother {mother_id} not found"}

    notes = mother.get("clinical_notes", [])
    risks = _run_adherence_extraction(notes) if HAS_GEMMA else _run_adherence_extraction_offline(notes)

    log_data_access(auth.user_id, auth.role, f"mother/{mother_id}/notes",
                    ["clinical_notes"], auth.organization)

    _gov = {
        "audit_log_id": _audit_id(),
        "access_level": "restricted",
        "data_source": "HIV_program (APIN-like)",
    }

    if auth.role == "hiv_specialist":
        return {
            "mother_id": mother_id,
            "risk_count": len(risks),
            "risks": [
                {
                    "indicator": r.indicator,
                    "severity": r.severity,
                    "source_text": r.source_text[:200],
                    "source_date": r.source_date,
                }
                for r in risks
            ],
            "data_governance": _gov,
        }
    else:
        return {
            "mother_id": mother_id,
            "risk_count": len(risks),
            "has_adherence_concerns": len(risks) > 0,
            "data_governance": _gov,
        }


# --- MCP Tool 3: Classify Infant Risk ---

@mcp.tool
def classify_infant_risk(infant_id: str, mother_id: str) -> dict:
    """Classifies infant HIV exposure risk per WHO PMTCT protocol and generates a FHIR Task."""
    ctx = _ctx_from_headers()
    auth = parse_auth_context(ctx)

    if not is_authorized(auth):
        log_access_denied(auth.user_id, auth.role, "classify_infant_risk")
        return {"error": "ACCESS DENIED", "role": auth.role}

    mother = get_patient_by_id(mother_id, ctx["fhir_server"], ctx["fhir_token"])
    infant = get_patient_by_id(infant_id, ctx["fhir_server"], ctx["fhir_token"])

    if not mother:
        return {"error": f"Mother {mother_id} not found"}
    if not infant:
        return {"error": f"Infant {infant_id} not found"}

    notes = mother.get("clinical_notes", [])
    risks = _run_adherence_extraction(notes) if HAS_GEMMA else _run_adherence_extraction_offline(notes)

    risk = classify_risk(mother, risks)

    mothers = get_mothers(ctx["fhir_server"], ctx["fhir_token"])
    candidates = find_mother(infant, mothers)

    if not candidates:
        return {"error": "Could not establish linkage for bridge summary"}

    linkage = candidates[0]
    summary = build_bridge_summary(infant, linkage, risk)

    log_risk_classification(auth.user_id, infant_id, mother_id,
                            risk.level, risk.reasons, auth.organization)

    task = create_fhir_task(summary)
    birth_date = infant.get("birthDate", "")
    care_plan = create_fhir_care_plan(summary, birth_date)

    filtered = filter_output_by_role(summary, auth)
    filtered["fhir_task"] = task
    filtered["data_governance"] = {
        "access_level": "restricted",
        "data_source": "HIV_program (APIN-like)",
        "audit_log_id": f"txn_{hash(infant_id + mother_id) % 100000:05d}",
        "disclosure_note": (
            "Only clinically necessary information shared. "
            "Full HIV records remain in source program."
        ),
    }

    if auth.role == "hiv_specialist":
        filtered["fhir_care_plan"] = care_plan
        filtered["reasons"] = risk.reasons

    return filtered


# --- MCP Tool 4: Full Workflow ---

@mcp.tool
def run_full_workflow(infant_id: str) -> dict:
    """Runs the complete VIGILANT pipeline: link infant to mother → extract adherence risks → classify risk."""
    ctx = _ctx_from_headers()
    auth = parse_auth_context(ctx)

    if not is_authorized(auth):
        log_access_denied(auth.user_id, auth.role, "run_full_workflow")
        return {"error": "ACCESS DENIED", "role": auth.role}

    link_result = link_infant_to_mother(infant_id)
    if link_result.get("status") != "match_found":
        return {"step": "linkage", "result": link_result}

    mother_id = link_result["mother_id"]

    adherence_result = extract_adherence_risks(mother_id)
    classify_result = classify_infant_risk(infant_id, mother_id)

    return {
        "workflow": "complete",
        "agent_collaboration": {
            "step_1": {"agent": "Forensic Linker Agent", "action": "Linked infant to mother", "passed_context_to": "Adherence Intelligence Agent"},
            "step_2": {"agent": "Adherence Intelligence Agent", "action": "Extracted adherence risks from clinical notes", "passed_context_to": "Protocol Guardian Agent"},
            "step_3": {"agent": "Protocol Guardian Agent", "action": "Classified risk and generated FHIR Task + CarePlan"},
        },
        "step_1_linkage": link_result,
        "step_2_adherence": adherence_result,
        "step_3_classification": classify_result,
        "data_governance": {
            "audit_log_id": _audit_id(),
            "access_level": "restricted",
            "data_source": "HIV_program (APIN-like)",
            "disclosure_note": "Only clinically necessary information shared. Full HIV records remain in source program.",
        },
    }


def _bind_socket(host: str, port: int) -> socket.socket | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError:
        sock.close()
        return None
    sock.listen(2048)
    sock.set_inheritable(True)
    return sock


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # stateless_http=True: each request is independent (no persistent SSE sessions).
    # json_response=True: initialize/tool responses are plain JSON, not SSE streams.
    # Both are required for Railway's proxy and for _FHIRCapabilityMiddleware to
    # intercept the initialize response (SSE responses cannot be buffered/patched).
    http_app = mcp.http_app(
        middleware=[Middleware(_FHIRCapabilityMiddleware)],
        stateless_http=True,
        json_response=True,
    )

    candidate_ports = []
    for candidate in (port, 8000, 8501):
        if candidate not in candidate_ports:
            candidate_ports.append(candidate)

    sockets = []
    for candidate in candidate_ports:
        sock = _bind_socket("0.0.0.0", candidate)
        if sock is not None:
            sockets.append(sock)

    if not sockets:
        raise RuntimeError(f"Failed to bind any listening socket from {candidate_ports}")

    config = uvicorn.Config(http_app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    asyncio.run(server.serve(sockets=sockets))
