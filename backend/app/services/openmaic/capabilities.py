"""Capability vocabulary shared with the managed OpenMAIC service.

The service reports the capability tags it currently implements. CampusMate must
never forward an unknown tag to the browser, because a compromised or out-of-date
service could otherwise switch on an entry point that does not exist. The list
here mirrors ``openmaic-service/src/capabilities.ts``; a contract test keeps the
two in step.
"""

from __future__ import annotations

from typing import Iterable

KNOWN_CAPABILITIES: tuple[str, ...] = (
    "workspace",
    "stage-dsl",
    "editor",
    "player",
    "folder",
    "search",
    "material",
    "import-pptx",
    "import-maic",
    "export-maic",
    "export-pptx",
    "export-markdown",
    "export-docx",
    "export-video",
    "generation",
    "whiteboard",
    "tts",
    "multi-agent",
    "provider-status",
)

_KNOWN = frozenset(KNOWN_CAPABILITIES)


def is_known_capability(value: object) -> bool:
    return isinstance(value, str) and value in _KNOWN


def filter_capabilities(values: Iterable[object]) -> list[str]:
    """Keep only known tags, de-duplicated and in the canonical order."""
    accepted = {value for value in values if is_known_capability(value)}
    return [capability for capability in KNOWN_CAPABILITIES if capability in accepted]


__all__ = ["KNOWN_CAPABILITIES", "filter_capabilities", "is_known_capability"]
