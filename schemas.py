"""
VIGILANT Data Schemas — Shared data structures used across all agents.

These dataclasses define the contracts between the Forensic Linker,
Adherence Miner, and Protocol Guardian agents.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Evidence:
    """A single piece of linkage evidence."""
    type: str       # e.g. "name_similarity", "facility_match", "phone_match"
    detail: str     # Human-readable description
    strength: float # 0.0 to 1.0


@dataclass
class LinkageResult:
    """Result of matching an infant to a mother."""
    mother_id: str
    mother_name: str
    art_id: str
    confidence: float           # 0.0 to 1.0
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class AdherenceRisk:
    """A single adherence risk indicator extracted from clinical notes."""
    indicator: str    # e.g. "Missed pharmacy pick-up"
    source_text: str  # The original text that triggered this
    source_date: str  # Date of the clinical note
    severity: str     # "low", "moderate", "high"


@dataclass
class RiskClassification:
    """Final risk classification for an infant."""
    level: str                  # "HIGH", "MODERATE", "LOW"
    reasons: List[str]
    viral_load: float
    viral_load_date: str
    adherence_risks: List[AdherenceRisk] = field(default_factory=list)


@dataclass
class BridgeSummary:
    """The human-readable summary that goes into the FHIR Task."""
    infant_name: str
    mother_name: str
    art_id: str
    confidence: float
    evidence_summary: str
    viral_load: float
    risk_level: str
    adherence_findings: List[str]
    recommended_action: str
    audit_hash: str = ""
