from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page.add_init_script(
            """
            localStorage.setItem('campus_access_token', 'visual-check-token');
            localStorage.setItem('campus_refresh_token', 'visual-check-refresh');
            localStorage.setItem('campus_session', JSON.stringify({
              id: 1, role: 'student', name: '视觉检查用户'
            }));
            """
        )

        def mock_api(route):
            path = route.request.url.split('/api/v1/')[-1].split('?')[0]
            payloads = {
                'health': {},
                'student/dashboard': {},
                'student/courses': {'items': []},
                'community/posts': {'items': []},
                'study/sessions': [],
                'student/assignments': {'items': []},
                'student/tasks': {'items': []},
                'student/notices': {'items': []},
                'edu/schedule/items': {'items': []},
            }
            route.fulfill(status=200, content_type='application/json', body=__import__('json').dumps(payloads.get(path, {})))

        page.route('**/api/v1/**', mock_api)
        page.goto('http://127.0.0.1:5173/home')
        page.wait_for_load_state('networkidle')
        page.locator('.home-foreground').wait_for()

        mask = page.locator('.home-foreground')
        before = mask.evaluate("el => getComputedStyle(el, '::before').backgroundColor")
        after = mask.evaluate("el => getComputedStyle(el, '::after').backgroundColor")
        before_width = mask.evaluate("el => getComputedStyle(el, '::before').width")
        after_width = mask.evaluate("el => getComputedStyle(el, '::after').width")
        page.screenshot(path='edge-mask-check.png', full_page=True)

        print({
            'url': page.url,
            'before_background': before,
            'after_background': after,
            'before_width': before_width,
            'after_width': after_width,
        })
        browser.close()


if __name__ == '__main__':
    main()
