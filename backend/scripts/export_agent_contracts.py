from __future__ import annotations

import json
from pathlib import Path


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "agent_runtime" / "v1"


def _run(domain: str) -> dict:
    return {
        "run_id": f"run_{domain}",
        "job_id": f"job_{domain}",
        "domain": domain,
        "status": "RUNNING",
        "phase": "CONTEXT_BUILDING",
        "current_role": None,
        "progress": {"current": 0, "total": 4, "percent": 0},
        "context_snapshot_id": None,
        "created_at": "2026-09-12T10:00:00Z",
        "updated_at": "2026-09-12T10:00:00Z",
        "finished_at": None,
    }


def fixtures() -> dict[str, dict]:
    return {
        "runtime.json": _run("runtime"),
        "final_review.json": {
            "campaign_id": "campaign_demo",
            "exam_id": "exam_server_owned",
            "active_version": 1,
            "status": "ACTIVE",
            "run": _run("final_review"),
        },
        "course_research.json": {
            "research_id": "research_demo",
            "course_id": "course_demo",
            "mode": "EXPLAIN",
            "academic_policy": "STANDARD",
            "source_policy": {
                "course_material_priority": True,
                "allow_web": False,
                "allow_user_upload": False,
            },
            "run": _run("course_research"),
        },
        "notice_workflow.json": {
            "workflow_id": "workflow_demo",
            "notice_id": "notice_server_owned",
            "status": "CREATED",
            "automation_enabled": False,
            "run": _run("notice_workflow"),
        },
    }


def main() -> None:
    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    for name, payload in fixtures().items():
        (FIXTURE_ROOT / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
