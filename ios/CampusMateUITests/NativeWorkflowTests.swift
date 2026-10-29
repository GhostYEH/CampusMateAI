import XCTest
import UIKit

@MainActor
final class NativeWorkflowTests: XCTestCase {
    private let root = URL(string: "http://localhost:18927/api/v1/")!

    override func setUpWithError() throws {
        continueAfterFailure = false
        XCUIDevice.shared.orientation = .portrait
    }

    // MARK: - Helpers

    private func requireDisposableBackend() async throws {
        let (healthData, _) = try await URLSession.shared.data(from: root.appendingPathComponent("health"))
        let health = try XCTUnwrap(JSONSerialization.jsonObject(with: healthData) as? [String: Any])
        guard health["env"] as? String == "test" else { throw XCTSkip("Only the disposable test backend is permitted") }
    }

    @discardableResult
    private func registerAccount() async throws -> (username: String, password: String) {
        // Lowercase letters and digits only: avoids shift-key and autocorrect
        // surprises when the credentials are typed through the software keyboard.
        let token = UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
        let username = "iosui" + token.prefix(12)
        let password = "campus" + token.suffix(10) + "9"
        var registration = URLRequest(url: root.appendingPathComponent("auth/register"))
        registration.httpMethod = "POST"
        registration.setValue("application/json", forHTTPHeaderField: "Content-Type")
        registration.httpBody = try JSONSerialization.data(withJSONObject: [
            "username": username, "password": password, "display_name": "原生 UI 验证",
        ])
        let (_, response) = try await URLSession.shared.data(for: registration)
        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 201)
        return (String(username), password)
    }

    /// The system may offer to save these disposable test credentials when
    /// password editing ends. Dismiss only that prompt, never save them.
    private func dismissSavePasswordPrompt(_ app: XCUIApplication, timeout: TimeInterval = 1) {
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let deadline = Date().addingTimeInterval(timeout)
        repeat {
            for owner in [springboard, app] {
                let title = owner.staticTexts.matching(NSPredicate(
                    format: "label CONTAINS[c] %@ OR label CONTAINS[c] %@", "保存密码", "Save Password"
                )).firstMatch
                guard title.exists else { continue }
                for label in ["以后", "稍后", "Not Now", "Later"] {
                    let button = owner.buttons[label]
                    if button.exists && button.isHittable { button.tap(); return }
                }
            }
            usleep(150_000)
        } while Date() < deadline
    }

    private func launchSignedOut(theme: String = "light", largeText: Bool = false) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-campus.serverURL", root.absoluteString,
                               "-campus.signOutOnLaunch", "-campus.resetLocalState", "-campus.theme", theme,
                               "-campus.reduceMotion", "YES"]
        if largeText { app.launchArguments += ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"] }
        app.launch()
        return app
    }

    private func signIn(_ app: XCUIApplication, account provided: (username: String, password: String)? = nil,
                        remember: Bool = true) async throws {
        let account: (username: String, password: String)
        if let provided { account = provided } else { account = try await registerAccount() }
        let usernameField = app.textFields["login.username"]
        XCTAssertTrue(usernameField.waitForExistence(timeout: 20))
        usernameField.tap()
        if !app.keyboards.element.waitForExistence(timeout: 3) { usernameField.tap() }
        XCTAssertTrue(app.keyboards.element.waitForExistence(timeout: 5), "点击账号后应出现键盘")
        usernameField.typeText(account.username)
        let passwordField = app.secureTextFields["login.password"]
        passwordField.tap()
        XCTAssertTrue(app.keyboards.element.waitForExistence(timeout: 5), "点击密码后应出现键盘")
        passwordField.typeText(account.password)
        dismissSavePasswordPrompt(app)
        if !remember {
            let toggle = app.buttons["login.remember"]
            for _ in 0..<5 where !toggle.isHittable { app.swipeUp() }
            XCTAssertTrue(toggle.isHittable)
            toggle.tap()
        }
        let submit = app.buttons["login.submit"]
        for _ in 0..<5 where !submit.isHittable { app.swipeUp() }
        submit.tap()
        dismissSavePasswordPrompt(app, timeout: 2)
        XCTAssertTrue(app.buttons["打开待办"].waitForExistence(timeout: 25), "首页场景应在登录后出现")
    }

    private func recordFailureDiagnostics(_ app: XCUIApplication, _ name: String) {
        let screenshot = XCTAttachment(image: flattened(XCUIScreen.main.screenshot().image))
        screenshot.name = "\(name)-screen"
        screenshot.lifetime = .keepAlways
        add(screenshot)
        let hierarchy = XCTAttachment(string: app.debugDescription)
        hierarchy.name = "\(name)-hierarchy"
        hierarchy.lifetime = .keepAlways
        add(hierarchy)
    }

    private func snapshot(_ app: XCUIApplication, _ name: String) {
        // Let the push/pop transition settle so the capture shows the page,
        // not a frame of the navigation animation.
        Thread.sleep(forTimeInterval: 0.6)
        let attachment = XCTAttachment(image: flattened(XCUIScreen.main.screenshot().image))
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    /// XCUIScreen returns a portrait pixel buffer with a non-zero UIImage
    /// orientation in landscape; drawing through UIKit bakes that orientation
    /// into the exported image and keeps the screenshot full-screen.
    private func flattened(_ image: UIImage) -> UIImage {
        guard image.imageOrientation != .up else { return image }
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        return UIGraphicsImageRenderer(size: image.size, format: format).image { _ in
            image.draw(in: CGRect(origin: .zero, size: image.size))
        }
    }

    private func back(_ app: XCUIApplication, expecting marker: XCUIElement? = nil) {
        // Several pushed screens keep their own glass back control in the
        // hierarchy; tap the one that is actually on screen.
        let query = app.buttons.matching(NSPredicate(format: "label == %@", "返回"))
        let deadline = Date().addingTimeInterval(8)
        while Date() < deadline {
            for index in 0..<query.count {
                let button = query.element(boundBy: index)
                if button.exists, button.isHittable {
                    button.tap()
                    // Wait out the pop animation before the caller taps again.
                    Thread.sleep(forTimeInterval: 0.7)
                    if let marker {
                        XCTAssertTrue(marker.waitForExistence(timeout: 6), "返回后应回到预期页面")
                    }
                    return
                }
            }
            usleep(200_000)
        }
        XCTFail("二级页面应提供返回校园的控件")
    }

    /// Taps a control and retries once if the transition never starts. The
    /// simulator occasionally drops a synthesized tap while another agent is
    /// loading the same host, which used to abort the workflow at the composer.
    private func tap(_ button: XCUIElement, until target: XCUIElement) {
        for _ in 0..<2 {
            if button.exists, button.isHittable { button.tap() }
            if target.waitForExistence(timeout: 4) { return }
        }
        XCTFail("点击 \(button) 后应出现 \(target)")
    }

    /// A fresh install asks for notification permission when the first exam
    /// reminder is saved; the system alert otherwise blocks the sheet dismissal.
    private func allowNotificationsIfNeeded() {
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let deadline = Date().addingTimeInterval(4)
        while Date() < deadline {
            for label in ["允许", "Allow"] {
                let button = springboard.buttons[label]
                if button.exists, button.isHittable { button.tap(); return }
            }
            usleep(150_000)
        }
    }

    private func assertKeyboardDismisses(_ app: XCUIApplication, beside field: XCUIElement, atMargin: Bool = true) {
        let keyboard = app.keyboards.element
        XCTAssertTrue(keyboard.waitForExistence(timeout: 5))
        let window = app.windows.firstMatch
        let frame = window.frame
        // Stay inside the horizontal safe area in landscape, and above the keyboard.
        let targetY = atMargin ? field.frame.midY : field.frame.minY - 14
        let y = max(frame.minY + 50, min(targetY, keyboard.frame.minY - 20))
        let x = frame.width * (atMargin ? 0.08 : 0.5)
        window.coordinate(withNormalizedOffset: CGVector(dx: 0, dy: 0))
            .withOffset(CGVector(dx: x, dy: y - frame.minY)).tap()
        let hidden = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: keyboard)
        XCTAssertEqual(XCTWaiter.wait(for: [hidden], timeout: 5), .completed, "点击页面空白应收起键盘")
    }

    private func exerciseLoginKeyboardDismissal(_ app: XCUIApplication) {
        let username = app.textFields["login.username"]
        XCTAssertTrue(username.waitForExistence(timeout: 10))
        username.tap()
        username.typeText("student")
        assertKeyboardDismisses(app, beside: username)
        username.tap()
        XCTAssertTrue(app.keyboards.element.waitForExistence(timeout: 5), "收起后应能重新聚焦账号")

        let password = app.secureTextFields["login.password"]
        password.tap()
        password.typeText("password123")
        assertKeyboardDismisses(app, beside: password)
        dismissSavePasswordPrompt(app, timeout: 2)
        password.tap()
        XCTAssertTrue(app.keyboards.element.waitForExistence(timeout: 5), "收起后应能重新聚焦密码")
        app.buttons["显示密码"].tap()
        dismissSavePasswordPrompt(app, timeout: 2)
        let visiblePassword = app.textFields["login.password.visible"]
        XCTAssertTrue(visiblePassword.waitForExistence(timeout: 5), "切换密码可见性应保持可操作")
        let window = app.windows.firstMatch
        let frame = visiblePassword.frame
        let keyboard = app.keyboards.element
        guard !frame.isEmpty, window.frame.contains(frame),
              !keyboard.exists || !keyboard.frame.intersects(frame) else {
            recordFailureDiagnostics(app, "login-visible-password-outside-viewport")
            XCTFail("明文密码输入框应位于可见区域")
            return
        }
        let hittable = XCTNSPredicateExpectation(predicate: NSPredicate(format: "hittable == true"), object: visiblePassword)
        if XCTWaiter.wait(for: [hittable], timeout: 3) == .completed {
            visiblePassword.tap()
        } else {
            // After SecureField becomes TextField, XCTest can report a visible
            // field as non-hittable. Tap the verified on-screen field itself.
            let windowFrame = window.frame
            window.coordinate(withNormalizedOffset: CGVector(dx: 0, dy: 0))
                .withOffset(CGVector(dx: frame.midX - windowFrame.minX, dy: frame.midY - windowFrame.minY)).tap()
        }
        guard keyboard.waitForExistence(timeout: 5) else {
            recordFailureDiagnostics(app, "login-visible-password-keyboard-missing")
            XCTFail("点击明文密码输入框后应出现键盘")
            return
        }
        app.typeText("z")
        let editedPassword = visiblePassword.value as? String ?? ""
        XCTAssertEqual(editedPassword.count, "password123".count + 1, "明文密码应能编辑")
        XCTAssertEqual(editedPassword.replacingOccurrences(of: "z", with: ""), "password123")
        assertKeyboardDismisses(app, beside: visiblePassword, atMargin: false)
        dismissSavePasswordPrompt(app, timeout: 2)

        let serverButton = app.buttons["服务连接"]
        for _ in 0..<5 where !serverButton.isHittable { app.swipeUp() }
        XCTAssertTrue(serverButton.isHittable)
        serverButton.tap()
        let server = app.textFields["login.server"]
        for _ in 0..<5 where !server.isHittable { app.swipeUp() }
        XCTAssertTrue(server.isHittable)
        server.tap()
        XCTAssertTrue(app.keyboards.element.waitForExistence(timeout: 5))
        assertKeyboardDismisses(app, beside: server)
        server.tap()
        XCTAssertTrue(app.keyboards.element.waitForExistence(timeout: 5), "收起后应能重新聚焦服务地址")
        let originalAddress = server.value as? String ?? ""
        let marker = "x" + UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased().prefix(8)
        server.typeText(marker)
        let editedAddress = server.value as? String ?? ""
        XCTAssertTrue(editedAddress.contains(marker), "重新聚焦后服务地址应可编辑")
        XCTAssertEqual(editedAddress.replacingOccurrences(of: marker, with: ""), originalAddress)
        assertKeyboardDismisses(app, beside: server)
    }

    func testRememberAccountControlsSessionRestoration() async throws {
        try await requireDisposableBackend()
        let account = try await registerAccount()
        let app = launchSignedOut()
        try await signIn(app, account: account, remember: false)
        dismissSavePasswordPrompt(app)

        app.terminate()
        app.launchArguments = ["-campus.serverURL", root.absoluteString, "-campus.reduceMotion", "YES"]
        app.launch()
        let username = app.textFields["login.username"]
        XCTAssertTrue(username.waitForExistence(timeout: 15), "未记住账号时重启应回到登录页")
        // XCTest may report an empty field's placeholder as its value.
        // Typing one character distinguishes that from a retained username.
        username.tap()
        username.typeText("z")
        XCTAssertEqual(username.value as? String, "z", "未记住账号时不应保留用户名")
        username.typeText(XCUIKeyboardKey.delete.rawValue)

        try await signIn(app, account: account)
        dismissSavePasswordPrompt(app)
        app.terminate()
        app.launch()
        XCTAssertTrue(app.buttons["打开待办"].waitForExistence(timeout: 25), "记住账号后重启应恢复会话")
    }

    func testLoginKeyboardDismissal() {
        exerciseLoginKeyboardDismissal(launchSignedOut())
    }

    func testLoginKeyboardDismissalInLandscape() {
        XCUIDevice.shared.orientation = .landscapeLeft
        defer { XCUIDevice.shared.orientation = .portrait }
        let app = launchSignedOut()
        let window = app.windows.firstMatch
        for _ in 0..<20 where window.frame.width <= window.frame.height { usleep(250_000) }
        XCTAssertGreaterThan(window.frame.width, window.frame.height)
        exerciseLoginKeyboardDismissal(app)
    }

    // MARK: - Workflow

    func testLoginTaskAndFocusWorkflow() async throws {
        try await requireDisposableBackend()
        let app = launchSignedOut()
        try await signIn(app)
        snapshot(app, "01-home-twilight")

        // 待办：新建 → 完成 → 恢复 → 删除
        openFromHome(app, "打开待办")
        XCTAssertTrue(app.buttons["tasks.add"].waitForExistence(timeout: 10))
        snapshot(app, "02-task-journal")
        tap(app.buttons["tasks.add"], until: app.buttons["tasks.create.manual"])
        app.buttons["tasks.create.manual"].tap()
        let title = "原生操作验证 " + UUID().uuidString.prefix(6)
        let titleField = app.descendants(matching: .any)["tasks.title"].firstMatch
        XCTAssertTrue(titleField.waitForExistence(timeout: 5))
        titleField.tap()
        titleField.typeText(title)
        app.buttons["tasks.save"].tap()
        XCTAssertTrue(app.staticTexts[title].waitForExistence(timeout: 15))
        tap(app.staticTexts[title], until: app.buttons["标记为已完成"])
        let complete = app.buttons["标记为已完成"]
        if !complete.isHittable { app.swipeUp() }
        XCTAssertTrue(complete.waitForExistence(timeout: 6))
        tap(complete, until: app.buttons["恢复为待完成"])
        XCTAssertTrue(app.buttons["恢复为待完成"].waitForExistence(timeout: 10))
        app.buttons["删除待办"].tap()
        app.buttons["删除"].firstMatch.tap()
        XCTAssertTrue(app.buttons["tasks.add"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.staticTexts[title].exists)
        back(app)

        // 自习室：真实会话入口
        XCTAssertTrue(app.buttons["进入一楼自习室"].waitForExistence(timeout: 8))
        openFromHome(app, "进入一楼自习室")
        XCTAssertTrue(app.buttons["开始专注"].waitForExistence(timeout: 10))
        snapshot(app, "03-focus-hall")
        back(app)

        // 互动课堂 → 共同课堂
        XCTAssertTrue(app.buttons["进入互动课堂"].waitForExistence(timeout: 8))
        openFromHome(app, "进入互动课堂")
        XCTAssertTrue(app.staticTexts["同学一起学"].waitForExistence(timeout: 8))
        app.staticTexts["同学一起学"].tap()
        XCTAssertTrue(app.buttons["新建讨论课堂"].waitForExistence(timeout: 10))
        app.buttons["新建讨论课堂"].tap()
        let roomTitle = "原生协作验证 " + UUID().uuidString.prefix(6)
        app.alerts.textFields.firstMatch.typeText(roomTitle)
        app.alerts.buttons["创建"].tap()
        XCTAssertTrue(app.staticTexts[roomTitle].waitForExistence(timeout: 15))
        let chatInput = app.textFields["和同学聊聊…"]
        XCTAssertTrue(chatInput.waitForExistence(timeout: 6))
        chatInput.tap()
        chatInput.typeText("这是一条原生验证消息")
        app.buttons["发送"].tap()
        XCTAssertTrue(app.staticTexts["这是一条原生验证消息"].waitForExistence(timeout: 10))
        snapshot(app, "04-learning-room")
        app.buttons["room.leave"].tap()
        let confirmLeave = app.buttons["room.leave.confirm"].firstMatch
        XCTAssertTrue(confirmLeave.waitForExistence(timeout: 5))
        confirmLeave.tap()
        XCTAssertTrue(app.buttons["新建讨论课堂"].waitForExistence(timeout: 10))
        snapshot(app, "05-learning-rooms")
    }

    func testMainScreensNavigationAndLayout() async throws {
        try await requireDisposableBackend()
        let app = launchSignedOut()
        try await signIn(app)

        // 图书馆书架
        openFromHome(app, "进入二楼图书馆")
        XCTAssertTrue(app.staticTexts["我的课程书架"].waitForExistence(timeout: 10))
        snapshot(app, "10-library")
        back(app)

        // 个人中心 → 通知与提醒
        XCTAssertTrue(app.buttons["打开我的"].waitForExistence(timeout: 8))
        openFromHome(app, "打开我的")
        XCTAssertTrue(app.staticTexts["更多服务"].waitForExistence(timeout: 10))
        snapshot(app, "11-profile")
        let notices = app.buttons["profile.notices"]
        XCTAssertTrue(notices.waitForExistence(timeout: 5)); notices.tap()
        XCTAssertTrue(app.staticTexts["课程与校园通知"].waitForExistence(timeout: 10))
        let unreadOnly = app.switches["只看未读"]
        XCTAssertTrue(unreadOnly.waitForExistence(timeout: 5))
        let initialValue = unreadOnly.value as? String
        unreadOnly.tap()
        XCTAssertNotEqual(unreadOnly.value as? String, initialValue, "未读筛选开关应可切换")
        unreadOnly.tap()
        XCTAssertEqual(unreadOnly.value as? String, initialValue)
        snapshot(app, "12-notices")
        back(app, expecting: app.staticTexts["更多服务"])
        back(app, expecting: app.buttons["打开待办"])

        // 考试安排（待办页的日历菜单）
        openFromHome(app, "打开待办")
        XCTAssertTrue(app.buttons["日历与考试"].waitForExistence(timeout: 8))
        app.buttons["日历与考试"].tap()
        app.buttons["考试安排"].tap()
        XCTAssertTrue(app.staticTexts["考试安排"].waitForExistence(timeout: 10))
        snapshot(app, "16-exams")
        app.buttons["添加考试"].tap()
        let examTitle = "原生考试验证 " + UUID().uuidString.prefix(6)
        let examField = app.textFields["课程名称"]
        XCTAssertTrue(examField.waitForExistence(timeout: 5))
        examField.tap(); examField.typeText(examTitle)
        app.buttons["保存"].tap()
        allowNotificationsIfNeeded()
        XCTAssertTrue(app.staticTexts[examTitle].waitForExistence(timeout: 15))
        tap(app.staticTexts[examTitle], until: app.staticTexts["考试详情"])
        XCTAssertTrue(app.staticTexts["考试详情"].waitForExistence(timeout: 10))
        snapshot(app, "17-exam-detail")
        back(app, expecting: app.staticTexts["考试安排"])
        back(app, expecting: app.buttons["tasks.add"])
        back(app, expecting: app.buttons["打开待办"])

        // 社区
        XCTAssertTrue(app.buttons["打开社区"].waitForExistence(timeout: 8))
        openFromHome(app, "打开社区")
        XCTAssertTrue(app.staticTexts["校园论坛"].waitForExistence(timeout: 10))
        snapshot(app, "13-community")
        back(app)

        // CPM
        openFromHome(app, "打开CPM")
        XCTAssertTrue(app.staticTexts["CPM"].waitForExistence(timeout: 10))
        snapshot(app, "14-cpm")
        back(app)

        // 学习足迹
        openFromHome(app, "打开学习足迹")
        XCTAssertTrue(app.staticTexts["学习足迹"].waitForExistence(timeout: 10))
        snapshot(app, "15-focus-history")
        back(app)
    }

    private func openFromHome(_ app: XCUIApplication, _ label: String) {
        dismissSavePasswordPrompt(app)
        let button = app.buttons[label]
        // Let the pop transition finish before scrolling; otherwise the first
        // swipe is swallowed by the navigation animation.
        Thread.sleep(forTimeInterval: 0.5)
        // The scene is taller than the screen on iPad: the arch row sits below
        // the fold, so scroll towards the bottom first and only fall back to
        // scrolling up when the target is above the current position.
        // XCTest calls partly clipped illustration hotspots hittable, including
        // ones whose centre is behind the home indicator. Scroll the full hit
        // region into the safe viewport instead of tapping the clipped sliver.
        let viewport = app.windows.firstMatch.frame.insetBy(dx: 0, dy: 40)
        func isVisible() -> Bool {
            let frame = button.frame
            return button.isHittable && frame.minY >= viewport.minY && frame.maxY <= viewport.maxY && frame.intersects(viewport)
        }
        for _ in 0..<6 where !isVisible() { app.swipeUp() }
        for _ in 0..<6 where !isVisible() { app.swipeDown() }
        if !button.isHittable { recordFailureDiagnostics(app, "home-entry-not-hittable") }
        XCTAssertTrue(button.isHittable, "首页入口 \(label) 应可点击")
        button.tap()
    }

    func testLaterTaskPagesAndNestedFocusNavigation() async throws {
        try await requireDisposableBackend()
        let account = try await registerAccount()
        var login = URLRequest(url: root.appendingPathComponent("auth/login"))
        login.httpMethod = "POST"; login.setValue("application/json", forHTTPHeaderField: "Content-Type")
        login.httpBody = try JSONSerialization.data(withJSONObject: ["username": account.username, "password": account.password])
        let (data, _) = try await URLSession.shared.data(for: login)
        let token = try XCTUnwrap((JSONSerialization.jsonObject(with: data) as? [String: Any])?["access_token"] as? String)
        for number in 0..<105 {
            var request = URLRequest(url: root.appendingPathComponent("tasks"))
            request.httpMethod = "POST"; request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
            request.httpBody = try JSONSerialization.data(withJSONObject: ["title": "分页审查待办 \(number)"])
            let (_, response) = try await URLSession.shared.data(for: request)
            XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 201)
        }
        let app = launchSignedOut()
        try await signIn(app, account: account)
        openFromHome(app, "打开待办")
        let search = app.textFields["搜索作业或课程"]
        XCTAssertTrue(search.waitForExistence(timeout: 10))
        search.tap(); search.typeText("分页审查待办 0\n")
        let target = app.staticTexts["分页审查待办 0"]
        XCTAssertTrue(target.waitForExistence(timeout: 15), "第一页以外的待办应可搜索")
        tap(target, until: app.buttons["围绕这项任务专注"])
        let focus = app.buttons["围绕这项任务专注"]
        for _ in 0..<4 where !focus.isHittable { app.swipeUp() }
        XCTAssertTrue(focus.isHittable); tap(focus, until: app.buttons["开始专注"])
        XCTAssertTrue(app.buttons["开始专注"].waitForExistence(timeout: 10))
        back(app)
        XCTAssertTrue(app.buttons["围绕这项任务专注"].waitForExistence(timeout: 8), "返回应回到任务详情，而不是越级回首页")
        focus.tap()
        XCUIDevice.shared.orientation = .landscapeLeft
        let window = app.windows.firstMatch
        for _ in 0..<20 where window.frame.width <= window.frame.height { usleep(250_000) }
        XCTAssertGreaterThan(window.frame.width, window.frame.height, "旋转完成后再验证横屏布局")
        defer { XCUIDevice.shared.orientation = .portrait }
        let start = app.buttons["开始专注"]
        for _ in 0..<5 where !start.isHittable { app.swipeUp() }
        XCTAssertTrue(start.isHittable); start.tap()
        let pause = app.buttons["暂停"]
        XCTAssertTrue(pause.waitForExistence(timeout: 10))
        for _ in 0..<4 where !pause.isHittable { app.swipeUp() }
        XCTAssertTrue(pause.isHittable, "横屏的专注操作应可见或可滚动到达")
        pause.tap()
        XCTAssertTrue(app.buttons["继续"].waitForExistence(timeout: 10))
        snapshot(app, "20-landscape-focus-paused")
    }

    func testLargeTextDarkSettingsAndAssistantWorkflowSheet() async throws {
        try await requireDisposableBackend()
        let app = launchSignedOut(theme: "dark", largeText: true)
        try await signIn(app)
        openFromHome(app, "打开我的")
        let settings = app.buttons["profile.settings"]
        XCTAssertTrue(settings.waitForExistence(timeout: 10)); settings.tap()
        XCTAssertTrue(app.staticTexts["系统设置"].waitForExistence(timeout: 10))
        snapshot(app, "30-dark-large-settings")
        let contribution = app.buttons["settings.contribution"]
        XCTAssertTrue(contribution.waitForExistence(timeout: 5))
        for _ in 0..<8 where !contribution.isHittable { app.swipeUp() }
        XCTAssertTrue(contribution.isHittable, "大字体下应能滚动到模型共建入口")
        contribution.tap()
        XCTAssertTrue(app.staticTexts["隐私优先的单帧共建"].waitForExistence(timeout: 10))
        snapshot(app, "34-dark-large-contribution")
        back(app, expecting: app.staticTexts["系统设置"])
        back(app, expecting: app.staticTexts["更多服务"])
        XCTAssertTrue(app.buttons["profile.notices"].waitForExistence(timeout: 5))
        app.buttons["profile.notices"].tap()
        XCTAssertTrue(app.staticTexts["课程与校园通知"].waitForExistence(timeout: 10))
        snapshot(app, "32-dark-large-notices")
        back(app, expecting: app.staticTexts["更多服务"])
        back(app, expecting: app.buttons["打开CPM"])
        openFromHome(app, "打开CPM")
        let input = app.textFields["assistant.input"]
        XCTAssertTrue(input.waitForExistence(timeout: 5)); input.tap()
        XCTAssertTrue(app.keyboards.element.waitForExistence(timeout: 5))
        // ASCII keeps this contrast/layout check independent of the simulator's active input method.
        let draft = "Review tomorrow"
        input.typeText(draft)
        let draftAppeared = XCTNSPredicateExpectation(predicate: NSPredicate(format: "value == %@", draft), object: input)
        XCTAssertEqual(XCTWaiter.wait(for: [draftAppeared], timeout: 5), .completed)
        snapshot(app, "33-dark-assistant-input")
        app.buttons["学习计划与工作流"].tap()
        let goals = app.buttons["assistant.workflow.goals"]
        XCTAssertTrue(goals.waitForExistence(timeout: 5)); goals.tap()
        XCTAssertTrue(app.buttons["新建目标"].waitForExistence(timeout: 10), "弹层中的工作流必须有可用的导航栈")
        snapshot(app, "31-assistant-workflow-goals")
        back(app)
        XCTAssertTrue(app.buttons["assistant.workflow.goals"].waitForExistence(timeout: 5), "返回后应保留工作流菜单弹层")
    }
}



