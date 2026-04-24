# VIGILANT — Agents Assemble Video Script (≤3 minutes)

## Pre-Production Notes
- **Length:** 2:30–3:00 max
- **Must show:** Project functioning **within the Prompt Opinion platform**
- **Tone:** Technical but accessible — show interoperability in action
- **Upload to:** Any video platform (DevPost submission)

---

## [0:00–0:20] THE HOOK — The Problem (20 sec)

**[Screen: Hospital corridor → data silos visualization]**

> *"In healthcare, AI tools are powerful — but they're trapped in silos. A risk detection model can't talk to a patient matching system. A drug protocol engine can't access clinical notes. Every hospital builds the same plumbing from scratch."*

---

## [0:20–0:50] THE SOLUTION — What VIGILANT Is (30 sec)

**[Screen: VIGILANT architecture — 3 MCP tools on Prompt Opinion]**

> *"VIGILANT changes that. We built three healthcare AI superpowers as MCP tools — and published them to the Prompt Opinion Marketplace. Any agent, anywhere, can now invoke them."*

> *"Tool 1: **Link Infant to Mother** — forensic matching across fragmented records."*
> *"Tool 2: **Extract Adherence Risks** — AI-powered clinical note analysis."*  
> *"Tool 3: **Classify Infant Risk** — WHO-protocol risk scoring with drug recommendations."*

> *"Each tool speaks SHARP — meaning patient context flows automatically through FHIR tokens. No custom auth code needed."*

---

## [0:50–1:50] THE DEMO — Inside Prompt Opinion (60 sec)

**[Screen: Prompt Opinion platform — logged in]**

> *"Let me show you this running live inside Prompt Opinion."*

**[Show: Marketplace listing for VIGILANT tools]**

> *"Here are our three tools published in the Marketplace. Any organization can discover and invoke them."*

**[Show: Agent workspace — invoke link_infant_to_mother]**

> *"I'll start with a real scenario. Baby record NB-042 — born at a rural clinic, no mother linked. I invoke the Forensic Linker tool..."*

> *"It returns the top 3 candidate mothers, ranked by confidence. The best match is 87% — it caught a name misspelling and matched on facility + birth timing."*

**[Show: invoke extract_adherence_risks with SHARP context]**

> *"Now I pass the mother's patient ID through SHARP context. The Adherence Miner reads her clinical notes and extracts two risk signals: missed ARV doses and a late appointment. Notice — the FHIR token propagated automatically through the call chain."*

**[Show: invoke classify_infant_risk]**

> *"Finally, the Protocol Guardian takes everything — the linkage, the adherence risks, the mother's viral load — and classifies this infant as HIGH RISK. It recommends AZT + 3TC + NVP with a 6-hour urgency window."*

**[Show: Role-based output — nurse vs specialist view]**

> *"And the output adapts to who's asking. A nurse sees the risk flag and drug regimen. A specialist sees the full clinical detail."*

---

## [1:50–2:25] THE ARCHITECTURE — Why It Matters (35 sec)

**[Screen: Architecture diagram — MCP + A2A + SHARP + FHIR]**

> *"Here's what makes this special. VIGILANT isn't a monolith — it's composable."*

> *"Each tool is an independent MCP server. Prompt Opinion handles the A2A orchestration. SHARP propagates the patient context. And FHIR ensures the data is standards-compliant."*

> *"Any hospital can pick up one tool or all three. They can compose VIGILANT's tools with other agents in the Marketplace. That's the power of interoperability."*

**[Screen: Audit log with SHA-256 hashes]**

> *"And every invocation is logged in a tamper-proof audit chain — because in healthcare, you need to prove what happened and why."*

---

## [2:25–2:50] THE IMPACT (25 sec)

**[Screen: Statistics + map]**

> *"In Nigeria alone, 21,000 infants are infected with HIV annually because of broken data linkages (UNAIDS, 2023). VIGILANT's tools can be invoked by any agent on the Prompt Opinion platform — meaning any clinic, any country, any workflow can use them."*

> *"We didn't just build an app. We built healthcare superpowers that any AI agent can assemble."*

---

## [2:50–3:00] THE CLOSE (10 sec)

**[Screen: VIGILANT logo + Prompt Opinion + "Agents Assemble"]**

> *"VIGILANT. Three superpowers. One mission. Agents Assemble."*

---

## Post-Production Checklist
- [ ] Video shows VIGILANT running **inside Prompt Opinion platform** (required)
- [ ] All 3 MCP tools demonstrated
- [ ] SHARP context propagation visible
- [ ] Under 3 minutes
- [ ] Upload and attach to DevPost submission
