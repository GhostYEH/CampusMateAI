from typing import Any


def score_band(score: Any) -> str | None:
    """Use the same observed-score bands for events and state projections."""
    # 0 分是有效成绩(0_59 段)，只有缺失或空值才不产出分段。
    if score is None or str(score).strip() == "":
        return None
    try:
        numeric = float(score)
    except (TypeError, ValueError):
        return "non_numeric"
    if numeric >= 90:
        return "90_100"
    if numeric >= 80:
        return "80_89"
    if numeric >= 70:
        return "70_79"
    if numeric >= 60:
        return "60_69"
    return "0_59"
