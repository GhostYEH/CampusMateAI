from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssignmentPolicy:
    version: str
    salt: str
    groups: tuple[str, ...] = ("CONTROL", "STATE_DRIVEN", "CLOSED_LOOP")


@dataclass(frozen=True)
class Assignment:
    participant_id: str
    group: str
    assignment_version: str
    active: bool = True


class ExperimentRegistry:
    def __init__(self, *, enabled: bool = False, policy: AssignmentPolicy | None = None) -> None:
        self.enabled = enabled
        self.policy = policy or AssignmentPolicy(version="assignment-v1", salt="disabled")
        self._assignments: dict[str, Assignment] = {}
        self._exposures: dict[str, list[dict[str, str]]] = {}

    def assign(self, participant_id: str) -> Assignment:
        if not self.enabled:
            raise RuntimeError("real-study assignment is disabled")
        if participant_id in self._assignments:
            return self._assignments[participant_id]
        digest = hashlib.sha256(f"{self.policy.salt}:{participant_id}".encode()).digest()
        group = self.policy.groups[int.from_bytes(digest[:8], "big") % len(self.policy.groups)]
        result = Assignment(participant_id, group, self.policy.version)
        self._assignments[participant_id] = result
        return result

    def get(self, participant_id: str) -> Assignment | None:
        return self._assignments.get(participant_id)

    def record_exposure(self, participant_id: str, mode: str, exposure_id: str) -> None:
        assignment = self._assignments.get(participant_id)
        if assignment is None or not assignment.active:
            return
        self._exposures.setdefault(participant_id, []).append({"mode": mode, "exposure_id": exposure_id, "assignment_version": assignment.assignment_version})

    def exposures(self, participant_id: str) -> list[dict[str, str]]:
        return list(self._exposures.get(participant_id, []))

    def exit(self, participant_id: str) -> None:
        current = self._assignments.get(participant_id)
        if current:
            self._assignments[participant_id] = Assignment(current.participant_id, current.group, current.assignment_version, active=False)
            self._exposures.pop(participant_id, None)

    def delete(self, participant_id: str) -> None:
        self._assignments.pop(participant_id, None)
        self._exposures.pop(participant_id, None)


def power_analysis(*, variance: float, effect_size: float, alpha: float = 0.05, power: float = 0.8, groups: int = 2) -> dict[str, Any]:
    if variance <= 0 or effect_size <= 0 or not 0 < alpha < 1 or not 0 < power < 1 or groups < 2:
        raise ValueError("variance/effect_size/alpha/power/groups must be valid")
    # Conservative planning approximation; final sample size requires a study statistician.
    z_alpha = 1.96 if alpha <= 0.05 else 1.645
    z_power = 0.84 if power <= 0.8 else 1.28
    per_group = math.ceil(2 * variance * (z_alpha + z_power) ** 2 / (effect_size ** 2))
    return {"per_group": per_group, "total": per_group * groups, "alpha": alpha, "power": power, "groups": groups, "note": "planning approximation; not an educational-effect conclusion"}
