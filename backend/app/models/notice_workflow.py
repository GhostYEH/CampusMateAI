from dataclasses import dataclass


@dataclass(frozen=True)
class InterpretedNotice:
    facts: dict
    uncertainty_codes: tuple[str, ...]
    checklist: tuple[str, ...]
    action_risk: str
