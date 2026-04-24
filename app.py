"""
VIGILANT Streamlit UI — Agents Assemble Hackathon Version.

Hackathon: Agents Assemble
AI Backend: Gemma 4 (Local via Ollama)
Focus: MCP/A2A/SHARP integration demo
"""

import streamlit as st
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from agents import find_mother, extract_adherence_risks, extract_adherence_risks_offline, HAS_GEMMA
from agents import classify_risk, build_bridge_summary
from fhir_layer import create_fhir_task, create_fhir_care_plan
from security import log_risk_classification, get_last_hash

st.set_page_config(page_title="VIGILANT — Agents Assemble", page_icon="🛡️", layout="wide")

# --- Load Data ---
@st.cache_data
def load_data():
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    with open(os.path.join(data_dir, "mothers.json")) as f:
        mothers = json.load(f)
    with open(os.path.join(data_dir, "newborns.json")) as f:
        newborns = json.load(f)
    return mothers, newborns

mothers, newborns = load_data()

# --- Session State ---
for key in ["screen", "selected_infant", "linkage_result", "risk_result", "bridge_summary"]:
    if key not in st.session_state:
        st.session_state[key] = 1 if key == "screen" else None

# --- Sidebar: Role Selection (TRUST FRAMEWORK) ---
st.sidebar.title("🔐 Access Control")
role = st.sidebar.radio("Select Role:", ["👩‍⚕️ Nurse (Ward)", "🔬 HIV Specialist"], index=0)
is_specialist = "Specialist" in role
st.sidebar.divider()
if is_specialist:
    st.sidebar.success("✅ Full access: Risk + Clinical Notes + Evidence")
else:
    st.sidebar.warning("⚠️ Limited access: Risk Level + Action Only")
st.sidebar.caption("VIGILANT enforces role-based data access. Sensitive HIV clinical notes are only visible to authorized HIV specialists.")
st.sidebar.divider()
st.sidebar.info(f"🤖 AI Backend: **{'Gemma 4 (Local via Ollama)' if HAS_GEMMA else 'Offline (keyword fallback)'}**")

# --- Header ---
st.title("🛡️ VIGILANT — Agents Assemble")
st.caption("The Mother-Child HIV Safety Net — MCP + A2A + SHARP + FHIR R4")
st.markdown("_VIGILANT ensures HIV-exposed infants receive the correct prophylaxis — not just any prophylaxis — within the first 6 hours of life._")

# =============================================
# SCREEN 1: Newborn Intake
# =============================================
if st.session_state.screen == 1:
    st.header("Screen 1: Newborn Intake")
    st.markdown("**Select an unlinked newborn to analyze.**")
    for i, nb in enumerate(newborns):
        name = f"{nb['name'][0].get('given', [''])[0]} {nb['name'][0].get('family', '')}".strip()
        col1, col2, col3, col4, col5 = st.columns([3, 2, 3, 2, 2])
        col1.write(f"**{name}**")
        col2.write(nb.get("birthDate", ""))
        col3.write(nb.get("meta", {}).get("facility", ""))
        # 6-hour urgency countdown
        birth_str = nb.get("birthDate", "")
        if birth_str:
            try:
                from datetime import datetime, timedelta
                birth_dt = datetime.strptime(birth_str, "%Y-%m-%d")
                deadline = birth_dt + timedelta(hours=6)
                remaining = deadline - datetime.utcnow()
                if remaining.total_seconds() > 0:
                    hrs = int(remaining.total_seconds() // 3600)
                    mins = int((remaining.total_seconds() % 3600) // 60)
                    col4.warning(f"⏰ {hrs}h {mins}m")
                else:
                    col4.error("🔴 DELAYED PROPHYLAXIS ALERT")
            except ValueError:
                col4.write("")
        else:
            col4.write("")
        if col5.button("Analyze", key=f"analyze_{i}"):
            st.session_state.selected_infant = nb
            st.session_state.screen = 2
            st.rerun()

# =============================================
# SCREEN 2: Review & Verification
# =============================================
elif st.session_state.screen == 2:
    infant = st.session_state.selected_infant
    infant_name = f"{infant['name'][0].get('given', [''])[0]} {infant['name'][0].get('family', '')}".strip()
    st.header("Screen 2: Review & Verification")

    st.info("🤖 **A2A Agent Collaboration:** Forensic Linker Agent → Adherence Intelligence Agent → Protocol Guardian Agent")

    with st.spinner("🔍 **MCP Tool 1 — Forensic Linker:** Searching for mother..."):
        candidates = find_mother(infant, mothers)

    if not candidates:
        st.error("❌ No confident match found. Flagged for manual review.")
        if st.button("← Back"):
            st.session_state.screen = 1
            st.rerun()
    else:
        linkage = candidates[0]
        matched_mother = next((m for m in mothers if m["id"] == linkage.mother_id), None)
        with st.spinner("🧠 **MCP Tool 2 — Adherence Intelligence:** Analyzing clinical notes..."):
            notes = matched_mother.get("clinical_notes", [])
            if HAS_GEMMA:
                adherence_risks = extract_adherence_risks(notes)
            else:
                adherence_risks = extract_adherence_risks_offline(notes)

        with st.spinner("⚙️ **MCP Tool 3 — Protocol Guardian:** Classifying risk..."):
            risk = classify_risk(matched_mother, adherence_risks)
        # Log to audit chain and capture hash for tamper-proof display
        audit_event_id = log_risk_classification(
            user_id=role, infant_id=infant.get("id", ""),
            mother_id=linkage.mother_id, risk_level=risk.level,
            reasons=risk.reasons
        )
        current_hash = get_last_hash()
        summary = build_bridge_summary(infant, linkage, risk, audit_hash=current_hash)
        st.session_state.linkage_result = linkage
        st.session_state.risk_result = risk
        st.session_state.bridge_summary = summary

        left, center, right = st.columns(3)

        with left:
            st.subheader("👶 Newborn")
            st.write(f"**Name:** {infant_name}")
            st.write(f"**DOB:** {infant.get('birthDate', '')}")
            st.write(f"**Facility:** {infant.get('meta', {}).get('facility', '')}")
            st.write(f"**Gender:** {infant.get('gender', '')}")

        with center:
            st.subheader("👩 Matched Mother")
            st.write(f"**Name:** {linkage.mother_name}")
            st.write(f"**ART ID:** {linkage.art_id}")
            st.write(f"**Viral Load:** {risk.viral_load} copies/mL")
            st.write(f"**Confidence:** {linkage.confidence:.0%}")
            if is_specialist:
                st.markdown("**Evidence:**")
                for e in linkage.evidence:
                    st.write(f"  ✓ {e.detail}")

        with right:
            st.subheader("⚠️ Risk Intelligence")
            if risk.level == "HIGH":
                st.error(f"🔴 Risk: **{risk.level}**")
            elif risk.level == "MODERATE":
                st.warning(f"🟡 Risk: **{risk.level}**")
            else:
                st.success(f"🟢 Risk: **{risk.level}**")
            for reason in risk.reasons:
                st.write(f"  → {reason}")

            if is_specialist:
                if adherence_risks:
                    st.markdown("**Adherence Risks Found:**")
                    for r in adherence_risks:
                        st.write(f"  🔸 {r.indicator}")
                        st.caption(f'    Source: "{r.source_text[:100]}"')
                else:
                    st.write("No adherence risks detected.")
            else:
                if adherence_risks:
                    st.info(f"🔒 {len(adherence_risks)} adherence risk(s) detected. Details restricted to HIV Specialist role.")

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirm Linkage", type="primary"):
                st.session_state.screen = 3
                st.rerun()
        with col2:
            if st.button("❌ Reject — Flag for Manual Review"):
                st.session_state.screen = 1
                st.rerun()

# =============================================
# SCREEN 3: Clinical Action (FHIR Task)
# =============================================
elif st.session_state.screen == 3:
    st.header("Screen 3: Clinical Action")
    summary = st.session_state.bridge_summary
    risk = st.session_state.risk_result

    if risk.level == "HIGH":
        st.error(f"🔴 RISK LEVEL: {risk.level}")
    elif risk.level == "MODERATE":
        st.warning(f"🟡 RISK LEVEL: {risk.level}")
    else:
        st.success(f"🟢 RISK LEVEL: {risk.level}")

    st.subheader("📋 Bridge Summary")
    st.markdown(f"""
- **Infant:** {summary.infant_name}
- **Linked to:** {summary.mother_name} ({summary.art_id}) — Confidence: {summary.confidence:.0%}
- **Viral Load:** {summary.viral_load} copies/mL
- **Risk Level:** {summary.risk_level}
    """)
    if is_specialist:
        st.write(f"**Evidence:** {summary.evidence_summary}")

    if risk.level == "HIGH":
        st.warning("⚡ **Recommended:** Start Triple Therapy (AZT + 3TC + NVP/RAL) for 6 weeks")
    elif risk.level == "MODERATE":
        st.info("⚠️ **Recommended:** Assess — Consider Triple Therapy or AZT alone based on clinical judgment")
    else:
        st.info("**Recommended:** Standard prophylaxis — AZT for 2 weeks")

    if summary.adherence_findings:
        if is_specialist:
            st.subheader("⚠️ Adherence Findings")
            for finding in summary.adherence_findings:
                st.write(f"  🔸 {finding}")
        else:
            st.info("🔒 Adherence details restricted to HIV Specialist role.")

    st.divider()
    st.subheader("📄 Generated FHIR Task")
    task = create_fhir_task(summary)
    st.json(task)
    st.success("✅ FHIR Task ready for clinician action")

    st.divider()
    infant = st.session_state.selected_infant
    birth_date = infant.get("birthDate", "")
    st.subheader("📅 12-Month Follow-Up CarePlan")
    care_plan = create_fhir_care_plan(summary, birth_date)
    st.markdown("**Scheduled Activities:**")
    for activity in care_plan.get("activity", []):
        detail = activity.get("detail", {})
        desc = detail.get("description", "")
        period = detail.get("scheduledPeriod", {})
        start = period.get("start", "")[:10]
        st.write(f"  📌 **{desc}** — starts {start}")
    with st.expander("View Full FHIR CarePlan JSON"):
        st.json(care_plan)
    st.success("✅ CarePlan with PCR tests + Bactrim schedule ready")

    st.divider()
    st.subheader("🔐 Data Governance")
    if summary.audit_hash:
        short_hash = f"{summary.audit_hash[:8]}...{summary.audit_hash[-4:]}"
        st.code(f"🛡️ Tamper-Proof Audit ID: {short_hash}", language=None)
    st.markdown("""
- **Access Level:** Restricted
- **Data Source:** HIV Program (APIN-like) — not hospital records
- **Disclosure:** Only clinically necessary information shared. Full HIV records remain in source program.
    """)
    st.caption("VIGILANT does not access hospital records — it securely connects to HIV program systems like APIN and only shares what is necessary.")

    st.divider()
    if st.button("← Analyze Another Newborn"):
        st.session_state.screen = 1
        st.session_state.selected_infant = None
        st.session_state.linkage_result = None
        st.session_state.risk_result = None
        st.session_state.bridge_summary = None
        st.rerun()
