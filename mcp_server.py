"""
VIGILANT MCP Server — Agents Assemble Hackathon Version.

Exposes 3 MCP tools for the Prompt Opinion platform:
1. link_infant_to_mother — Probabilistic identity matching
2. extract_adherence_risks — AI-powered clinical note analysis (Gemma 4 via Ollama)
3. classify_infant_risk — Rule-based risk classification + FHIR Task

Uses SHARP context for healthcare data propagation and role-based access.

Hackathon: Agents Assemble
AI Backend: Gemma 4 (Local via Ollama)
"""

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional

from agents import (
    find_mother, extract_adherence_risks, extract_adherence_risks_offline,
    HAS_GEMMA, classify_risk, build_bridge_summary
)
from fhir_layer import (
    create_fhir_task, create_fhir_care_plan,
    get_mothers, get_newborns, get_patient_by_id,
    parse_sharp_context
)
from security import (
    parse_auth_context, is_authorized, filter_output_by_role,
    log_linkage, log_risk_classification, log_access_denied, log_data_access, verify_chain
)

app = FastAPI(
    title="VIGILANT MCP Server — Agents Assemble",
    description="Mother-Child HIV Safety Net — MCP tools for linking newborns to maternal HIV records (Gemma 4 via Ollama)",
    version="1.0.0",
)


def _audit_id() -> str:
    """Generate a unique audit log ID for data governance tracking."""
    return f"audit_{uuid.uuid4().hex[:12]}"


# --- Pydantic Models for MCP Tool Inputs ---

class LinkInfantInput(BaseModel):
    infant_id: str
    sharp_context: Optional[dict] = {}

class AdherenceInput(BaseModel):
    mother_id: str
    sharp_context: Optional[dict] = {}

class ClassifyRiskInput(BaseModel):
    infant_id: str
    mother_id: str
    sharp_context: Optional[dict] = {}

class FullWorkflowInput(BaseModel):
    infant_id: str
    sharp_context: Optional[dict] = {}


# --- Health Check ---

@app.get("/")
def health_check():
    return {
        "service": "VIGILANT MCP Server — Agents Assemble",
        "status": "running",
        "ai_backend": "Gemma 4 (Local via Ollama)" if HAS_GEMMA else "offline (keyword fallback)",
        "tools": [
            "link_infant_to_mother",
            "extract_adherence_risks",
            "classify_infant_risk",
            "run_full_workflow",
        ],
    }


# --- MCP Tool 1: Link Infant to Mother ---

@app.post("/tools/link_infant_to_mother")
def tool_link_infant_to_mother(input: LinkInfantInput):
    """MCP Tool: Probabilistic identity matching for 'Baby of X' cases."""
    ctx = parse_sharp_context(input.sharp_context or {})
    auth = parse_auth_context(ctx)

    if not is_authorized(auth):
        log_access_denied(auth.user_id, auth.role, "link_infant_to_mother")
        return {"error": "ACCESS DENIED", "role": auth.role}

    mothers = get_mothers(ctx.get("fhir_server", ""), ctx.get("fhir_token", ""))
    infant = get_patient_by_id(input.infant_id, ctx.get("fhir_server", ""), ctx.get("fhir_token", ""))

    if not infant:
        return {"error": f"Infant {input.infant_id} not found"}

    candidates = find_mother(infant, mothers)

    if not candidates:
        log_linkage(auth.user_id, auth.role, input.infant_id, "",
                    0.0, "no_match", auth.organization)
        return {
            "status": "no_match",
            "message": "No confident match found. Flagged for manual review.",
            "infant_id": input.infant_id,
        }

    linkage = candidates[0]
    log_linkage(auth.user_id, auth.role, input.infant_id, linkage.mother_id,
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

@app.post("/tools/extract_adherence_risks")
def tool_extract_adherence_risks(input: AdherenceInput):
    """MCP Tool: AI-powered clinical note analysis for hidden adherence risks."""
    ctx = parse_sharp_context(input.sharp_context or {})
    auth = parse_auth_context(ctx)

    if not is_authorized(auth):
        log_access_denied(auth.user_id, auth.role, "extract_adherence_risks")
        return {"error": "ACCESS DENIED", "role": auth.role}

    mother = get_patient_by_id(input.mother_id, ctx.get("fhir_server", ""), ctx.get("fhir_token", ""))
    if not mother:
        return {"error": f"Mother {input.mother_id} not found"}

    notes = mother.get("clinical_notes", [])

    if HAS_GEMMA:
        risks = extract_adherence_risks(notes)
    else:
        risks = extract_adherence_risks_offline(notes)

    log_data_access(auth.user_id, auth.role, f"mother/{input.mother_id}/notes",
                    ["clinical_notes"], auth.organization)

    _gov = {
        "audit_log_id": _audit_id(),
        "access_level": "restricted",
        "data_source": "HIV_program (APIN-like)",
    }

    if auth.role == "hiv_specialist":
        return {
            "mother_id": input.mother_id,
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
            "mother_id": input.mother_id,
            "risk_count": len(risks),
            "has_adherence_concerns": len(risks) > 0,
            "data_governance": _gov,
        }


# --- MCP Tool 3: Classify Infant Risk ---

@app.post("/tools/classify_infant_risk")
def tool_classify_infant_risk(input: ClassifyRiskInput):
    """MCP Tool: Rule-based risk classification + FHIR Task generation."""
    ctx = parse_sharp_context(input.sharp_context or {})
    auth = parse_auth_context(ctx)

    if not is_authorized(auth):
        log_access_denied(auth.user_id, auth.role, "classify_infant_risk")
        return {"error": "ACCESS DENIED", "role": auth.role}

    mother = get_patient_by_id(input.mother_id, ctx.get("fhir_server", ""), ctx.get("fhir_token", ""))
    infant = get_patient_by_id(input.infant_id, ctx.get("fhir_server", ""), ctx.get("fhir_token", ""))

    if not mother:
        return {"error": f"Mother {input.mother_id} not found"}
    if not infant:
        return {"error": f"Infant {input.infant_id} not found"}

    notes = mother.get("clinical_notes", [])
    risks = extract_adherence_risks(notes) if HAS_GEMMA else extract_adherence_risks_offline(notes)

    risk = classify_risk(mother, risks)

    mothers = get_mothers(ctx.get("fhir_server", ""), ctx.get("fhir_token", ""))
    candidates = find_mother(infant, mothers)

    if not candidates:
        return {"error": "Could not establish linkage for bridge summary"}

    linkage = candidates[0]
    summary = build_bridge_summary(infant, linkage, risk)

    log_risk_classification(auth.user_id, input.infant_id, input.mother_id,
                            risk.level, risk.reasons, auth.organization)

    task = create_fhir_task(summary)
    birth_date = infant.get("birthDate", "")
    care_plan = create_fhir_care_plan(summary, birth_date)

    filtered = filter_output_by_role(summary, auth)
    filtered["fhir_task"] = task

    filtered["data_governance"] = {
        "access_level": "restricted",
        "data_source": "HIV_program (APIN-like)",
        "audit_log_id": f"txn_{hash(input.infant_id + input.mother_id) % 100000:05d}",
        "disclosure_note": (
            "Only clinically necessary information shared. "
            "Full HIV records remain in source program."
        ),
    }

    if auth.role == "hiv_specialist":
        filtered["fhir_care_plan"] = care_plan
        filtered["reasons"] = risk.reasons

    return filtered


# --- Bonus: Full Workflow (Tool 1 + 2 + 3 in sequence) ---

@app.post("/tools/run_full_workflow")
def tool_run_full_workflow(input: FullWorkflowInput):
    """Run the complete VIGILANT workflow: Link → Extract → Classify."""
    ctx = parse_sharp_context(input.sharp_context or {})
    auth = parse_auth_context(ctx)

    if not is_authorized(auth):
        log_access_denied(auth.user_id, auth.role, "run_full_workflow")
        return {"error": "ACCESS DENIED", "role": auth.role}

    link_result = tool_link_infant_to_mother(
        LinkInfantInput(infant_id=input.infant_id, sharp_context=input.sharp_context)
    )
    if link_result.get("status") != "match_found":
        return {"step": "linkage", "result": link_result}

    mother_id = link_result["mother_id"]

    adherence_result = tool_extract_adherence_risks(
        AdherenceInput(mother_id=mother_id, sharp_context=input.sharp_context)
    )

    classify_result = tool_classify_infant_risk(
        ClassifyRiskInput(
            infant_id=input.infant_id,
            mother_id=mother_id,
            sharp_context=input.sharp_context,
        )
    )

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


# --- Run with uvicorn ---

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
