import Foundation

enum APIError: LocalizedError {
    case notSignedIn, offline, server(Int, String), decoding(String)
    var errorDescription: String? {
        switch self {
        case .notSignedIn: "Please sign in again."
        case .offline: "No internet connection. Your changes are saved and will sync automatically."
        case .server(_, let msg): msg
        case .decoding(let msg): "Unexpected response from server (\(msg))."
        }
    }
    var isOffline: Bool { if case .offline = self { return true }; return false }
}

/// Talks to the Bharati backend. Holds no provider or AI credentials — only the user's own session tokens,
/// which live in the Keychain.
actor APIClient {
    static let shared = APIClient()

    private let session: URLSession
    private let decoder: JSONDecoder = {
        let d = JSONDecoder(); d.keyDecodingStrategy = .convertFromSnakeCase; return d
    }()
    private let encoder: JSONEncoder = {
        let e = JSONEncoder(); e.keyEncodingStrategy = .convertToSnakeCase; return e
    }()
    private var refreshTask: Task<Void, Error>?

    init() {
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 60
        cfg.timeoutIntervalForResource = 600
        cfg.waitsForConnectivity = false
        cfg.urlCache = nil  // never cache confidential responses on disk
        cfg.requestCachePolicy = .reloadIgnoringLocalCacheData
        session = URLSession(configuration: cfg)
    }

    static var baseURL: URL {
        let s = UserDefaults.standard.string(forKey: "serverURL") ?? "https://api.example.com"
        return URL(string: s.trimmingCharacters(in: .whitespaces))!.appendingPathComponent("api/v1")
    }

    // MARK: - core request

    func request<T: Decodable>(_ method: String, _ path: String, body: (any Encodable)? = nil,
                               query: [URLQueryItem] = [], auth: Bool = true) async throws -> T {
        let data = try await raw(method, path, body: body, query: query, auth: auth)
        if T.self == EmptyResponse.self { return EmptyResponse() as! T }
        do { return try decoder.decode(T.self, from: data) }
        catch { throw APIError.decoding(String(describing: error).prefix(200).description) }
    }

    func raw(_ method: String, _ path: String, body: (any Encodable)? = nil, query: [URLQueryItem] = [],
             auth: Bool = true, multipart: (Data, String)? = nil, retried: Bool = false) async throws -> Data {
        var comps = URLComponents(url: Self.baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty { comps.queryItems = query }
        var req = URLRequest(url: comps.url!)
        req.httpMethod = method
        if let body {
            req.httpBody = try encoder.encode(AnyEncodable(body))
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if let mp = multipart {
            req.httpBody = mp.0
            req.setValue("multipart/form-data; boundary=\(mp.1)", forHTTPHeaderField: "Content-Type")
        }
        if auth {
            guard let token = Keychain.get(.accessToken) else { throw APIError.notSignedIn }
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, resp): (Data, URLResponse)
        do { (data, resp) = try await session.data(for: req) }
        catch let e as URLError where [.notConnectedToInternet, .networkConnectionLost, .timedOut,
                                       .cannotConnectToHost, .dataNotAllowed].contains(e.code) {
            throw APIError.offline
        }
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code == 401 && auth && !retried {
            try await refreshTokens()
            return try await raw(method, path, body: body, query: query, auth: auth, multipart: multipart, retried: true)
        }
        guard (200..<300).contains(code) else {
            let detail = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"]
            let msg = (detail as? String) ?? (detail.map { "\($0)" } ?? HTTPURLResponse.localizedString(forStatusCode: code))
            if code == 401 { throw APIError.notSignedIn }
            throw APIError.server(code, msg)
        }
        return data
    }

    private func refreshTokens() async throws {
        if let t = refreshTask { return try await t.value }
        let task = Task {
            defer { refreshTask = nil }
            guard let rt = Keychain.get(.refreshToken) else { throw APIError.notSignedIn }
            let pair: TokenPair = try await request("POST", "auth/refresh", body: ["refresh_token": rt], auth: false)
            Keychain.store(pair)
        }
        refreshTask = task
        try await task.value
    }

    // MARK: - auth

    func login(email: String, password: String) async throws {
        let device = "iPhone"
        let pair: TokenPair = try await request("POST", "auth/login",
                                                body: ["email": email, "password": password, "device": device], auth: false)
        Keychain.store(pair)
    }

    func register(email: String, password: String, name: String) async throws {
        let pair: TokenPair = try await request("POST", "auth/register",
                                                body: ["email": email, "password": password, "full_name": name], auth: false)
        Keychain.store(pair)
    }

    func logout() async {
        if let rt = Keychain.get(.refreshToken) {
            _ = try? await raw("POST", "auth/logout", body: ["refresh_token": rt], auth: false)
        }
        Keychain.clear()
    }

    // MARK: - multipart upload

    func upload(caseId: String, fileURL: URL, filename: String, mimeType: String, clientUUID: String) async throws -> CaseDocument {
        let boundary = "BID-\(UUID().uuidString)"
        var d = Data()
        func field(_ name: String, _ value: String) {
            d.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(name)\"\r\n\r\n\(value)\r\n".data(using: .utf8)!)
        }
        field("client_uuid", clientUUID)
        d.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\nContent-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        d.append(try Data(contentsOf: fileURL))
        d.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        let data = try await raw("POST", "cases/\(caseId)/documents", multipart: (d, boundary))
        return try decoder.decode(CaseDocument.self, from: data)
    }

    /// Downloads a file into the app's protected caches and returns its URL.
    func download(path: String, query: [URLQueryItem], filename: String) async throws -> URL {
        let data = try await raw("GET", path, query: query)
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("Reports", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let url = dir.appendingPathComponent(filename)
        try data.write(to: url, options: [.atomic, .completeFileProtection])
        return url
    }
}

struct EmptyResponse: Decodable {}

private struct AnyEncodable: Encodable {
    let value: any Encodable
    init(_ v: any Encodable) { value = v }
    func encode(to encoder: Encoder) throws { try value.encode(to: encoder) }
}
