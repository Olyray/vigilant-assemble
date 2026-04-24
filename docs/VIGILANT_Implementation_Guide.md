# VIGILANT — Developer Implementation Guide (v2)

> **Goal:** Build the full VIGILANT demo end-to-end with MCP server + Prompt Opinion integration.
> **Stack:** Python + MCP SDK + FastAPI + Streamlit + OpenAI-compatible LLM + FHIR
> **Timeline:** 1 developer / 1 week
> **Hackathon:** Agents Assemble (Prompt Opinion) — Deadline May 11, 2026

---

## WHAT'S ALREADY BUILT (✅ Done)

The core clinical logic is complete and tested:
- `agents/forensic_linker.py` — probabilistic identity matching
- `agents/adherence_miner.py` — LLM + offline adherence risk extraction
- `agents/protocol_guardian.py` — deterministic risk classification
- `fhir/schemas.py` — data models
- `fhir/resources.py` — FHIR Task + CarePlan builder
- `data/generate_data.py` — synthetic dataset generator
- `app.py` — Streamlit 3-screen UI

## WHAT NEEDS TO BE BUILT (🔴 Remaining)

1. **MCP Server** (`mcp_server.py`) — wrap existing logic as MCP tools
2. **SHARP Context Handler** (`sharp/context.py`) — accept patient context from Prompt Opinion
3. **FHIR Client** (`fhir/client.py`) — fetch data from FHIR server using SHARP tokens
4. **Deployment** — deploy MCP server to Railway/Render
5. **Prompt Opinion Integration** — register, configure agent, publish to Marketplace
6. **Demo Video** — record on Prompt Opinion platform

---

## UPDATED PROJECT STRUCTURE

```
vigilant/
├── data/
│   ├── mothers.json              # ✅ Synthetic FHIR data (local fallback)
│   ├── newborns.json             # ✅ Synthetic FHIR data (local fallback)
│   └── generate_data.py          # ✅ Dataset generator
├── agents/
│   ├── forensic_linker.py        # ✅ Identity resolution
│   ├── adherence_miner.py        # ✅ LLM-based note extraction
│   └── protocol_guardian.py      # ✅ Rule-based risk classification
├── fhir/
│   ├── resources.py              # ✅ FHIR Task + CarePlan builder
│   ├── schemas.py                # ✅ Data models
│   └── client.py                 # 🔴 NEW: FHIR server client (SHARP-aware)
├── sharp/
│   └── context.py                # 🔴 NEW: SHARP context parser
├── mcp_server.py                 # 🔴 NEW: MCP server exposing 3 tools
├── app.py                        # ✅ Streamlit UI (companion app)
├── Dockerfile                    # 🔴 NEW: For deployment
├── requirements.txt              # 🟡 UPDATE: Add mcp, fastapi, httpx
├── .env
└── README.md
```

---

## STEP 1: UPDATE DEPENDENCIES

### File: `requirements.txt`

```
streamlit>=1.30.0
openai>=1.10.0
python-dotenv>=1.0.0
rapidfuzz>=3.5.0
mcp>=1.0.0
fastapi>=0.110.0
uvicorn>=0.27.0
httpx>=0.27.0
```

```bash
pip install mcp fastapi uvicorn httpx
```

---

## STEP 2: SHARP CONTEXT HANDLER (🔴 NEW)

### File: `sharp/context.py`

SHARP is how Prompt Opinion passes patient context (who the patient is, which FHIR server, auth tokens) into your MCP tools.

```python
"""
SHARP Context Handler for VIGILANT.

SHARP (Substitutable Health Applications and Reusable Plugins) context
is passed by the Prompt Opinion platform to provide:
- patientId: The FHIR Patient ID in context
- fhirBaseUrl: The FHIR server base URL
- accessToken: Bearer token for FHIR API authorization

If SHARP context is not available (offline/local mode), falls back to
local JSON data files.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SharpContext:
    patient_id: str
    fhir_base_url: str
    access_token: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "SharpContext":
        """Parse SHARP context from MCP tool input."""
        return cls(
            patient_id=data.get("patientId", ""),
            fhir_base_url=data.get("fhirBaseUrl", ""),
            access_token=data.get("accessToken")
        )

    @classmethod
    def local_fallback(cls) -> "SharpContext":
        """Return a context that signals local JSON fallback mode."""
        return cls(
            patient_id="",
            fhir_base_url="local",
            access_token=None
        )

    @property
    def is_local(self) -> bool:
        return self.fhir_base_url == "local" or not self.fhir_base_url
```

---

## STEP 3: FHIR CLIENT (🔴 NEW)

### File: `fhir/client.py`

This fetches data from a real FHIR server when SHARP context is available, or falls back to local JSON.

```python
"""
FHIR Client for VIGILANT.

Two modes:
1. FHIR Server mode: Uses SHARP context to fetch from a real FHIR server
2. Local mode: Reads from data/mothers.json and data/newborns.json
"""

import json
import os
import httpx
from typing import Optional
from sharp.context import SharpContext


class FhirClient:
    def __init__(self, sharp_context: SharpContext):
        self.ctx = sharp_context

    def _headers(self) -> dict:
        headers = {"Accept": "application/fhir+json"}
        if self.ctx.access_token:
            headers["Authorization"] = f"Bearer {self.ctx.access_token}"
        return headers

    def get_patient(self, patient_id: str) -> Optional[dict]:
        """Fetch a single Patient resource."""
        if self.ctx.is_local:
            return self._local_get_patient(patient_id)

        url = f"{self.ctx.fhir_base_url}/Patient/{patient_id}"
        resp = httpx.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def search_mothers(self, facility: str = None) -> list[dict]:
        """Search for HIV+ mothers (Patients with HIV condition)."""
        if self.ctx.is_local:
            return self._local_get_mothers()

        # Search for female patients with HIV condition at the facility
        params = {"gender": "female", "_count": "200"}
        url = f"{self.ctx.fhir_base_url}/Patient"
        resp = httpx.get(url, headers=self._headers(), params=params, timeout=15)
        resp.raise_for_status()
        bundle = resp.json()
        return [e["resource"] for e in bundle.get("entry", [])]

    def get_observations(self, patient_id: str, code: str = "20447-9") -> list[dict]:
        """Fetch Observations (e.g., viral load) for a patient."""
        if self.ctx.is_local:
            return self._local_get_observations(patient_id)

        params = {"patient": patient_id, "code": code}
        url = f"{self.ctx.fhir_base_url}/Observation"
        resp = httpx.get(url, headers=self._headers(), params=params, timeout=10)
        resp.raise_for_status()
        bundle = resp.json()
        return [e["resource"] for e in bundle.get("entry", [])]

    def get_document_references(self, patient_id: str) -> list[dict]:
        """Fetch DocumentReference (clinical notes) for a patient."""
        if self.ctx.is_local:
            return self._local_get_notes(patient_id)

        params = {"patient": patient_id}
        url = f"{self.ctx.fhir_base_url}/DocumentReference"
        resp = httpx.get(url, headers=self._headers(), params=params, timeout=10)
        resp.raise_for_status()
        bundle = resp.json()
        return [e["resource"] for e in bundle.get("entry", [])]

    # --- Local JSON fallback methods ---

    def _load_json(self, filename: str) -> list:
        path = os.path.join(os.path.dirname(__file__), "..", "data", filename)
        with open(path) as f:
            return json.load(f)

    def _local_get_patient(self, patient_id: str) -> Optional[dict]:
        for dataset in ["newborns.json", "mothers.json"]:
            for p in self._load_json(dataset):
                if p["id"] == patient_id:
                    return p
        return None

    def _local_get_mothers(self) -> list[dict]:
        return self._load_json("mothers.json")

    def _local_get_observations(self, patient_id: str) -> list[dict]:
        for m in self._load_json("mothers.json"):
            if m["id"] == patient_id and "viral_load" in m:
                return [m["viral_load"]]
        return []

    def _local_get_notes(self, patient_id: str) -> list[dict]:
        for m in self._load_json("mothers.json"):
            if m["id"] == patient_id:
                return m.get("clinical_notes", [])
        return []
```

---

## STEP 4: MCP SERVER (🔴 NEW — THE KEY DELIVERABLE)

### File: `mcp_server.py`

This is the most important new file. It wraps your existing logic as an MCP server with 3 tools that Prompt Opinion can invoke.

```python
"""
VIGILANT MCP Server

Exposes 3 tools for the Prompt Opinion platform:
1. link_infant_to_mother — Identity resolution
2. extract_adherence_risks — Clinical note analysis
3. classify_infant_risk — Risk classification + FHIR Task generation

Run with: python mcp_server.py
Or: uvicorn mcp_server:app --host 0.0.0.0 --port 8000
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from sharp.context import SharpContext
from fhir.client import FhirClient
from agents.forensic_linker import find_mother, score_match
from agents.adherence_miner import extract_adherence_risks_offline
from agents.protocol_guardian import classify_risk, build_bridge_summary
from fhir.resources import create_fhir_task, create_fhir_care_plan
from fhir.schemas import AdherenceRisk

server = Server("vigilant")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="link_infant_to_mother",
            description=(
                "Links a newborn infant to their HIV-positive mother using "
                "probabilistic matching (name, phone, facility, birth timing). "
                "Designed for African health facilities where infants are often "
                "registered as 'Baby of [Mother]' with no direct linkage."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "infant_patient_id": {
                        "type": "string",
                        "description": "FHIR Patient ID of the newborn infant"
                    },
                    "sharp_context": {
                        "type": "object",
                        "description": "SHARP context with patientId, fhirBaseUrl, accessToken",
                        "properties": {
                            "patientId": {"type": "string"},
                            "fhirBaseUrl": {"type": "string"},
                            "accessToken": {"type": "string"}
                        }
                    }
                },
                "required": ["infant_patient_id"]
            }
        ),
        Tool(
            name="extract_adherence_risks",
            description=(
                "Analyzes clinical notes (FHIR DocumentReference) from a mother's "
                "prenatal record to extract hidden adherence risk indicators such as "
                "missed pharmacy pick-ups, transport difficulties, and missed ART doses. "
                "Supports English, French, and Portuguese notes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mother_patient_id": {
                        "type": "string",
                        "description": "FHIR Patient ID of the mother"
                    },
                    "clinical_notes": {
                        "type": "array",
                        "description": "Array of clinical note objects with 'content' and 'date' fields",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "date": {"type": "string"}
                            }
                        }
                    },
                    "sharp_context": {
                        "type": "object",
                        "description": "SHARP context (optional — if provided, notes fetched from FHIR server)",
                        "properties": {
                            "patientId": {"type": "string"},
                            "fhirBaseUrl": {"type": "string"},
                            "accessToken": {"type": "string"}
                        }
                    }
                },
                "required": ["mother_patient_id"]
            }
        ),
        Tool(
            name="classify_infant_risk",
            description=(
                "Classifies an HIV-exposed infant's risk level (HIGH/MODERATE/LOW) "
                "based on maternal viral load and adherence risk indicators. "
                "Generates a FHIR Task with Bridge Summary for clinician action. "
                "Uses deterministic rules aligned with CDC/NIH/WHO guidelines."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mother_patient_id": {
                        "type": "string",
                        "description": "FHIR Patient ID of the mother"
                    },
                    "infant_patient_id": {
                        "type": "string",
                        "description": "FHIR Patient ID of the infant"
                    },
                    "viral_load_value": {
                        "type": "number",
                        "description": "Most recent viral load in copies/mL"
                    },
                    "viral_load_date": {
                        "type": "string",
                        "description": "Date of most recent viral load test (ISO format)"
                    },
                    "adherence_risks": {
                        "type": "array",
                        "description": "Adherence risk indicators from extract_adherence_risks tool",
                        "items": {
                            "type": "object",
                            "properties": {
                                "indicator": {"type": "string"},
                                "severity": {"type": "string"},
                                "source_text": {"type": "string"},
                                "source_date": {"type": "string"}
                            }
                        }
                    },
                    "linkage_confidence": {
                        "type": "number",
                        "description": "Confidence score from link_infant_to_mother (0-1)"
                    },
                    "linkage_evidence": {
                        "type": "string",
                        "description": "Evidence summary from linkage"
                    },
                    "mother_name": {"type": "string"},
                    "mother_art_id": {"type": "string"},
                    "sharp_context": {
                        "type": "object",
                        "description": "SHARP context (optional)",
                        "properties": {
                            "patientId": {"type": "string"},
                            "fhirBaseUrl": {"type": "string"},
                            "accessToken": {"type": "string"}
                        }
                    }
                },
                "required": ["mother_patient_id", "infant_patient_id", "viral_load_value"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    # Parse SHARP context (use local fallback if not provided)
    sharp_data = arguments.get("sharp_context", {})
    ctx = SharpContext.from_dict(sharp_data) if sharp_data else SharpContext.local_fallback()
    fhir = FhirClient(ctx)

    if name == "link_infant_to_mother":
        return await _link_infant(arguments, fhir)
    elif name == "extract_adherence_risks":
        return await _extract_risks(arguments, fhir)
    elif name == "classify_infant_risk":
        return await _classify_risk(arguments, fhir)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _link_infant(args: dict, fhir: FhirClient):
    infant_id = args["infant_patient_id"]
    infant = fhir.get_patient(infant_id)
    if not infant:
        return [TextContent(type="text", text=json.dumps({
            "error": f"Infant patient {infant_id} not found",
            "status": "no_match"
        }))]

    mothers = fhir.search_mothers()
    linkage = find_mother(infant, mothers)

    if not linkage:
        return [TextContent(type="text", text=json.dumps({
            "status": "no_match",
            "message": "No confident match found. Flagged for manual review.",
            "infant_id": infant_id
        }))]

    return [TextContent(type="text", text=json.dumps({
        "status": "matched",
        "mother_id": linkage.mother_id,
        "mother_name": linkage.mother_name,
        "art_id": linkage.art_id,
        "confidence": linkage.confidence,
        "evidence": [
            {"type": e.type, "detail": e.detail, "strength": e.strength}
            for e in linkage.evidence
        ]
    }))]


async def _extract_risks(args: dict, fhir: FhirClient):
    mother_id = args["mother_patient_id"]

    # Get notes from args or fetch from FHIR
    notes = args.get("clinical_notes")
    if not notes:
        notes = fhir.get_document_references(mother_id)

    # Use offline extraction (no API key dependency for hackathon)
    risks = extract_adherence_risks_offline(notes)

    return [TextContent(type="text", text=json.dumps({
        "mother_id": mother_id,
        "risk_count": len(risks),
        "risks": [
            {
                "indicator": r.indicator,
                "severity": r.severity,
                "source_text": r.source_text,
                "source_date": r.source_date
            }
            for r in risks
        ]
    }))]


async def _classify_risk(args: dict, fhir: FhirClient):
    # Build a mother-like dict for the protocol guardian
    mother_data = {
        "viral_load": {
            "valueQuantity": {"value": args.get("viral_load_value", 0)},
            "effectiveDateTime": args.get("viral_load_date", "")
        }
    }

    # Convert adherence risks from dicts to AdherenceRisk objects
    adherence_risks = [
        AdherenceRisk(
            indicator=r.get("indicator", ""),
            source_text=r.get("source_text", ""),
            source_date=r.get("source_date", ""),
            severity=r.get("severity", "moderate")
        )
        for r in args.get("adherence_risks", [])
    ]

    risk = classify_risk(mother_data, adherence_risks)

    # Build bridge summary
    from fhir.schemas import LinkageResult, Evidence, BridgeSummary
    infant = fhir.get_patient(args["infant_patient_id"]) or {
        "name": [{"given": ["Unknown"], "family": "Infant"}]
    }

    linkage = LinkageResult(
        mother_id=args["mother_patient_id"],
        mother_name=args.get("mother_name", "Unknown"),
        art_id=args.get("mother_art_id", ""),
        confidence=args.get("linkage_confidence", 0),
        evidence=[Evidence("summary", args.get("linkage_evidence", ""), 1.0)]
    )

    summary = build_bridge_summary(infant, linkage, risk)
    task = create_fhir_task(summary)
    care_plan = create_fhir_care_plan(summary, infant.get("birthDate", ""))

    return [TextContent(type="text", text=json.dumps({
        "risk_level": risk.level,
        "reasons": risk.reasons,
        "viral_load": risk.viral_load,
        "adherence_risk_count": len(adherence_risks),
        "bridge_summary": {
            "infant_name": summary.infant_name,
            "mother_name": summary.mother_name,
            "art_id": summary.art_id,
            "confidence": summary.confidence,
            "viral_load": summary.viral_load,
            "risk_level": summary.risk_level,
            "adherence_findings": summary.adherence_findings,
            "recommended_action": summary.recommended_action
        },
        "fhir_task": task,
        "fhir_care_plan": care_plan
    }, default=str))]


# --- Entry point ---
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## STEP 5: DOCKERFILE FOR DEPLOYMENT (🔴 NEW)

### File: `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# MCP server runs on stdio by default
# For HTTP transport, use: CMD ["uvicorn", "mcp_server:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["python", "mcp_server.py"]
```

---

## STEP 6: DEPLOYMENT (Railway / Render)

### Option A: Railway (Recommended — easiest)

1. Push code to GitHub
2. Go to [railway.app](https://railway.app)
3. Click "New Project" → "Deploy from GitHub"
4. Select your repo
5. Railway auto-detects the Dockerfile
6. Set environment variables: `OPENAI_API_KEY` (if using LLM mode)
7. Deploy → get public URL (e.g., `https://vigilant-production.up.railway.app`)

### Option B: Render

1. Push code to GitHub
2. Go to [render.com](https://render.com)
3. New → Web Service → connect GitHub repo
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `python mcp_server.py`
6. Deploy → get public URL

### Option C: ngrok (Quick local tunnel for testing)

```bash
# Terminal 1: Run MCP server
python mcp_server.py

# Terminal 2: Expose via ngrok
ngrok http 8000
# → gives you a public URL like https://abc123.ngrok.io
```

---

## STEP 7: PROMPT OPINION INTEGRATION

### 7a. Register on Prompt Opinion
1. Go to [promptopinion.com](https://promptopinion.com)
2. Create a free account

### 7b. Register Your MCP Server
1. In Prompt Opinion dashboard → "Create New Project"
2. Select **"MCP Server"** (Option 1: Build a Superpower)
3. Enter your deployed MCP server URL
4. The platform will discover your 3 tools automatically

### 7c. Configure A2A Agent (Optional — Option 2)
1. In Prompt Opinion → "Create Agent"
2. Name: "VIGILANT — Mother-Child HIV Safety Net"
3. Description: Use the one-line pitch from the proposal
4. Equip the agent with your 3 MCP tools
5. Configure the orchestration:
   - Step 1: Call `link_infant_to_mother` with SHARP context
   - Step 2: Call `extract_adherence_risks` with mother ID from step 1
   - Step 3: Call `classify_infant_risk` with results from steps 1 + 2
6. The platform handles A2A communication — no code needed

### 7d. Publish to Marketplace
1. In your project settings → "Publish"
2. Add description, tags (HIV, PMTCT, pediatric, Africa, FHIR)
3. Submit for listing

---

## STEP 8: END-TO-END TESTING

### Test 1: MCP Server locally
```bash
python mcp_server.py
# Server starts on stdio — use MCP client to test
```

### Test 2: Streamlit companion app
```bash
streamlit run app.py
# Open http://localhost:8501
# Click "Analyze" on a "Baby of Banda" record
# Verify 3-panel view with confidence, evidence, adherence risks
# Click "Confirm Linkage" → see FHIR Task
```

### Test 3: On Prompt Opinion
1. Open your agent in the Prompt Opinion workspace
2. Set SHARP context to a test infant patient ID
3. Invoke the workflow
4. Verify all 3 tools execute and produce correct output
5. Verify the FHIR Task is generated

### Test the "WOW" case
Find a newborn whose mother has **low VL but adherence issues** (hidden risk).
The system should flag it as HIGH risk due to adherence findings — this is the demo moment.

---

## STEP 9: RECORD THE DEMO VIDEO (Day 7)

**Must show VIGILANT working on Prompt Opinion platform.**

1. **0:00–0:20 (Hook):** Show the unlinked newborn on Prompt Opinion. Say the hook line.
2. **0:20–0:50 (Problem):** Show fragmented records — infant and mother are separate.
3. **0:50–1:30 (WOW):** Show VIGILANT agent running:
   - Tool 1: Forensic Linker finds mother (confidence + evidence)
   - Tool 2: Adherence Miner extracts "missed pharmacy pickup"
   - Tool 3: Protocol Guardian → **HIGH RISK**
4. **1:30–2:00 (Human Verification):** Clinician confirms linkage.
5. **2:00–2:30 (Action):** Show FHIR Task with Bridge Summary.
6. **2:30–3:00 (Impact):** Closing statement about 130,000 children + MCP/A2A standards.

---

## QUICK REFERENCE: FILE CHECKLIST

| File | Status | Purpose | Priority |
|---|---|---|---|
| `data/generate_data.py` | ✅ Done | Synthetic FHIR dataset | — |
| `data/mothers.json` | ✅ Done | 50 mothers with VL + notes | — |
| `data/newborns.json` | ✅ Done | 50 infants with dirty names | — |
| `fhir/schemas.py` | ✅ Done | Data models | — |
| `fhir/resources.py` | ✅ Done | FHIR Task + CarePlan builder | — |
| `fhir/client.py` | 🔴 New | FHIR server client (SHARP-aware) | Day 3 |
| `sharp/context.py` | 🔴 New | SHARP context parser | Day 3 |
| `agents/forensic_linker.py` | ✅ Done | Identity resolution | — |
| `agents/adherence_miner.py` | ✅ Done | LLM + offline note extraction | — |
| `agents/protocol_guardian.py` | ✅ Done | Risk classification rules | — |
| `mcp_server.py` | 🔴 New | **MCP server (KEY DELIVERABLE)** | Day 3 |
| `Dockerfile` | 🔴 New | Deployment container | Day 4 |
| `app.py` | ✅ Done | Streamlit companion UI | — |
| `requirements.txt` | 🟡 Update | Add mcp, fastapi, httpx | Day 3 |

---

## NOTES FOR THE FULL-STACK ENGINEER

### What's the #1 priority?
**`mcp_server.py`** — this is what makes VIGILANT a valid hackathon submission. Without it, we have a standalone Streamlit app that doesn't meet the Prompt Opinion integration requirement.

### Do I need to rewrite the existing agents?
**No.** The existing `forensic_linker.py`, `adherence_miner.py`, and `protocol_guardian.py` are the core logic. The MCP server just wraps them. Don't touch the clinical logic.

### Do I need an OpenAI API key?
**Not for the hackathon demo.** The `adherence_miner.py` has an `extract_adherence_risks_offline()` fallback that uses keyword matching. The MCP server uses this by default. If you have a key, set it in `.env` for better extraction.

### What about the Streamlit app?
**Keep it.** It's a companion interface for local clinic use. But the **primary demo must be on Prompt Opinion**. The Streamlit app is secondary.

### How does SHARP context work?
Prompt Opinion passes a JSON object with `patientId`, `fhirBaseUrl`, and `accessToken` when it calls your MCP tools. The `sharp/context.py` module parses this. If no SHARP context is provided (local mode), the system falls back to reading from `data/mothers.json` and `data/newborns.json`.

### What FHIR server should I use?
For the hackathon: either use the **local JSON fallback** (simplest) or load synthetic data into **HAPI FHIR** (`https://hapi.fhir.org/baseR4`). A real FHIR server is impressive but not required — the JSON fallback demonstrates the same clinical logic.

### Deployment checklist
- [ ] MCP server runs locally (`python mcp_server.py`)
- [ ] MCP server deployed to Railway/Render with public URL
- [ ] Registered on Prompt Opinion
- [ ] MCP tools discoverable on Prompt Opinion
- [ ] A2A agent configured (optional but recommended)
- [ ] Published to Prompt Opinion Marketplace
- [ ] Demo video recorded (under 3 minutes, on Prompt Opinion)
