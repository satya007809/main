import SwiftUI

@main
struct BharatiDeskApp: App {
    @State private var session = AppSession()
    @State private var offline = OfflineStore.shared
    @Environment(\.scenePhase) private var phase

    var body: some Scene {
        WindowGroup {
            Group {
                if !session.isSignedIn {
                    LoginView()
                } else if session.isLocked {
                    LockView()
                } else {
                    DashboardView()
                }
            }
            .environment(session)
            .environment(offline)
            .tint(Theme.navy)
            .task { if session.isSignedIn { await session.loadUser(); await offline.sync() } }
            .onChange(of: phase) { _, new in
                switch new {
                case .background: session.lockIfNeeded()
                case .active: Task { await offline.sync() }
                default: break
                }
            }
        }
    }
}

enum Theme {
    static let navy = Color(red: 0.075, green: 0.231, blue: 0.427)
    static let gold = Color(red: 0.788, green: 0.592, blue: 0.180)
    static let paper = Color(.secondarySystemBackground)

    static func statusColor(_ status: String) -> Color {
        switch status {
        case "processed", "completed", "done", "report_ready", "available", "established", "verified_from_supplied_record": .green
        case "partial", "duplicate", "pending_verification", "analysed", "partly_established", "pending", "minor": .orange
        case "unreadable", "password_protected", "corrupted", "unsupported", "error", "failed", "missing", "material",
             "not_established": .red
        case "scanning", "analysing", "running", "queued", "processing": .blue
        default: .secondary
        }
    }
}

struct LockView: View {
    @Environment(AppSession.self) private var session
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "lock.shield").font(.system(size: 56)).foregroundStyle(Theme.navy)
            Text("Bharati Investigation Desk is locked").font(.headline)
            Button("Unlock") { Task { await session.unlock() } }.buttonStyle(.borderedProminent)
        }
        .task { await session.unlock() }
    }
}
