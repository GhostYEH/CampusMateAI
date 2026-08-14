from test_community_posts import _headers, _setup


def test_lost_found_feed_is_university_scoped_and_private_contact_is_masked() -> None:
    client, _ = _setup()
    a = _headers(client, "student_a")
    peer = _headers(client, "student_a_peer")
    b = _headers(client, "student_b")
    created = client.post(
        "/api/v1/student/lost-found",
        headers=a,
        json={
            "kind": "lost",
            "title": "Campus card",
            "content": "Lost near library",
            "location": "Library",
            "contact": "private-phone",
            "contact_visibility": "private",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["contact"] == "private-phone"
    assert client.get("/api/v1/student/lost-found", headers=b).json() == []
    peer_item = client.get("/api/v1/student/lost-found", headers=peer).json()[0]
    assert peer_item["title"] == "Campus card"
    assert peer_item["contact"] is None
    assert peer_item["contact_visibility"] == "private"


def test_lost_found_requires_selected_university() -> None:
    client, _ = _setup()
    response = client.get("/api/v1/student/lost-found", headers=_headers(client, "student_demo_01"))
    assert response.status_code == 409
    assert response.json()["code"] == "UNIVERSITY_REQUIRED"
