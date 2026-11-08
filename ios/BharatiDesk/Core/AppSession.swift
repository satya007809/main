import AuthenticationServices
import LocalAuthentication
import Observation
import SwiftUI

@MainActor
@Observable
final class AppSession {
    var user: UserProfile?
    var isSignedIn = Keychain.get(.refreshToken) != nil
    var isLocked = false
    var lastError: String?
    /// "api" (server calls Claude) or "claude_code" (investigation runs in Claude Code on the user's plan)
    var aiMode: String = UserDefaults.standard.string(forKey: "aiMode") ?? "api"
    var usesClaudeCode: Bool { aiMode == "claude_code" }

    var appLockEnabled: Bool {
        get { UserDefaults.standard.bool(forKey: "appLock") }
        set { UserDefaults.standard.set(newValue, forKey: "appLock") }
    }

    func loadUser() async {
        do {
            user = try await APIClient.shared.request("GET", "auth/me")
            OfflineStore.shared.cache(user, as: "me.json")
            if let cfg: AppConfig = try? await APIClient.shared.request("GET", "config") {
                aiMode = cfg.aiMode
                UserDefaults.standard.set(cfg.aiMode, forKey: "aiMode")
            }
        } catch APIError.notSignedIn {
            isSignedIn = false
        } catch {
            user = OfflineStore.shared.load("me.json")
        }
    }

    func signIn(email: String, password: String, register: Bool, name: String) async throws {
        if register { try await APIClient.shared.register(email: email, password: password, name: name) }
        else { try await APIClient.shared.login(email: email, password: password) }
        isSignedIn = true
        await loadUser()
    }

    func signOut() async {
        await APIClient.shared.logout()
        OfflineStore.shared.wipe()
        user = nil
        isSignedIn = false
    }

    func lockIfNeeded() { if appLockEnabled && isSignedIn { isLocked = true } }

    func unlock() async {
        let ctx = LAContext()
        var err: NSError?
        guard ctx.canEvaluatePolicy(.deviceOwnerAuthentication, error: &err) else { isLocked = false; return }
        if (try? await ctx.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: "Unlock Bharati Desk")) == true {
            isLocked = false
        }
    }
}

/// Runs the cloud OAuth flow in ASWebAuthenticationSession. The backend completes the code exchange and keeps
/// the provider tokens; the app only receives "bharatidesk://oauth-complete?status=ok".
@MainActor
final class WebAuthenticator: NSObject, ASWebAuthenticationPresentationContextProviding {
    private var session: ASWebAuthenticationSession?

    func connect(provider: String) async throws {
        let resp: AuthorizeResponse = try await APIClient.shared.request("POST", "connectors/\(provider)/authorize")
        guard let url = URL(string: resp.authorizeUrl) else { throw APIError.server(0, "Invalid authorisation URL") }
        let callback: URL = try await withCheckedThrowingContinuation { cont in
            let s = ASWebAuthenticationSession(url: url, callbackURLScheme: resp.callbackScheme) { url, error in
                if let url { cont.resume(returning: url) }
                else { cont.resume(throwing: error ?? APIError.server(0, "Cancelled")) }
            }
            s.presentationContextProvider = self
            s.prefersEphemeralWebBrowserSession = false
            session = s
            s.start()
        }
        let items = URLComponents(url: callback, resolvingAgainstBaseURL: false)?.queryItems ?? []
        if items.first(where: { $0.name == "status" })?.value != "ok" {
            throw APIError.server(0, items.first(where: { $0.name == "message" })?.value ?? "Connection failed")
        }
    }

    nonisolated func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        MainActor.assumeIsolated {
            UIApplication.shared.connectedScenes.compactMap { ($0 as? UIWindowScene)?.keyWindow }.first ?? ASPresentationAnchor()
        }
    }
}

/// Polls a background job until it finishes. Jobs run on the server, so closing the app does not stop them;
/// on reopen the case screen resumes polling any active job.
@MainActor
@Observable
final class JobTracker {
    var job: Job?
    var finished: ((Job) -> Void)?
    private var task: Task<Void, Never>?

    func track(_ job: Job, onFinish: @escaping (Job) -> Void) {
        self.job = job
        finished = onFinish
        task?.cancel()
        task = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(2))
                guard let self, let id = self.job?.id else { return }
                if let j: Job = try? await APIClient.shared.request("GET", "jobs/\(id)") {
                    self.job = j
                    if !j.isActive { self.finished?(j); return }
                }
            }
        }
    }

    func stop() { task?.cancel() }
}
