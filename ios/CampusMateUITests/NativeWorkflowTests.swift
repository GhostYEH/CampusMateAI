import XCTest

@MainActor
final class NativeWorkflowTests: XCTestCase {
    private let root = URL(string: "http://localhost:18927/api/v1/")!

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

    private func launchSignedOut() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-campus.serverURL", root.absoluteString,
                               "-campus.signOutOnLaunch", "-campus.resetLocalState"]
        app.launch()
        return app
    }

    private func signIn(_ app: XCUIApplication) async throws {
        let account = try await registerAccount()
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
        app.buttons["login.submit"].tap()
        XCTAssertTrue(app.buttons["打开待办"].waitForExistence(timeout: 25), "首页场景应在登录后出现")
    }

    private func snapshot(_ app: XCUIApplication, _ name: String) {
        // Let the push/pop transition settle so the capture shows the page,
        // not a frame of the navigation animation.
        Thread.sleep(forTimeInterval: 0.6)
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private func back(_ app: XCUIApplication) {
        // Several pushed screens keep their own glass back control in the
        // hierarchy; tap the one that is actually on screen.
        let query = app.buttons.matching(NSPredicate(format: "label == %@", "返回"))
        let deadline = Date().addingTimeInterval(8)
        while Date() < deadline {
            for index in 0..<query.count {
                let button = query.element(boundBy: index)
                if button.exists, button.isHittable {
                    button.tap()
                    Thread.sleep(forTimeInterval: 0.4)
                    return
                }
            }
            usleep(200_000)
        }
        XCTFail("二级页面应提供返回校园的控件")
    }

    // MARK: - Workflow

    func testLoginTaskAndFocusWorkflow() async throws {
        try await requireDisposableBackend()
        let app = launchSignedOut()
        try await signIn(app)
        snapshot(app, "01-home-twilight")

        // 待办：新建 → 完成 → 恢复 → 删除
        app.buttons["打开待办"].tap()
        XCTAssertTrue(app.buttons["tasks.add"].waitForExistence(timeout: 10))
        snapshot(app, "02-task-journal")
        app.buttons["tasks.add"].tap()
        XCTAssertTrue(app.buttons["tasks.create.manual"].waitForExistence(timeout: 5))
        app.buttons["tasks.create.manual"].tap()
        let title = "原生操作验证 " + UUID().uuidString.prefix(6)
        let titleField = app.descendants(matching: .any)["tasks.title"].firstMatch
        XCTAssertTrue(titleField.waitForExistence(timeout: 5))
        titleField.tap()
        titleField.typeText(title)
        app.buttons["tasks.save"].tap()
        XCTAssertTrue(app.staticTexts[title].waitForExistence(timeout: 15))
        app.staticTexts[title].tap()
        let complete = app.buttons["标记为已完成"]
        if !complete.isHittable { app.swipeUp() }
        XCTAssertTrue(complete.waitForExistence(timeout: 6))
        complete.tap()
        XCTAssertTrue(app.buttons["恢复为待完成"].waitForExistence(timeout: 10))
        app.buttons["删除待办"].tap()
        app.buttons["删除"].firstMatch.tap()
        XCTAssertTrue(app.buttons["tasks.add"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.staticTexts[title].exists)
        back(app)

        // 自习室：真实会话入口
        XCTAssertTrue(app.buttons["进入一楼自习室"].waitForExistence(timeout: 8))
        app.buttons["进入一楼自习室"].tap()
        XCTAssertTrue(app.buttons["开始专注"].waitForExistence(timeout: 10))
        snapshot(app, "03-focus-hall")
        back(app)

        // 互动课堂 → 共同课堂
        XCTAssertTrue(app.buttons["进入互动课堂"].waitForExistence(timeout: 8))
        app.buttons["进入互动课堂"].tap()
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

    func testMainScreensMatchAndroidDesign() async throws {
        try await requireDisposableBackend()
        let app = launchSignedOut()
        try await signIn(app)

        // 图书馆书架
        app.buttons["进入二楼图书馆"].tap()
        XCTAssertTrue(app.staticTexts["我的课程书架"].waitForExistence(timeout: 10))
        snapshot(app, "10-library")
        back(app)

        // 个人中心 → 通知与提醒
        XCTAssertTrue(app.buttons["打开我的"].waitForExistence(timeout: 8))
        openFromHome(app, "打开我的")
        XCTAssertTrue(app.staticTexts["更多服务"].waitForExistence(timeout: 10))
        snapshot(app, "11-profile")
        app.staticTexts["系统消息"].tap()
        XCTAssertTrue(app.staticTexts["课程与校园通知"].waitForExistence(timeout: 10))
        snapshot(app, "12-notices")
        back(app)
        back(app)

        // 考试安排（待办页的日历菜单）
        app.buttons["打开待办"].tap()
        XCTAssertTrue(app.buttons["日历与考试"].waitForExistence(timeout: 8))
        app.buttons["日历与考试"].tap()
        app.buttons["考试安排"].tap()
        XCTAssertTrue(app.staticTexts["考试安排"].waitForExistence(timeout: 10))
        snapshot(app, "16-exams")
        back(app)
        back(app)

        // 社区
        XCTAssertTrue(app.buttons["打开社区"].waitForExistence(timeout: 8))
        app.buttons["打开社区"].tap()
        XCTAssertTrue(app.staticTexts["校园论坛"].waitForExistence(timeout: 10))
        snapshot(app, "13-community")
        back(app)

        // CPM
        app.buttons["打开CPM"].tap()
        XCTAssertTrue(app.staticTexts["CPM"].waitForExistence(timeout: 10))
        snapshot(app, "14-cpm")
        back(app)

        // 学习足迹
        app.buttons["打开学习足迹"].tap()
        XCTAssertTrue(app.staticTexts["学习足迹"].waitForExistence(timeout: 10))
        snapshot(app, "15-focus-history")
        back(app)
    }

    private func openFromHome(_ app: XCUIApplication, _ label: String) {
        let button = app.buttons[label]
        // Let the pop transition finish before scrolling; otherwise the first
        // swipe is swallowed by the navigation animation.
        Thread.sleep(forTimeInterval: 0.5)
        // The scene is taller than the screen on iPad: the arch row sits below
        // the fold, so scroll towards the bottom first and only fall back to
        // scrolling up when the target is above the current position.
        for _ in 0..<6 where !button.isHittable { app.swipeUp() }
        for _ in 0..<4 where !button.isHittable { app.swipeDown() }
        XCTAssertTrue(button.isHittable, "首页入口 \(label) 应可点击")
        button.tap()
    }
}



