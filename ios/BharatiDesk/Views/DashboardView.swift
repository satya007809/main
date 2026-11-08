import SwiftUI

enum CaseGroup: String, CaseIterable, Identifiable {
    case all, new, processing, reportsReady = "reports_ready", pendingVerification = "pending_verification", completed
    var id: String { rawValue }
    var title: String {
        switch self {
        case .all: "All"
        case .new: "New"
        case .processing: "Processing"
        case .reportsReady: "Reports Ready"
        case .pendingVerification: "Pending Verification"
        case .completed: "Completed"
        }
    }
    var icon: String {
        switch self {
        case .all: "tray.full"
        case .new: "sparkles"
        case .processing: "gearshape.2"
        case .reportsReady: "doc.richtext"
        case .pendingVerification: "hourglass"
        case .completed: "checkmark.seal"
        }
    }
}

struct DashboardView: View {
    @Environment(OfflineStore.self) private var offline
    @State private var cases: [CaseRecord] = []
    @State private var counts: [String: Int] = [:]
    @State private var group: CaseGroup = .all
    @State private var search = ""
    @State private var showNew = false
    @State private var showSettings = false
    @State private var error: String?
    @State private var path = NavigationPath()

    var body: some View {
        NavigationStack(path: $path) {
            List {
                Section {
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                        ForEach(CaseGroup.allCases.dropFirst()) { g in
                            Button { group = (group == g ? .all : g) } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Label(g.title, systemImage: g.icon).font(.caption.weight(.semibold))
                                    Text("\(counts[g.rawValue] ?? 0)").font(.title2.bold())
                                }
                                .frame(maxWidth: .infinity, alignment: .leading).padding(10)
                                .background(group == g ? Theme.navy.opacity(0.15) : Theme.paper,
                                            in: RoundedRectangle(cornerRadius: 12))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    Button { showNew = true } label: {
                        Label("New Investigation", systemImage: "plus.circle.fill").font(.headline)
                            .frame(maxWidth: .infinity).padding(.vertical, 6)
                    }
                    .buttonStyle(.borderedProminent)
                }
                .listRowSeparator(.hidden)
                ErrorBanner(message: error)
                Section(group == .all ? "Recent cases" : group.title) {
                    if cases.isEmpty {
                        ContentUnavailableView("No cases", systemImage: "folder", description: Text("Start a new investigation."))
                    }
                    ForEach(cases) { c in
                        NavigationLink(value: c) { CaseRow(c: c) }
                    }
                }
            }
            .safeAreaInset(edge: .top) { OfflineBanner() }
            .navigationTitle("Bharati Desk")
            .searchable(text: $search, prompt: "Claim no., vehicle no., insured, insurer")
            .onSubmit(of: .search) { Task { await load() } }
            .onChange(of: search) { _, v in if v.isEmpty { Task { await load() } } }
            .onChange(of: group) { _, _ in Task { await load() } }
            .refreshable { await load() }
            .task { await load() }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showSettings = true } label: { Image(systemName: "gearshape") }
                }
            }
            .navigationDestination(for: CaseRecord.self) { c in CaseDetailView(caseId: c.id, initial: c) }
            .sheet(isPresented: $showNew) {
                NewCaseView { created in
                    showNew = false
                    Task { await load() }
                    path.append(created)
                }
            }
            .sheet(isPresented: $showSettings) { SettingsView() }
        }
    }

    private func load() async {
        var q: [URLQueryItem] = []
        if group != .all { q.append(.init(name: "group", value: group.rawValue)) }
        if !search.isEmpty { q.append(.init(name: "q", value: search)) }
        let cacheName = "cases_\(group.rawValue).json"
        do {
            async let list: [CaseRecord] = APIClient.shared.request("GET", "cases", query: q)
            async let dash: Dashboard = APIClient.shared.request("GET", "dashboard")
            cases = try await list
            counts = try await dash.groups
            error = nil
            if search.isEmpty { offline.cache(cases, as: cacheName); offline.cache(counts, as: "dashboard.json") }
        } catch {
            if let cached: [CaseRecord] = offline.load(cacheName) {
                cases = search.isEmpty ? cached : cached.filter {
                    [$0.claimNumber, $0.vehicleRegistration, $0.insuredName, $0.insurerName]
                        .joined(separator: " ").localizedCaseInsensitiveContains(search)
                }
            }
            counts = offline.load("dashboard.json") ?? counts
            self.error = (error as? APIError)?.isOffline == true ? nil : error.localizedDescription
        }
    }
}

struct CaseRow: View {
    let c: CaseRecord
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(c.title).font(.headline).lineLimit(1)
                Spacer()
                StatusBadge(status: c.status)
            }
            Text([c.claimNumber, c.vehicleRegistration].filter { !$0.isEmpty }.joined(separator: " · "))
                .font(.subheadline.monospaced()).foregroundStyle(.secondary)
            HStack {
                Text(c.categoryTitle)
                if !c.insurerName.isEmpty { Text("· \(c.insurerName)") }
                Spacer()
                Text(c.updatedAt.shortDate)
            }
            .font(.caption).foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
    }
}
