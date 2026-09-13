from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchPolicyDecision:
    requested_mode: str
    effective_mode: str
    warning_codes: tuple[str, ...]


@dataclass(frozen=True)
class VerifiedResearchSource:
    source_type: str
    safe_label: str
    content_digest: str
    verification_status: str = "VERIFIED"
