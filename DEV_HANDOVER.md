# VIGILANT — Agents Assemble Hackathon

**Interoperable Healthcare AI Superpowers**
MCP Server + SHARP Context + FHIR | Runs on [Prompt Opinion](https://www.promptopinion.ai/)

## Quick Start

1. Watch the [Getting Started Video](https://youtu.be/Qvs_QK4meHc)
2. Read `SUBMISSION_GUIDE.md` — full step-by-step checklist
3. Deploy `mcp_server.py` to a server
4. Publish tools to Prompt Opinion Marketplace
5. Record video using `VIDEO_SCRIPT.md`
6. Submit on [DevPost](https://agents-assemble.devpost.com/) before **May 11, 2026**

## Files (15 total)

### Guides (5 docs — read these)
| # | File | Purpose |
|---|------|---------|
| 1 | `README.md` | This file — quick start |
| 2 | `SUBMISSION_GUIDE.md` | **Start here** — full submission checklist + Prompt Opinion integration steps |
| 3 | `VIDEO_SCRIPT.md` | 3-min demo video script |
| 4 | `VIGILANT_Proposal_v2.md` | Design doc — the vision |
| 5 | `VIGILANT_Implementation_Guide.md` | Technical build guide |

### Code (7 files — deploy these)
| # | File | Purpose |
|---|------|---------|
| 6 | `mcp_server.py` | **Main deliverable** — MCP server with 3 tools, publish to Prompt Opinion |
| 7 | `app.py` | Streamlit UI — optional local demo |
| 8 | `agents.py` | 3 AI agents: Forensic Linker, Adherence Miner, Protocol Guardian |
| 9 | `security.py` | SHA-256 audit log + role-based access control |
| 10 | `fhir_layer.py` | FHIR client + resource builders + SHARP context handler |
| 11 | `schemas.py` | Data contracts (Mother, Newborn, RiskFlag, etc.) |
| 12 | `requirements.txt` | Python dependencies |

### Test Data (3 files)
| # | File | Purpose |
|---|------|---------|
| 13 | `data/generate_data.py` | Generates 50 synthetic test cases |
| 14 | `data/mothers.json` | Sample mother records |
| 15 | `data/newborns.json` | Sample newborn records |

## 3 MCP Tools (Superpowers)

| Tool | What It Does |
|------|-------------|
| `link_infant_to_mother` | Matches unlinked infants to mothers across fragmented records |
| `extract_adherence_risks` | Extracts hidden risk signals from clinical notes |
| `classify_infant_risk` | Classifies infant risk (HIGH/MODERATE/LOW) + recommends drug regimen |
