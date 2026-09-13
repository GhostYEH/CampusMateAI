from __future__ import annotations


class MemoryManager:
    ALLOWED_TYPES = frozenset({
        "CONFIRMED_PREFERENCE", "CONFIRMED_STUDY_GOAL",
        "CONFIRMED_CONSTRAINT", "USER_APPROVED_SUMMARY",
    })

    @classmethod
    def is_model_consumable(cls, memory_type: str, *, confirmed: bool, withdrawn: bool, sensitivity: str) -> bool:
        return memory_type in cls.ALLOWED_TYPES and confirmed and not withdrawn and sensitivity == "LOW"
