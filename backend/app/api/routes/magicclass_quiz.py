from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends

from ...models.multi_role import UserRow
from ...schemas.magicclass_quiz import QuizAttemptIn, QuizAttemptStateOut
from ...services.container import ServiceContainer, get_container
from ...services.magicclass.course_context import assert_course_access
from ...services.magicclass.quiz_attempt_store import QuizAttempt, root_attempt_id
from ..deps import current_user

router = APIRouter(prefix="/courses", tags=["课堂测验"])


def _container() -> ServiceContainer:
    return get_container()


def _state(attempt: QuizAttempt | None) -> dict | None:
    if attempt is None:
        return None
    return {"session_id": attempt.attempt_id, "phase": attempt.phase, "answers": attempt.answers, "results": attempt.results}


@router.get(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/quiz-attempt",
    response_model=QuizAttemptStateOut,
    summary="读取测验作答",
    responses={
        200: {
            "description": "当前测验作答状态；尚未作答时 state 为 null",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "读取测验作答",
                            "value": {
                                "attempt_id": "usr_1:stage_1:scene_1",
                                "state": {
                                    "session_id": "usr_1:stage_1:scene_1",
                                    "phase": "draft",
                                    "answers": {"q1": "a"},
                                    "results": [],
                                },
                            },
                        }
                    }
                }
            },
        }
    },
)
def get_quiz_attempt(course_id: str, workspace_id: str, stage_id: str, scene_id: str, user: UserRow = Depends(current_user), container: ServiceContainer = Depends(_container)) -> QuizAttemptStateOut:
    """读取该场景的测验作答状态。

    - 尚未作答时 state 为 null，attempt_id 回退为根作答 ID。
    - 需要已登录且对该课程有访问权限。
    """
    assert_course_access(container, user, course_id)
    root = root_attempt_id(str(user.id), stage_id, scene_id)
    store = container.quiz_attempt_store
    current = store.latest(root, user_id=str(user.id))
    return QuizAttemptStateOut(attempt_id=current.attempt_id if current else root, state=_state(current))


@router.post(
    "/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/quiz-attempt",
    response_model=QuizAttemptStateOut,
    summary="保存测验作答",
    responses={
        409: {"description": "测验状态回退或课堂归属冲突（QUIZ_ATTEMPT_CONFLICT）"},
        200: {
            "description": "保存成功，返回更新后的测验作答状态",
            "content": {
                "application/json": {
                    "examples": {
                        "成功": {
                            "summary": "保存测验作答",
                            "value": {
                                "attempt_id": "usr_1:stage_1:scene_1",
                                "state": {
                                    "session_id": "usr_1:stage_1:scene_1",
                                    "phase": "submitted",
                                    "answers": {"q1": "a"},
                                    "results": [],
                                },
                            },
                        }
                    }
                }
            },
        },
    },
)
def save_quiz_attempt(course_id: str, workspace_id: str, stage_id: str, scene_id: str, body: Annotated[
        QuizAttemptIn,
        Body(
            openapi_examples={
                "成功": {
                    "summary": "保存一次测验作答",
                    "value": {
                        "attempt_id": "usr_1:stage_1:scene_1",
                        "phase": "submitted",
                        "answers": {"q1": "a"},
                        "results": [],
                        "start_new_attempt": False,
                    },
                }
            }
        ),
    ], user: UserRow = Depends(current_user), container: ServiceContainer = Depends(_container)) -> QuizAttemptStateOut:
    """保存该场景的测验作答。

    状态回退或试图把已有作答移到另一课堂时返回 409（QUIZ_ATTEMPT_CONFLICT）；
    start_new_attempt=true 时滚动分配新的作答 ID。需要已登录且对该课程有访问权限。
    """
    assert_course_access(container, user, course_id)
    store = container.quiz_attempt_store
    attempt = store.update(
        attempt_id=body.attempt_id, user_id=str(user.id), course_id=course_id,
        workspace_id=workspace_id, stage_id=stage_id, scene_id=scene_id,
        phase=body.phase, answers=body.answers, results=body.results,
        start_new_attempt=body.start_new_attempt,
    )
    return QuizAttemptStateOut(attempt_id=attempt.attempt_id, state=_state(attempt))
