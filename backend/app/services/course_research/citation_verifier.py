from ...models.course_research import VerifiedResearchSource


_SOURCE_PRIORITY = {"COURSE_METADATA": 0, "COURSE_MATERIAL": 1, "USER_UPLOAD": 2, "WEB": 3}


def order_verified_sources(sources: list[VerifiedResearchSource]) -> list[VerifiedResearchSource]:
    """Keep only verified citations and prefer authorized course sources."""
    verified = [source for source in sources if source.verification_status == "VERIFIED"]
    return sorted(verified, key=lambda source: (_SOURCE_PRIORITY.get(source.source_type, 99), source.safe_label))
