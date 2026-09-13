from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests


def _setup():
    c=reset_container_for_tests(Settings(app_env="test",database_url="sqlite:///:memory:",llm_provider="none"))
    users=[]
    for name in ("review_student","review_other"):
        users.append(c.user_repository.create_user(username=name,password_hash=hash_password("Demo123456"),role="student",display_name=name))
    client=TestClient(create_app()); headers=[]
    for user in users:
        login=client.post("/api/v1/auth/login",json={"username":user.username,"password":"Demo123456"})
        headers.append({"Authorization":f"Bearer {login.json()['access_token']}"})
    exam=client.post("/api/v1/student/exams",headers=headers[0],json={"course_name":"程序设计课程","exam_date":"2026-12-20"})
    assert exam.status_code==201
    return client,headers,exam.json()["id"]


def test_final_review_closed_loop_preserves_immutable_versions():
    client,headers,exam_id=_setup()
    created=client.post("/api/v1/final-review/campaigns",headers=headers[0],json={"exam_id":exam_id,"daily_capacity_minutes":90})
    assert created.status_code==200; cid=created.json()["campaign_id"]
    assert client.get(f"/api/v1/final-review/campaigns/{cid}",headers=headers[1]).status_code==404
    v1=client.post(f"/api/v1/final-review/campaigns/{cid}/plans/generate",headers=headers[0]).json()
    assert v1["version"]==1
    activated=client.post(f"/api/v1/final-review/campaigns/{cid}/activate",headers=headers[0])
    assert activated.json()["active_version"]==1
    agenda=client.get(f"/api/v1/final-review/campaigns/{cid}/agendas/today",headers=headers[0]).json()
    assert len(agenda["items"])==2
    assert all(item["external_task_id"] for item in agenda["items"])
    completed=client.post(f"/api/v1/final-review/daily-items/{agenda['items'][0]['item_id']}/complete",headers=headers[0])
    assert completed.status_code==200 and completed.json()["status"]=="COMPLETED"
    client.post(f"/api/v1/final-review/campaigns/{cid}/activate",headers=headers[0])
    tasks=client.get("/api/v1/tasks",headers=headers[0]).json()
    task_items=tasks.get("items",tasks)
    assert {task["title"] for task in task_items} >= {"复习核心知识点", "完成诊断练习"}
    checkin=client.post(f"/api/v1/final-review/campaigns/{cid}/daily-checkins",headers=headers[0],json={"completion_percent":40,"actual_minutes":35,"difficulty_code":"TIME_LIMITED"})
    assert checkin.status_code==200
    proposal=client.post(f"/api/v1/final-review/campaigns/{cid}/adjustments/analyze",headers=headers[0]).json()
    decision=client.post(f"/api/v1/final-review/adjustment-proposals/{proposal['id']}/decision",headers=headers[0],json={"decision":"APPROVED"})
    assert decision.status_code==200 and decision.json()["new_version"]["version"]==2
    versions=client.get(f"/api/v1/final-review/campaigns/{cid}/plan-versions",headers=headers[0]).json()
    assert [item["version"] for item in versions]==[1,2]
    assert versions[0]["content_hash"]==v1["content_hash"]


def test_campaign_rejects_foreign_or_local_guessed_exam_id():
    client,headers,_exam_id=_setup()
    response=client.post("/api/v1/final-review/campaigns",headers=headers[0],json={"exam_id":"123","daily_capacity_minutes":60})
    assert response.status_code==404
    assert response.json()["code"]=="AGENT_PERMISSION_DENIED"
