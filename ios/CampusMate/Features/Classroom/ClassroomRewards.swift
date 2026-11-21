import CryptoKit
import Foundation

/// 上游课堂 WebView 的游戏化 HUD。
///
/// 规则脚本与 Android 共用 `Resources/classroom-rewards.js`（`scripts/tests/classroom-rewards.test.mjs`
/// 校验两份逐字一致）；账本 key 由服务 + 账号 + 课堂派生，只有拿到稳定的
/// `data-scene-id` 才记账。旧版 v1 账本不迁移、不删除。
enum ClassroomRewards {
    static func script(accountKey: String, classroom: String, totalScenes: Int? = nil, bottom: Int = 74) -> String {
        let digest = SHA256.hash(data: Data("\(accountKey)|\(classroom)".utf8))
            .map { String(format: "%02x", $0) }
            .joined()
        var config: [String: Any] = [
            "key": "campusmate:classroom-rewards:v2:\(digest)",
            "classroomLabel": "网页兼容课堂",
            "accountBound": true,
            "bottom": bottom,
        ]
        if let totalScenes, totalScenes > 0 {
            config["totalScenes"] = totalScenes
        }
        let data = (try? JSONSerialization.data(withJSONObject: config, options: [.sortedKeys]))
            ?? Data("{}".utf8)
        let json = String(data: data, encoding: .utf8) ?? "{}"
        let script = Bundle.main.url(forResource: "classroom-rewards", withExtension: "js")
            .flatMap { try? String(contentsOf: $0, encoding: .utf8) }
            ?? ""
        return "window.__campusRewardsConfig = \(json);\n" + script
    }
}
