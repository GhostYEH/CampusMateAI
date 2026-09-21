from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ...models.multi_role import UserRow
from ...schemas.magicclass_quiz import QuizAttemptIn, QuizAttemptStateOut
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.course_context import assert_course_access
from ...services.magicclass.quiz_attempt_store import PHASE_ORDER, QuizAttempt, root_attempt_id
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["magicclass-quiz"])


def _container() -> ServiceContainer:
    return get_container()


def _state(attempt: QuizAttempt | None) -> dict | None:
    if attempt is None:
        return None
    return {"session_id": attempt.attempt_id, "phase": attempt.phase, "answers": attempt.answers, "results": attempt.results}


@router.get("/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/quiz-attempt", response_model=QuizAttemptStateOut)
async def get_quiz_attempt(course_id: str, workspace_id: str, stage_id: str, scene_id: str, user: UserRow = Depends(current_user), container: ServiceContainer = Depends(_container)) -> QuizAttemptStateOut:
    assert_course_access(container, user, course_id)
    root = root_attempt_id(str(user.id), stage_id, scene_id)
    store = container.quiz_attempt_store
    current = store.get(root, user_id=str(user.id))
    index = 1
    while store.get(f"{root}:retry:{index}", user_id=str(user.id)) is not None:
        current = store.get(f"{root}:retry:{index}", user_id=str(user.id))
        index += 1
    return QuizAttemptStateOut(attempt_id=current.attempt_id if current else root, state=_state(current))


@router.post("/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/quiz-attempt", response_model=QuizAttemptStateOut)
async def save_quiz_attempt(course_id: str, workspace_id: str, stage_id: str, scene_id: str, body: QuizAttemptIn, user: UserRow = Depends(current_user), container: ServiceContainer = Depends(_container)) -> QuizAttemptStateOut:
    assert_course_access(container, user, course_id)
    store = container.quiz_attempt_store
    attempt_id = body.attempt_id
    prior = store.get(attempt_id, user_id=str(user.id))
    if prior is None and not body.start_new_attempt:
        # A fast click can race the initial GET; normalize the client placeholder
        # to the server-owned deterministic root before writing.
        attempt_id = root_attempt_id(str(user.id), stage_id, scene_id)
        prior = store.get(attempt_id, user_id=str(user.id))
    if body.start_new_attempt:
        attempt_id = store.next_retry_id(root_attempt_id(str(user.id), stage_id, scene_id), user_id=str(user.id))
        prior = None
    if prior and PHASE_ORDER[body.phase] < PHASE_ORDER[prior.phase]:
        return JSONResponse(status_code=409, content={"detail": "测验状态不能回退"})
    attempt = QuizAttempt(
        attempt_id=attempt_id, user_id=str(user.id), course_id=course_id,
        workspace_id=workspace_id, stage_id=stage_id, scene_id=scene_id,
        phase=body.phase, answers=body.answers, results=body.results,
    )
    store.save(attempt)
    return QuizAttemptStateOut(attempt_id=attempt_id, state=_state(attempt))
