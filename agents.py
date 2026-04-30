"""
VIGILANT AI Agents — All three agents in one file.

Agent 1: Forensic Linker — Links "Baby of X" infants to their mothers
Agent 2: Adherence Miner — Extracts hidden adherence risks from clinical notes (Gemma 4 via Ollama)
Agent 3: Protocol Guardian — Classifies infant risk (HIGH/MODERATE/LOW) + generates actions

Hackathon: Agents Assemble
AI Backend: Gemma 4 (Local via Ollama)
"""

import json
import os
from datetime import datetime, timedelta

try:
    import ollama as _ollama_lib
    _HAS_OLLAMA_LIB = True
except ImportError:
    _HAS_OLLAMA_LIB = False

from rapidfuzz import fuzz

from schemas import (
    Evidence, LinkageResult, AdherenceRisk, RiskClassification, BridgeSummary
)

# =============================================
# Gemma 4 via Ollama Setup (for Adherence Miner)
# =============================================

GEMMA_MODEL = os.environ.get("GEMMA_MODEL", "gemma4:e2b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

HAS_GEMMA = False
_ollama_client = None
if _HAS_OLLAMA_LIB:
    try:
        _ollama_client = _ollama_lib.Client(host=OLLAMA_HOST)
        _ollama_client.list()
        HAS_GEMMA = True
    except Exception:
        HAS_GEMMA = False


# =============================================================================
#  AGENT 1: FORENSIC LINKER
#  Links "Baby of X" infants to their mothers using probabilistic matching
# =============================================================================

def extract_mother_name_from_infant(infant):
    """Parse 'Baby of X' patterns to extract possible mother name."""
    given = infant["name"][0].get("given", [""])[0]
    family = infant["name"][0].get("family", "")
    if given.lower().startswith("baby of "):
        extracted_first = given[8:].strip()
        return extracted_first, family
    if given.lower() in ["unnamed male", "unnamed female", "baby boy", "baby girl"]:
        return None, family
    return given, family


def _build_phone_usage_map(mothers: list) -> dict:
    """Build a map of phone_number -> count of mothers using it.
    Used to apply the Shared Phone Penalty."""
    phone_counts = {}
    for mother in mothers:
        for t in mother.get("telecom", []):
            phone = t.get("value", "")
            if phone:
                phone_counts[phone] = phone_counts.get(phone, 0) + 1
    return phone_counts


def score_match(infant, mother, phone_usage_map: dict = None):
    """Score how likely this mother is the parent of this infant.
    Returns (score 0-100, list of Evidence)."""
    evidence = []
    total = 0

    extracted_first, extracted_family = extract_mother_name_from_infant(infant)

    # 1. Name similarity
    mother_first = mother["name"][0]["given"][0]
    mother_family = mother["name"][0]["family"]

    if extracted_first:
        first_score = fuzz.ratio(extracted_first.lower(), mother_first.lower())
        if first_score > 70:
            evidence.append(Evidence("name_similarity",
                f"First name match: '{extracted_first}' ~ '{mother_first}' ({first_score}%)",
                first_score / 100))
            total += first_score * 0.3

    if extracted_family:
        family_score = fuzz.ratio(extracted_family.lower(), mother_family.lower())
        if family_score > 70:
            evidence.append(Evidence("name_similarity",
                f"Family name match: '{extracted_family}' ~ '{mother_family}' ({family_score}%)",
                family_score / 100))
            total += family_score * 0.25

    # 2. Facility match
    infant_facility = infant.get("meta", {}).get("facility", "")
    mother_facility = mother.get("meta", {}).get("facility", "")
    if infant_facility and mother_facility and infant_facility == mother_facility:
        evidence.append(Evidence("facility_match", f"Same facility: {infant_facility}", 1.0))
        total += 20

    # 3. Birth timing
    infant_dob = infant.get("birthDate", "")
    mother_delivery = mother.get("meta", {}).get("delivery_date", "")[:10]
    if infant_dob and mother_delivery:
        try:
            i_date = datetime.strptime(infant_dob, "%Y-%m-%d")
            m_date = datetime.strptime(mother_delivery, "%Y-%m-%d")
            days_diff = abs((i_date - m_date).days)
            if days_diff <= 1:
                evidence.append(Evidence("birth_timing",
                    f"Birth within {days_diff} day(s) of mother's delivery", 1.0))
                total += 20
            elif days_diff <= 3:
                evidence.append(Evidence("birth_timing",
                    f"Birth within {days_diff} days of delivery", 0.7))
                total += 10
        except ValueError:
            pass

    # 4. Phone match with Shared Phone Penalty
    infant_phones = [t["value"] for t in infant.get("telecom", []) if t.get("value")]
    mother_phones = [t["value"] for t in mother.get("telecom", []) if t.get("value")]
    if infant_phones and mother_phones:
        for ip in infant_phones:
            for mp in mother_phones:
                if ip == mp:
                    phone_count = 1
                    if phone_usage_map:
                        phone_count = phone_usage_map.get(mp, 1)
                    if phone_count > 1:
                        penalty_weight = max(5, 15 // phone_count)
                        evidence.append(Evidence("phone_match",
                            f"Phone match: {ip} (SHARED by {phone_count} mothers — weight reduced to {penalty_weight})",
                            penalty_weight / 15))
                        total += penalty_weight
                    else:
                        evidence.append(Evidence("phone_match", f"Phone match: {ip}", 1.0))
                        total += 15
                    break

    return min(total, 100), evidence


def find_mother(infant, mothers, threshold=50, top_n=3):
    """Find the best matching mother(s) for an infant.
    Returns a list of up to top_n LinkageResult candidates sorted by confidence.
    Returns empty list if no candidates meet the threshold."""
    phone_usage_map = _build_phone_usage_map(mothers)
    candidates = []

    for mother in mothers:
        score, evidence = score_match(infant, mother, phone_usage_map)
        if score >= threshold:
            art_id = ""
            for ident in mother.get("identifier", []):
                if "art" in ident.get("system", "").lower():
                    art_id = ident["value"]
            candidates.append(LinkageResult(
                mother_id=mother["id"],
                mother_name=f"{mother['name'][0]['given'][0]} {mother['name'][0]['family']}",
                art_id=art_id,
                confidence=score / 100,
                evidence=evidence
            ))

    if not candidates:
        return []
    candidates.sort(key=lambda x: x.confidence, reverse=True)
    return candidates[:top_n]


# =============================================================================
#  AGENT 2: ADHERENCE MINER
#  Extracts hidden adherence risk indicators from clinical notes
# =============================================================================

SYSTEM_PROMPT = """You are a clinical adherence analyst for HIV care in Sub-Saharan Africa.
Given a clinical note from a patient's prenatal record, extract ANY adherence risk indicators.
Look for:
- Missed pharmacy pick-ups
- Missed ANC (antenatal care) visits
- Transport or financial difficulties
- Self-reported missed ART doses
- Late presentation to care
- Any other barrier to treatment adherence
For EACH risk indicator found, call the report_adherence_risks function.
If NO risk indicators are found, call the function with an empty list.
IMPORTANT:
- Only extract what is explicitly stated in the note
- Do NOT infer or guess
- The source_quote MUST be an exact substring from the original note"""


def report_adherence_risks(
    risks: list[dict],
) -> dict:
    """Report adherence risk indicators found in clinical notes.

    Args:
        risks: A list of risk indicator objects. Each object must contain:
            - indicator (str): Short description of the risk.
            - severity (str): One of 'low', 'moderate', or 'high'.
            - source_quote (str): Exact quote from the clinical note.

    Returns:
        A dict echoing the reported risks for confirmation.
    """
    return {"reported": len(risks), "risks": risks}


def extract_adherence_risks(clinical_notes: list) -> list:
    """Extract adherence risk indicators from clinical notes using Gemma 4 native function calling via Ollama."""
    if not clinical_notes:
        return []

    notes_text = ""
    for note in clinical_notes:
        notes_text += f"[Date: {note.get('date', 'unknown')}]\n{note['content']}\n\n"

    try:
        response = _ollama_client.chat(
            model=GEMMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze these clinical notes:\n\n{notes_text}"},
            ],
            tools=[report_adherence_risks],
            options={"temperature": 0.1},
        )

        risks_data = []
        for tc in response.message.tool_calls or []:
            if tc.function.name == "report_adherence_risks":
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json.loads(args)
                risks_data = args.get("risks", [])
                break

        # --- Hallucination Firewall (fuzzy match ≥75% similarity) ---
        _FIREWALL_THRESHOLD = 75
        risks = []
        for r in risks_data:
            quote = r.get("source_quote", "") if isinstance(r, dict) else ""
            if not quote:
                print(f"🚫 FIREWALL REJECTED: empty source_quote")
                continue
            similarity = fuzz.partial_ratio(quote.lower(), notes_text.lower())
            if similarity < _FIREWALL_THRESHOLD:
                print(f"🚫 FIREWALL REJECTED: '{quote[:80]}' — similarity {similarity}% < {_FIREWALL_THRESHOLD}%")
                continue
            source_date = "unknown"
            for note in clinical_notes:
                if fuzz.partial_ratio(quote.lower(), note["content"].lower()) >= _FIREWALL_THRESHOLD:
                    source_date = note.get("date", "unknown")
                    break
            risks.append(AdherenceRisk(
                indicator=r["indicator"],
                source_text=quote,
                source_date=source_date,
                severity=r.get("severity", "moderate")
            ))
        return risks

    except Exception as e:
        print(f"[AdherenceMiner] Gemma 4/Ollama error: {e} — falling back to offline extraction")
        return extract_adherence_risks_offline(clinical_notes)


def extract_adherence_risks_offline(clinical_notes: list) -> list:
    """Fallback: rule-based extraction without LLM."""
    risks = []
    keywords = {
        "missed pharmacy": ("Missed pharmacy pick-up", "moderate"),
        "missed pick-up": ("Missed pharmacy pick-up", "moderate"),
        "transport": ("Transport difficulties reported", "moderate"),
        "financial": ("Financial barriers to care", "moderate"),
        "missing art": ("Missed ART doses", "high"),
        "skipping medication": ("Self-reported medication skipping", "high"),
        "missed doses": ("Missed ART doses", "high"),
        "missing doses": ("Missed ART doses", "high"),
        "late presentation": ("Late entry to antenatal care", "moderate"),
        "did not attend": ("Missed scheduled visit", "moderate"),
        "first visit at 3": ("Late entry to antenatal care", "moderate"),
    }
    for note in clinical_notes:
        content = note.get("content", "").lower()
        for keyword, (indicator, severity) in keywords.items():
            if keyword in content:
                risks.append(AdherenceRisk(
                    indicator=indicator,
                    source_text=note["content"],
                    source_date=note.get("date", "unknown"),
                    severity=severity
                ))
    return risks


# =============================================================================
#  AGENT 3: PROTOCOL GUARDIAN
#  Deterministic risk classification — NO AI, pure rules
# =============================================================================

def calculate_adherence_score(adherence_risks: list) -> float:
    """Severity-weighted adherence scoring.
    high=3, moderate=2, low=1. Threshold for HIGH risk: cumulative >= 4."""
    severity_weights = {"high": 3, "moderate": 2, "low": 1}
    return sum(severity_weights.get(r.severity, 2) for r in adherence_risks)


def classify_risk(mother: dict, adherence_risks: list) -> RiskClassification:
    """Deterministic risk classification.
    Risk Levels:
      HIGH:     VL > 1000, OR no VL on record, OR stale VL (>90 days),
                OR adherence score >= 4 despite suppressed VL
      MODERATE: VL 50-1000, OR 1 adherence indicator, OR adherence score 1-3
      LOW:      VL < 50 AND no adherence risk indicators
    """
    vl_data = mother.get("viral_load", {})
    vl_value = vl_data.get("valueQuantity", {}).get("value", None)
    vl_date = vl_data.get("effectiveDateTime", "")
    reasons = []

    # Rule 0: No VL data at all
    if vl_value is None or (vl_value == 0 and not vl_date):
        reasons.append("No viral load on record — treat as untreated/unknown status")
        return RiskClassification(
            level="HIGH", reasons=reasons, viral_load=0,
            viral_load_date="", adherence_risks=adherence_risks
        )

    # Rule 1: Unsuppressed viral load
    if vl_value > 1000:
        reasons.append(f"Unsuppressed viral load: {vl_value} copies/mL")

    # Rule 2: Stale viral load data (>90 days old)
    if vl_date:
        try:
            vl_dt = datetime.fromisoformat(vl_date)
            days_old = (datetime.now() - vl_dt).days
            if days_old > 90:
                reasons.append(f"Last VL test is {days_old} days old (>3 months — stale data)")
        except ValueError:
            reasons.append("Unable to parse VL date — treating as stale")
    else:
        reasons.append("No VL test date available — treating as stale")

    # Rule 3: Severity-weighted adherence scoring
    adherence_score = calculate_adherence_score(adherence_risks)
    risk_indicator_count = len(adherence_risks)

    if vl_value <= 1000 and adherence_score >= 4:
        reasons.append(
            f"Adherence Miner found {risk_indicator_count} risk indicators "
            f"(severity score: {adherence_score}) despite suppressed VL"
        )

    # Determine level
    if reasons:
        level = "HIGH"
    elif 50 <= vl_value <= 1000:
        level = "MODERATE"
        reasons.append(f"Borderline viral load: {vl_value} copies/mL (50–1000 range)")
    elif risk_indicator_count >= 1:
        level = "MODERATE"
        reasons.append(
            f"Adherence Miner found {risk_indicator_count} risk indicator(s) "
            f"(severity score: {adherence_score})"
        )
    else:
        level = "LOW"

    return RiskClassification(
        level=level, reasons=reasons, viral_load=vl_value,
        viral_load_date=vl_date, adherence_risks=adherence_risks
    )


def get_prophylaxis_recommendation(risk_level: str) -> dict:
    """Return specific drug regimen based on risk level per CDC/NIH/WHO guidelines."""
    if risk_level == "HIGH":
        return {
            "regimen": "Triple Therapy: AZT + 3TC + NVP (or Raltegravir)",
            "duration": "6 weeks",
            "urgency": "Start within 6 hours of birth",
            "follow_up": "Continue AZT to complete 6 weeks total after combination therapy"
        }
    elif risk_level == "MODERATE":
        return {
            "regimen": "Assess: Consider Triple Therapy (AZT + 3TC + NVP) or AZT alone",
            "duration": "2–6 weeks depending on clinical assessment",
            "urgency": "Start within 6 hours of birth — clinician to determine regimen",
            "follow_up": "Obtain current VL if stale; reassess risk after results"
        }
    else:
        return {
            "regimen": "AZT (Zidovudine) only",
            "duration": "2 weeks",
            "urgency": "Start within 6 hours of birth",
            "follow_up": "Standard follow-up per protocol"
        }


def build_bridge_summary(infant, linkage, risk, audit_hash: str = "") -> BridgeSummary:
    """Build the human-readable Bridge Summary for the FHIR Task.

    Args:
        infant: The infant FHIR-like resource dict.
        linkage: LinkageResult from the Forensic Linker.
        risk: RiskClassification from the Protocol Guardian.
        audit_hash: Current SHA-256 audit chain hash for NDPA compliance display.
    """
    infant_name = f"{infant['name'][0].get('given', [''])[0]} {infant['name'][0].get('family', '')}".strip()
    evidence_summary = "; ".join(e.detail for e in linkage.evidence)

    adherence_findings = [
        f"{r.indicator} [{r.severity.upper()}] (Source: \"{r.source_text[:80]}\" — {r.source_date})"
        for r in risk.adherence_risks
    ]

    prophylaxis = get_prophylaxis_recommendation(risk.level)

    if risk.level == "HIGH":
        action = (
            f"URGENT: {prophylaxis['regimen']} for {prophylaxis['duration']}. "
            f"{prophylaxis['urgency']}."
        )
    elif risk.level == "MODERATE":
        action = (
            f"REVIEW: {prophylaxis['regimen']}. "
            f"{prophylaxis['urgency']}."
        )
    else:
        action = (
            f"Standard: {prophylaxis['regimen']} for {prophylaxis['duration']}. "
            f"{prophylaxis['urgency']}."
        )

    return BridgeSummary(
        infant_name=infant_name,
        mother_name=linkage.mother_name,
        art_id=linkage.art_id,
        confidence=linkage.confidence,
        evidence_summary=evidence_summary,
        viral_load=risk.viral_load,
        risk_level=risk.level,
        adherence_findings=adherence_findings,
        recommended_action=action,
        audit_hash=audit_hash
    )
