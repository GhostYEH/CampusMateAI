import Foundation
import Security
import CampusCore

enum KeychainStore {
    private static var service: String { (Bundle.main.bundleIdentifier ?? "CampusMate") + ".sessions" }

    static func load(server: String) -> Session? {
        var query = baseQuery(server)
        query[kSecReturnData] = true
        query[kSecMatchLimit] = kSecMatchLimitOne
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return try? JSONDecoder().decode(Session.self, from: data)
    }

    static func save(_ session: Session?, server: String) throws {
        guard let session else {
            let result = SecItemDelete(baseQuery(server) as CFDictionary)
            guard result == errSecSuccess || result == errSecItemNotFound else { throw StoreError(status: result) }
            return
        }
        let data = try JSONEncoder().encode(session)
        let query = baseQuery(server)
        let update = SecItemUpdate(query as CFDictionary, [kSecValueData: data] as CFDictionary)
        if update == errSecSuccess { return }
        guard update == errSecItemNotFound else { throw StoreError(status: update) }
        var item = query
        item[kSecValueData] = data
        item[kSecAttrAccessible] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let result = SecItemAdd(item as CFDictionary, nil)
        guard result == errSecSuccess else { throw StoreError(status: result) }
    }

    private static func baseQuery(_ server: String) -> [CFString: Any] {
        [kSecClass: kSecClassGenericPassword, kSecAttrService: service, kSecAttrAccount: server]
    }

    private struct StoreError: LocalizedError {
        let status: OSStatus
        var errorDescription: String? { "无法安全保存登录状态，请检查设备钥匙串后重试。" }
    }
}
