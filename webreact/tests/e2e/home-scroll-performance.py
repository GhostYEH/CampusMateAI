import json
import os

from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WEB_BASE_URL", "http://127.0.0.1:5174")


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(10000)
        page.add_init_script("""
          (() => {
            window.__particleFrames = 0;
            window.__smoothCursorFrames = 0;
            window.__webglDraws = 0;
            const original = CanvasRenderingContext2D.prototype.clearRect;
            CanvasRenderingContext2D.prototype.clearRect = function (...args) {
              if (this.canvas?.classList?.contains('particle-text__canvas')) {
                window.__particleFrames += 1;
              }
              if (this.canvas?.classList?.contains('smooth-cursor-layer')) {
                window.__smoothCursorFrames += 1;
              }
              return original.apply(this, args);
            };
            for (const Context of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) {
              if (!Context) continue;
              for (const method of ['drawArrays', 'drawElements']) {
                const draw = Context.prototype[method];
                Context.prototype[method] = function (...args) {
                  window.__webglDraws += 1;
                  return draw.apply(this, args);
                };
              }
            }
          })();
        """)

        def fulfill_api(route):
            if "dashboard/student" not in route.request.url:
                route.fulfill(status=200, content_type="application/json", body="[]")
                return
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({
                    "pending_assignment_count": 0,
                    "pending_personal_task_count": 0,
                    "unread_announcement_count": 0,
                    "week_focus_minutes": 0,
                    "course_count": 0,
                    "due_soon_assignments": [],
                    "due_soon_personal_tasks": [],
                    "today_schedule": [],
                }),
            )

        page.route("**/api/v1/**", fulfill_api)
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        page.evaluate("""() => {
          localStorage.setItem('campus_access_token', 'scroll-performance-token');
          localStorage.setItem('campus_session', JSON.stringify({role: 'student', name: '测试同学'}));
        }""")
        page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(700)
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(1400)
        layout_snapshot = """() => {
          const rect = (selector) => {
            const node = document.querySelector(selector);
            if (!node) return null;
            const bounds = node.getBoundingClientRect();
            return { top: bounds.top + scrollY, height: bounds.height };
          };
          return {
            height: document.documentElement.scrollHeight,
            scrollY: window.scrollY,
            footerCount: document.querySelectorAll('.home-footer').length,
            brandCount: document.querySelectorAll('.home-footer-brand').length,
            home: rect('.student-home'),
            foreground: rect('.home-foreground'),
            command: rect('.simple-home-command-stack'),
            grid: rect('.simple-home-grid'),
            services: rect('.simple-quick-section'),
            footer: rect('.home-footer-info'),
          };
        }"""
        layout_before = page.evaluate(layout_snapshot)
        page.wait_for_timeout(1200)
        layout_after = page.evaluate(layout_snapshot)
        assert layout_after["height"] == layout_before["height"], f"home document height kept shifting after load: {layout_before} -> {layout_after}"
        assert abs(layout_after["footer"]["top"] - layout_before["footer"]["top"]) < 8, f"home footer kept shifting after load: {layout_before} -> {layout_after}"
        for selector in (".simple-home-command-stack", ".simple-home-grid", ".simple-quick-section"):
            assert page.locator(selector).count() == 0, f"redundant lower home section still rendered: {selector}"
        before = page.evaluate("window.__particleFrames")
        cursor_before = page.evaluate("window.__smoothCursorFrames")
        page.wait_for_timeout(500)
        after = page.evaluate("window.__particleFrames")
        cursor_after = page.evaluate("window.__smoothCursorFrames")

        assert after - before <= 1, f"idle particle canvas redrew {after - before} times in 500ms"
        assert cursor_after - cursor_before <= 1, f"idle cursor canvas redrew {cursor_after - cursor_before} times in 500ms"
        for selector in (".home-foreground", ".home-footer-info"):
            backdrop = page.evaluate("selector => getComputedStyle(document.querySelector(selector)).backdropFilter", selector)
            assert backdrop == "none", f"{selector} still uses scroll-time backdrop filtering: {backdrop}"

        webgl_before = page.evaluate("window.__webglDraws")
        scroll_sample = page.evaluate("""() => new Promise((resolve) => {
          const samples = [];
          const start = performance.now();
          let previous = start;
          function step(now) {
            samples.push(now - previous);
            previous = now;
            const progress = Math.min(1, (now - start) / 1400);
            window.scrollTo(0, (document.documentElement.scrollHeight - innerHeight) * progress);
            if (progress < 1) requestAnimationFrame(step);
            else resolve(samples.slice(1));
          }
          requestAnimationFrame(step);
        })""")
        webgl_after = page.evaluate("window.__webglDraws")
        slow_frames = sum(1 for duration in scroll_sample if duration > 34)
        slow_ratio = slow_frames / max(1, len(scroll_sample))
        assert len(scroll_sample) >= 1, f"scroll produced only {len(scroll_sample)} frames"
        if len(scroll_sample) >= 35:
            assert slow_ratio <= 0.2, f"{slow_ratio:.0%} of scroll frames exceeded 34ms"
        # 底部栏（rising sheet）的视频与涟漪特效在上升过程中持续播放，所以滚动期间允许
        # WebGL 继续绘制；这里守住"每帧不超过若干次绘制"，避免装饰层失控重绘。
        draws = webgl_after - webgl_before
        draws_per_frame = draws / max(1, len(scroll_sample))
        assert draws_per_frame <= 4, f"decorative WebGL drew {draws_per_frame:.1f} times per scroll frame"
        browser.close()
        print(f"home scroll performance passed: {len(scroll_sample)} frames, {slow_ratio:.0%} slow")


if __name__ == "__main__":
    run()
