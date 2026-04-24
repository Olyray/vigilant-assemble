# VIGILANT — Agents Assemble Submission Guide

## Overview

**Platform:** [Prompt Opinion](https://www.promptopinion.ai/)
**Submission:** [DevPost](https://agents-assemble.devpost.com/)
**Deadline:** May 11, 2026
**Prize Pool:** $25,000 (Grand Prize: $7,500)

We are building **Option 1: A Superpower (MCP Server)** — three MCP tools that any agent on Prompt Opinion can invoke.

---

## Step-by-Step: What Your Dev Does

### Step 1: Set Up Accounts
- [ ] Create a free account at [promptopinion.ai](https://www.promptopinion.ai/)
- [ ] Register on the [Agents Assemble Hackathon](https://agents-assemble.devpost.com/)
- [ ] Watch the [Getting Started Video](https://youtu.be/Qvs_QK4meHc) — this shows exactly how Prompt Opinion works

### Step 2: Deploy the MCP Server
- [ ] Clone/copy the `agents_assemble/` folder to your server (any cloud: AWS, GCP, Azure, Railway, Render, etc.)
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Set environment variable: `OPENAI_API_KEY=your-key` (or leave unset to use offline mode)
- [ ] Start the MCP server: `python mcp_server.py`
- [ ] Verify it's running: `curl http://your-server:8001/health`
- [ ] The server exposes 3 MCP tools:
  - `link_infant_to_mother` — Forensic Linker
  - `extract_adherence_risks` — Adherence Miner
  - `classify_infant_risk` — Protocol Guardian

### Step 3: Integrate with Prompt Opinion
- [ ] Log into Prompt Opinion
- [ ] Go to **Marketplace** → **Publish New Tool**
- [ ] Register your MCP server URL (e.g., `https://your-server.com:8001`)
- [ ] Configure each tool with its name, description, and input schema
- [ ] Enable **SHARP context** — map the platform's patient context to your tool's `sharp_context` parameter:
  - `patientId` → the FHIR patient ID
  - `fhirBaseUrl` → the FHIR server URL
  - `accessToken` → the OAuth bearer token
- [ ] Test each tool from within the Prompt Opinion workspace
- [ ] Publish to the Marketplace

### Step 4: Configure A2A Agent (Optional, No Code Needed)
- [ ] In Prompt Opinion, go to **Agents** → **Create New Agent**
- [ ] Name: "VIGILANT — Infant HIV Risk Agent"
- [ ] Description: "Identifies high-risk HIV-exposed infants by linking records, analyzing adherence, and classifying risk per WHO PMTCT protocols"
- [ ] Equip the agent with your 3 published MCP tools
- [ ] The platform handles A2A/COIN communication automatically — no code needed
- [ ] Test the agent by asking it natural language questions like:
  - "Link baby NB-042 to their mother"
  - "What are the adherence risks for patient M-015?"
  - "Classify the risk for newborn NB-042"

### Step 5: Record Demo Video
- [ ] Follow `VIDEO_SCRIPT.md` for the script
- [ ] **Must show the project working inside Prompt Opinion** (this is required)
- [ ] Keep to ≤ 3 minutes
- [ ] Show all 3 MCP tools being invoked
- [ ] Show SHARP context flowing through the call chain

### Step 6: Submit on DevPost
- [ ] Go to [agents-assemble.devpost.com](https://agents-assemble.devpost.com/)
- [ ] Create a new submission
- [ ] **Project Name:** VIGILANT — Infant HIV Risk Detection
- [ ] **Description:** Paste a summary from `VIGILANT_Proposal_v2.md`
- [ ] **What it does:** Three MCP tools for infant-mother linkage, adherence risk extraction, and WHO-protocol risk classification
- [ ] **How we built it:** Python MCP server + SHARP context + FHIR resources + SHA-256 audit chain
- [ ] **Attach:** Demo video link
- [ ] **Attach:** GitHub repo link (create a public repo with the `agents_assemble/` contents)
- [ ] **Attach:** Link to your published tools on Prompt Opinion Marketplace
- [ ] Submit before **May 11, 2026**

---

## Prompt Opinion SHARP Context — How It Works

When a clinician uses Prompt Opinion inside an EHR, the platform automatically provides SHARP context:

```json
{
  "patientId": "Patient/12345",
  "fhirBaseUrl": "https://fhir.hospital.org/r4",
  "accessToken": "eyJhbGciOiJSUzI1NiIs..."
}
```

Your MCP tools receive this in the `sharp_context` parameter. The `fhir_layer.py` file handles parsing it and using the token to fetch patient data from the FHIR server. This means:
- No custom auth code needed
- Patient context flows automatically through multi-agent call chains
- Any agent on the platform can invoke your tools with the right patient context

---

## Files in This Folder

| # | File | What It Is | Dev Action |
|---|------|-----------|------------|
| 1 | `README.md` | Quick start guide | Read first |
| 2 | `VIGILANT_Proposal_v2.md` | Design doc — what & why | Read for context |
| 3 | `VIGILANT_Implementation_Guide.md` | Build guide — how | Read for architecture |
| 4 | `SUBMISSION_GUIDE.md` | **This file** — step-by-step submission | Follow the checklist |
| 5 | `VIDEO_SCRIPT.md` | Demo video script | Record from this |
| 6 | `requirements.txt` | Python dependencies | `pip install -r requirements.txt` |
| 7 | `schemas.py` | Data contracts | Don't touch — shared types |
| 8 | `agents.py` | 3 AI agents (Linker, Miner, Guardian) | Core logic — review & test |
| 9 | `security.py` | Audit log + RBAC | Compliance layer |
| 10 | `fhir_layer.py` | FHIR client + SHARP context | Integration layer |
| 11 | `app.py` | Streamlit UI | Optional local demo |
| 12 | `mcp_server.py` | **MCP server** — publish this to Prompt Opinion | The main deliverable |
| 13 | `data/generate_data.py` | Test data generator | Run to create test cases |
| 14 | `data/mothers.json` | Sample mothers | Test data |
| 15 | `data/newborns.json` | Sample newborns | Test data |

---

## Reading Order for Your Dev

1. **Watch** the [Getting Started Video](https://youtu.be/Qvs_QK4meHc)
2. **Read** `SUBMISSION_GUIDE.md` (this file) — understand the full process
3. **Read** `VIGILANT_Proposal_v2.md` — understand the vision
4. **Read** `VIGILANT_Implementation_Guide.md` — understand the architecture
5. **Deploy** `mcp_server.py` to a server
6. **Publish** to Prompt Opinion Marketplace
7. **Record** video using `VIDEO_SCRIPT.md`
8. **Submit** on DevPost
