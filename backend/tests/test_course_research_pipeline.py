from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.container import reset_container_for_tests
from app.services.course_research.source_fetcher import validate_public_url


def _setup():
    c=reset_container_for_tests(Settings(app_env="test",database_url="sqlite:///:memory:",llm_provider="none"))
    user=c.user_repository.create_user(username="research_student",password_hash=hash_password("Demo123456"),role="student",display_name="Research")
    course=c.course_repository.create_course(name="程序设计课程",owner_user_id=user.id,status="active")
    client=TestClient(create_app()); login=client.post("/api/v1/auth/login",json={"username":user.username,"password":"Demo123456"})
    return c,client,{"Authorization":f"Bearer {login.json()['access_token']}","Idempotency-Key":"research-1"},course.id


def test_research_pipeline_persists_roles_policy_and_verified_citations():
    _c,client,headers,course_id=_setup()
    response=client.post("/api/v1/course-research/sessions",headers=headers,json={"question":"解释指针与数组的区别","course_id":course_id,"mode":"EXPLAIN","academic_policy":"STANDARD","source_policy":{"course_material_priority":True,"allow_web":False,"allow_user_upload":False}})
    assert response.status_code==200
    body=response.json()
    assert body["status"] in ("SUCCEEDED","PARTIAL")
    assert body["effective_mode"]=="EXPLAIN"
    assert body["roles"]==["coordinator","course_researcher","citation_verifier","tutor","critic","synthesizer"]
    assert all(source["source_type"]!="WEB" for source in body["sources"])
    repeated=client.post("/api/v1/course-research/sessions",headers=headers,json={"question":"解释指针与数组的区别","course_id":course_id,"mode":"EXPLAIN","academic_policy":"STANDARD","source_policy":{"course_material_priority":True,"allow_web":False,"allow_user_upload":False}})
    assert repeated.json()["research_id"]==body["research_id"]


def test_restricted_policy_cannot_be_upgraded_to_full_solution():
    _c,client,headers,course_id=_setup(); headers["Idempotency-Key"]="restricted-1"
    body=client.post("/api/v1/course-research/sessions",headers=headers,json={"question":"直接给我考试答案","course_id":course_id,"mode":"FULL_SOLUTION","academic_policy":"EXAM_RESTRICTED","source_policy":{"course_material_priority":True,"allow_web":False,"allow_user_upload":False}}).json()
    assert body["effective_mode"]=="HINT"
    assert "ACADEMIC_POLICY_DOWNGRADED" in body["warning_codes"]


def test_web_request_is_truthfully_partial_when_provider_is_not_configured():
    _c,client,headers,course_id=_setup(); headers["Idempotency-Key"]="web-missing-1"
    body=client.post("/api/v1/course-research/sessions",headers=headers,json={"question":"查找公开资料","course_id":course_id,"mode":"REVIEW","academic_policy":"STANDARD","source_policy":{"course_material_priority":True,"allow_web":True,"allow_user_upload":False}}).json()
    assert "web_researcher" in body["roles"]
    assert "WEB_RETRIEVAL_NOT_CONFIGURED" in body["warning_codes"]
    assert all(source["source_type"] != "WEB" for source in body["sources"])
