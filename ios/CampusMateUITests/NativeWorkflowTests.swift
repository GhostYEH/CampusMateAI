import XCTest

@MainActor
final class NativeWorkflowTests: XCTestCase {
    func testLoginCreateCompleteAndDeleteTask() async throws {
        // This suite cannot target a user-configured or production backend.
        let root = URL(string: "http://localhost:18927/api/v1/")!
        let (healthData, _) = try await URLSession.shared.data(from: root.appendingPathComponent("health"))
        let health = try XCTUnwrap(JSONSerialization.jsonObject(with: healthData) as? [String: Any])
        guard health["env"] as? String == "test" else { throw XCTSkip("Only the disposable test backend is permitted") }
        let username = "ios_ui_" + UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(16)
        let password = UUID().uuidString + "aA!"
        var registration = URLRequest(url: root.appendingPathComponent("auth/register"))
        registration.httpMethod = "POST"; registration.setValue("application/json", forHTTPHeaderField: "Content-Type")
        registration.httpBody = try JSONSerialization.data(withJSONObject: ["username": username, "password": password, "display_name": "原生 UI 验证"])
        let (_, response) = try await URLSession.shared.data(for: registration)
        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 201)

        let app = XCUIApplication()
        app.launchArguments = ["-campus.serverURL", root.absoluteString]
        app.launch()
        if app.tabBars.buttons["我的"].waitForExistence(timeout: 3) {
            app.tabBars.buttons["我的"].tap()
            let logout = app.buttons["退出登录"]
            if !logout.isHittable { app.swipeUp() }
            XCTAssertTrue(logout.waitForExistence(timeout: 5)); logout.tap()
            if app.alerts.buttons["退出登录"].waitForExistence(timeout: 1) { app.alerts.buttons["退出登录"].tap() }
        }
        let usernameField = app.textFields["login.username"]
        XCTAssertTrue(usernameField.waitForExistence(timeout: 15))
        usernameField.tap()
        if let previous = usernameField.value as? String, !previous.isEmpty, previous != "用户名" {
            usernameField.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: previous.count))
        }
        usernameField.typeText(username)
        app.secureTextFields["login.password"].tap(); app.secureTextFields["login.password"].typeText(password)
        app.buttons["login.submit"].tap()
        XCTAssertTrue(app.tabBars.buttons["待办"].waitForExistence(timeout: 20))
        app.tabBars.buttons["待办"].tap()
        app.buttons["tasks.add"].tap(); app.buttons["新建待办"].tap()
        let title = "原生操作验证 " + UUID().uuidString.prefix(6)
        let titleField = app.descendants(matching: .any)["tasks.title"].firstMatch
        XCTAssertTrue(titleField.waitForExistence(timeout: 5)); titleField.tap(); titleField.typeText(title)
        app.buttons["tasks.save"].tap()
        XCTAssertTrue(app.staticTexts[title].waitForExistence(timeout: 15)); app.staticTexts[title].tap()
        let complete = app.buttons["标记为已完成"]
        if !complete.isHittable { app.swipeUp() }
        XCTAssertTrue(complete.waitForExistence(timeout: 5)); complete.tap()
        XCTAssertTrue(app.buttons["恢复为待完成"].waitForExistence(timeout: 10))
        app.buttons["删除待办"].tap()
        app.buttons["删除"].firstMatch.tap()
        XCTAssertTrue(app.buttons["tasks.add"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.staticTexts[title].exists)
        app.tabBars.buttons["首页"].tap()
        app.buttons["自习室与学习足迹"].tap()
        XCTAssertTrue(app.buttons["开始专注"].waitForExistence(timeout: 10))
        let attachment = XCTAttachment(screenshot: app.screenshot()); attachment.lifetime = .keepAlways; add(attachment)
    }
}
