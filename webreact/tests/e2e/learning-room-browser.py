"""Two isolated browsers use real UID/room APIs and the real embedded classroom.

Start the Web and magicclass-app dev servers, then run with the backend Python
environment. WEB_BASE_URL and LEARNING_SPACE_APP_URL can override their origins.
All accounts, invitations and messages use an isolated in-memory test database.
No generation provider is called; the lesson is imported from a test archive.
"""
from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse
import zipfile

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from app.core.logging import logger
from app.services.container import reset_container_for_tests

WEB = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5304")
CLASSROOM = os.environ.get("LEARNING_SPACE_APP_URL", "http://127.0.0.1:5301")
TITLE = "UID 共同课堂测试"
CHANNEL = "campusmate-learning-room-v1"


def archive_bytes():
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jv1sAAAAASUVORK5CYII=")
    scenes = []
    for index in range(2):
        scenes.append({"type": "slide", "title": f"共同课件第{index + 1}页", "order": index, "actions": [], "content": {"type": "slide", "canvas": {"id": f"slide-{index}", "background": {"type": "solid", "color": "#ffffff"}, "elements": [{"id": f"text-{index}", "type": "text", "left": 80, "top": 60, "width": 750, "height": 100, "content": f"<p>共同课件第{index + 1}页</p>", "defaultFontName": "Arial", "defaultColor": "#222222"}, {"id": f"image-{index}", "type": "image", "src": "shared-image", "left": 80, "top": 180, "width": 80, "height": 80, "fixedRatio": True}]}}})
        scenes[-1]["content"]["canvas"].update({"viewportSize": 1000, "viewportRatio": 0.5625, "theme": {"fontName": "Arial", "fontColor": "#222222", "backgroundColor": "#ffffff", "themeColors": ["#222222"]}})
    manifest = {"formatVersion": 1, "exportedAt": "2026-01-01T00:00:00Z", "appVersion": "1.0.3", "stage": {"name": TITLE}, "agents": [], "scenes": scenes, "mediaIndex": {"media/image.png": {"type": "generated", "sourceRef": "shared-image", "mimeType": "image/png", "size": len(png)}}}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("media/image.png", png)
    return output.getvalue()


def main():
    logger.remove()
    reset_container_for_tests(Settings(app_env="test", database_url="sqlite:///:memory:", auto_seed_demo_users=False, llm_provider="none", agent_allow_mock_providers=True))
    client = TestClient(create_app())
    users = []
    for username in ("uid_browser_host", "uid_browser_guest"):
        assert client.post("/api/v1/auth/register", json={"username": username, "password": "BrowserTest123", "role": "student"}).status_code == 201
        users.append(client.post("/api/v1/auth/login", json={"username": username, "password": "BrowserTest123"}).json())

    def api(route):
        request = route.request
        parsed = urlparse(request.url)
        if parsed.path.endswith("/magicclass/learning-space/status"):
            route.fulfill(json={"enabled": True, "configured": True, "available": True, "embed_origin": CLASSROOM, "browser_embed_available": True})
            return
        headers = {key: value for key, value in request.headers.items() if key in ("authorization", "content-type")}
        response = client.request(request.method, parsed.path + (f"?{parsed.query}" if parsed.query else ""), headers=headers, content=request.post_data_buffer)
        route.fulfill(status=response.status_code, headers={"content-type": response.headers.get("content-type", "application/json")}, body=response.content)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        contexts = [browser.new_context(viewport={"width": 1440, "height": 1000}) for _ in users]
        pages = []
        try:
            for context, account in zip(contexts, users):
                context.route("**/api/v1/**", api)
                # Imported fixtures have no provider work; block any accidental generation.
                context.route("**/api/generate*", lambda route: route.fulfill(status=503, json={"error": "Generation is disabled in this test"}))
                context.add_init_script("""(account => {
                  if (location.origin === account.web) {
                    localStorage.setItem('campus_access_token', account.access_token);
                    localStorage.setItem('campus_refresh_token', account.refresh_token);
                    localStorage.setItem('campus_session', JSON.stringify(account.user));
                  }
                })(%s)""" % json.dumps({**account, "web": WEB}))
                page = context.new_page()
                page.on("pageerror", lambda error: print("Browser error:", str(error).splitlines()[0]))
                page.goto(f"{WEB}/learning-space")
                expect(page.get_by_text(account["user"]["uid"], exact=True)).to_be_visible(timeout=30000)
                pages.append(page)
            host, guest = pages
            host_frame = host.frame_locator('iframe[title="学习空间"]')
            expect(host.get_by_role("complementary", name="同学一起学")).to_have_attribute("aria-busy", "false", timeout=60000)
            host_frame.locator('input[type="file"][accept=".zip"]').set_input_files({"name": "uid-test.maic.zip", "mimeType": "application/zip", "buffer": archive_bytes()}, timeout=180000)
            try:
                host_frame.get_by_text(TITLE, exact=True).first.click(timeout=30000)
            except Exception:
                print("Classroom import UI:", host_frame.locator("body").inner_text()[-1500:])
                raise
            expect(host.get_by_role("dialog")).to_be_visible()
            host.get_by_label("同学 UID", exact=True).fill(users[1]["user"]["uid"])
            host.get_by_role("button", name="邀请并进入", exact=True).click()
            expect(host.get_by_text("邀请已发送，等待同学接受。", exact=False)).to_be_visible(timeout=180000)
            guest.get_by_role("button", name="接受并加入").click(timeout=30000)
            expect(guest.get_by_text("已加入同一课堂", exact=False)).to_be_visible(timeout=180000)
            guest_frame = guest.frame_locator('iframe[title="学习空间"]')
            expect(guest_frame.locator('[data-testid="scene-item"]')).to_have_count(2, timeout=60000)
            host.get_by_label("课堂消息").fill("这门课我们一起学")
            host.get_by_role("button", name="发送", exact=True).click()
            expect(guest.get_by_text("这门课我们一起学", exact=True)).to_be_visible(timeout=10000)
            guest.get_by_label("课堂消息").fill("好，一起看第二页")
            guest.get_by_role("button", name="发送", exact=True).click()
            expect(host.get_by_text("好，一起看第二页", exact=True)).to_be_visible(timeout=10000)
            host_frame.get_by_role("button", name="Toggle sidebar", exact=True).click()
            host_frame.locator('[data-testid="scene-item"]').nth(1).click()
            host_uid = users[0]["user"]["uid"]
            headers = {"Authorization": f"Bearer {users[0]['access_token']}"}
            room = client.get("/api/v1/magicclass/learning-space/rooms", headers=headers).json()["items"][0]
            # Read actual bridge state from the iframe without exposing auth credentials.
            state_script = """() => { window.__roomState = null; window.addEventListener('message', event => {
              if (event.data?.channel === '%s' && event.data.type === 'state') window.__roomState = event.data;
            }); }""" % CHANNEL
            guest.evaluate(state_script)
            guest.get_by_label("跟随发起人翻页").uncheck()
            guest_frame.get_by_role("button", name="Toggle sidebar", exact=True).click()
            guest_frame.locator('[data-testid="scene-item"]').nth(0).click()
            guest.get_by_label("跟随发起人翻页").check()
            guest.wait_for_function("window.__roomState?.sceneIndex === 1", timeout=15000)
            detail = client.get(f"/api/v1/magicclass/learning-space/rooms/{room['id']}", headers=headers).json()
            assert detail["host_uid"] == host_uid and detail["scene_index"] == 1
            # Rejoining the host must preserve the room cursor rather than resetting guests.
            host.reload()
            host.get_by_role("button", name=f"返回：{TITLE}", exact=True).click(timeout=30000)
            expect(host.get_by_text("已加入同一课堂", exact=False)).to_be_visible(timeout=180000)
            host.wait_for_timeout(2500)
            assert client.get(f"/api/v1/magicclass/learning-space/rooms/{room['id']}", headers=headers).json()["scene_index"] == 1
            payload = client.get(f"/api/v1/magicclass/learning-space/rooms/{room['id']}/archive", headers=headers).content
            with zipfile.ZipFile(io.BytesIO(payload)) as exported:
                manifest = json.loads(exported.read("manifest.json"))
                assert len(manifest["scenes"]) == 2
                assert any(name.startswith("media/") for name in exported.namelist())
            shots_dir = os.environ.get("E2E_SHOTS_DIR", "").strip()
            if shots_dir:
                output = Path(shots_dir)
                output.mkdir(parents=True, exist_ok=True)
                host.screenshot(path=str(output / "learning-room-desktop.png"))
            frame_box = host.locator('iframe[title="学习空间"]').bounding_box()
            assert frame_box["width"] > 800 and frame_box["height"] > 600, frame_box
            assert frame_box["y"] + frame_box["height"] <= 1000, frame_box
            guest.set_viewport_size({"width": 390, "height": 844})
            expect(guest.get_by_role("complementary", name="同学一起学")).to_be_visible()
            assert guest.evaluate("document.documentElement.scrollWidth <= innerWidth")
            frame_box = guest.locator('iframe[title="学习空间"]').bounding_box()
            panel_box = guest.get_by_role("complementary", name="同学一起学").bounding_box()
            assert frame_box["width"] > 300 and frame_box["height"] >= 280, frame_box
            assert panel_box["y"] + panel_box["height"] <= 844 - 60, panel_box
            if shots_dir:
                guest.screenshot(path=str(Path(shots_dir) / "learning-room-mobile.png"))
            print("PASS: UID invitation, same two-page lesson with media, two-way chat, follow navigation and host rejoin cursor")
        finally:
            for context in contexts:
                context.close()
            browser.close()


if __name__ == "__main__":
    main()
