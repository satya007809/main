import Foundation
import Security

/// Session tokens are stored only in the Keychain, readable only while the device is unlocked, never synced.
enum Keychain {
    enum Key: String { case accessToken = "bid.access", refreshToken = "bid.refresh" }

    static func set(_ value: String, for key: Key) {
        let base: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                   kSecAttrAccount as String: key.rawValue]
        SecItemDelete(base as CFDictionary)
        var add = base
        add[kSecValueData as String] = Data(value.utf8)
        add[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        SecItemAdd(add as CFDictionary, nil)
    }

    static func get(_ key: Key) -> String? {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                kSecAttrAccount as String: key.rawValue,
                                kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }

    static func store(_ pair: TokenPair) {
        set(pair.accessToken, for: .accessToken)
        set(pair.refreshToken, for: .refreshToken)
    }

    static func clear() {
        for k in [Key.accessToken, .refreshToken] {
            SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrAccount as String: k.rawValue] as CFDictionary)
        }
    }
}
