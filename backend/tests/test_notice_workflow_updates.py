from notice_workflow_helpers import create_workflow, setup_student


def test_notice_revision_shows_difference_and_preserves_completed_action():
    container, client, user, headers = setup_student()
    notice, workflow = create_workflow(client, headers)
    client.post(f"/api/v1/notice-workflows/{workflow['workflow_id']}/confirm", headers=headers, json={"approved": True})
    completed = client.post(f"/api/v1/notice-workflows/{workflow['workflow_id']}/execute", headers=headers, json={"idempotency_key": "original"}).json()
    assert completed["actions"][0]["status"] == "COMPLETED"
    container.notice_repository.create_or_update_notice(user.id, "manual_input", "manual:revision-test", "课程报告", "截止日期调整为2026-10-22，请提交课程报告")
    with container.db.transaction() as conn:
        conn.execute("UPDATE notices SET content=? WHERE id=? AND user_id=?", ("截止日期调整为2026-10-22，请提交课程报告", notice["notice_id"], user.id))
    updated = client.post(f"/api/v1/notices/{notice['notice_id']}/workflow", headers=headers).json()
    assert updated["workflow_id"] == workflow["workflow_id"]
    assert updated["source_revision"] == 2
    assert updated["difference"] == {"changed": True, "previous_revision": 1}
    assert updated["actions"][0]["status"] == "COMPLETED"


def test_cross_user_workflow_is_hidden_as_not_found():
    container, client, _user, headers = setup_student()
    _notice, workflow = create_workflow(client, headers)
    other = container.user_repository.create_user(username="cross_user", password_hash=__import__("app.core.security", fromlist=["hash_password"]).hash_password("Demo123456"), role="student", display_name="Cross")
    login = client.post("/api/v1/auth/login", json={"username": other.username, "password": "Demo123456"}).json()
    response = client.get(f"/api/v1/notice-workflows/{workflow['workflow_id']}", headers={"Authorization": f"Bearer {login['access_token']}"})
    assert response.status_code == 404
