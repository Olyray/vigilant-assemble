# 🛡️ VIGILANT: The Mother-Child HIV Safety Net

**Interoperable Healthcare AI Superpowers for the Prompt Opinion Ecosystem**

> **Winner/Submission for the Agents Assemble Hackathon (May 2026)** > Built at the intersection of **MCP, A2A, and FHIR**.

## 🎯 The Endgame Challenge

Every year, roughly **130,000 children** are newly infected with HIV, predominantly in Sub-Saharan Africa. The core failure isn't a lack of medication—it's a lack of **maternal clinical context** at the moment of birth. When delivery wards can't access fragmented HIV records, newborns miss the critical **6-hour window** for high-risk prophylaxis.

## 🦸‍♂️ Our Superpowers (MCP Tools)

VIGILANT provides three composable AI superpowers, exposed as an **MCP Server**, that any agent on the Prompt Opinion platform can invoke:

1. **`link_infant_to_mother` (Forensic Linker):** Probabilistically matches unlinked newborns ("Baby of X") to HIV+ mothers across fragmented records.
2. **`extract_adherence_risks` (Adherence Miner):** Uses AI to extract hidden risk signals (e.g., missed pharmacy pickups, transport issues) from unstructured clinical notes.
3. **`classify_infant_risk` (Protocol Guardian):** A deterministic, WHO-aligned rule engine that combines viral load and adherence scores to classify risk (HIGH/MODERATE/LOW) and generate actionable **FHIR Tasks** and **CarePlans**.
4. **`run_full_workflow`:** Orchestrates the entire safety net in a single call chain.

## 🔌 Platform Interoperability

VIGILANT solves the "plumbing" problem of healthcare AI:

- **SHARP Context:** Natively accepts `patientId`, `fhirBaseUrl`, and `accessToken` directly from Prompt Opinion EHR sessions.
- **FHIR R4 Native:** All inputs and outputs map to standard FHIR resources (`Patient`, `Observation`, `DocumentReference`, `Task`, `CarePlan`).
- **NDPA 2023 Compliant:** Features an immutable **SHA-256 Hash-Chained Audit Log** and Role-Based Access Control (RBAC) to ensure data minimization and sovereignty.

## 🚀 How to Run & Deploy

### Local Development

```bash
pip install -r requirements.txt
python mcp_server.py
# Server runs on port 8000
```
