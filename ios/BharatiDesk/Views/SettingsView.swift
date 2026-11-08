import SwiftUI
import UniformTypeIdentifiers

@MainActor
struct SettingsView: View {
    @Environment(AppSession.self) private var session
    @Environment(\.dismiss) private var dismiss
    @AppStorage("serverURL") private var serverURL = "https://api.example.com"
    @State private var connectors: [Connector] = []
    @State private var profile: [String: String] = [:]
    @State private var auth = WebAuthenticator()
    @State private var error: String?
    @State private var saved = false
    @State private var lock = false

    private let profileFields: [(String, String)] = [
        ("name", "Investigator name"), ("designation", "Designation"), ("firm", "Firm name"),
        ("licence_number", "Licence / registration no."), ("address", "Address"), ("phone", "Phone"),
        ("email", "Email"), ("gstin", "GSTIN"), ("bank_details", "Bank details (for invoice)"), ("place", "Place")]

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    ForEach(profileFields.indices, id: \.self) { i in
                        let (key, label) = profileFields[i]
                        TextField(label, text: Binding(get: { profile[key] ?? "" }, set: { profile[key] = $0 }), axis: .vertical)
                    }
                    Button(saved ? "Saved" : "Save profile") { Task { await saveProfile() } }
                } header: { Text("Investigator details") } footer: {
                    Text("Printed on reports and invoices exactly as entered. The AI never fills these in.")
                }

                Section {
                    ForEach(connectors) { c in
                        HStack {
                            VStack(alignment: .leading) {
                                Text(c.provider == "google_drive" ? "Google Drive" : c.provider == "onedrive" ? "OneDrive" : c.provider.humanized)
                                if c.connected { Text(c.accountEmail).font(.caption).foregroundStyle(.secondary) }
                                else if !c.configured { Text("Not configured on server").font(.caption).foregroundStyle(.secondary) }
                            }
                            Spacer()
                            if c.provider != "local" {
                                if c.connected {
                                    Button("Disconnect", role: .destructive) { Task { await disconnect(c.provider) } }
                                } else {
                                    Button("Connect") { Task { await connect(c.provider) } }.disabled(!c.configured)
                                }
                            }
                        }
                    }
                } header: { Text("Cloud accounts") } footer: {
                    Text("Read-only access to folders you open, plus permission to upload reports you choose to save back. Disconnecting revokes the app's access.")
                }

                Section("Security") {
                    Toggle("Require Face ID / passcode", isOn: $lock).onChange(of: lock) { _, v in session.appLockEnabled = v }
                    TextField("Server URL", text: $serverURL).textInputAutocapitalization(.never).keyboardType(.URL)
                }

                if session.user?.isAdmin == true {
                    Section("Administration") {
                        NavigationLink { PlaybookListView() } label: { Label("Investigation playbooks", systemImage: "books.vertical") }
                        NavigationLink { TemplatesView() } label: { Label("Reference report formats", systemImage: "doc.richtext") }
                    }
                }

                ErrorBanner(message: error)
                Section {
                    Button("Sign out", role: .destructive) { Task { await session.signOut(); dismiss() } }
                } footer: {
                    Text("Signing out removes all cached case data from this iPhone.")
                }
            }
            .navigationTitle("Settings")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
            .task {
                lock = session.appLockEnabled
                // .convertFromSnakeCase also rewrites dictionary keys ("licence_number" -> "licenceNumber"); undo that
                // so the fields below (keyed by the server's snake_case names) find their values.
                profile = Dictionary((session.user?.investigatorProfile ?? [:]).map { ($0.key.snakeCased, $0.value) },
                                     uniquingKeysWith: { a, _ in a })
                connectors = (try? await APIClient.shared.request("GET", "connectors")) ?? []
            }
        }
    }

    private func saveProfile() async {
        struct Body: Encodable { let investigatorProfile: [String: String] }
        do {
            let u: UserProfile = try await APIClient.shared.request("PUT", "auth/me", body: Body(investigatorProfile: profile))
            session.user = u; saved = true
        } catch { self.error = error.localizedDescription }
    }

    private func connect(_ p: String) async {
        do { try await auth.connect(provider: p) } catch { self.error = error.localizedDescription }
        connectors = (try? await APIClient.shared.request("GET", "connectors")) ?? connectors
    }

    private func disconnect(_ p: String) async {
        _ = try? await APIClient.shared.raw("DELETE", "connectors/\(p)")
        connectors = (try? await APIClient.shared.request("GET", "connectors")) ?? connectors
    }
}

// MARK: - Playbook administration (no code changes needed to improve investigation logic)

struct PlaybookListView: View {
    @State private var books: [Playbook] = []
    var body: some View {
        List(books) { b in
            NavigationLink { PlaybookEditorView(playbook: b) } label: {
                VStack(alignment: .leading) {
                    Text(b.name)
                    Text("\(b.kind.humanized) · active v\(b.activeVersion)").font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle("Playbooks")
        .task { books = (try? await APIClient.shared.request("GET", "playbooks")) ?? [] }
    }
}

struct PlaybookEditorView: View {
    let playbook: Playbook
    @State private var versions: [PlaybookVersion] = []
    @State private var text = ""
    @State private var note = ""
    @State private var active = 0
    @State private var error: String?
    @State private var saved: String?

    var body: some View {
        Form {
            Section {
                TextEditor(text: $text).font(.system(.footnote, design: .monospaced)).frame(minHeight: 380)
                    .autocorrectionDisabled().textInputAutocapitalization(.never)
            } header: { Text("YAML – edit checks, questions and report instructions") } footer: {
                Text("Saving creates a new version. Analyses record the version they used, so earlier reports stay traceable.")
            }
            Section {
                TextField("What changed? (e.g. added key-custody question)", text: $note)
                Button("Save as new version") { Task { await save() } }.disabled(text.isEmpty)
            }
            ErrorBanner(message: error)
            if let saved { Label(saved, systemImage: "checkmark.circle").foregroundStyle(.green) }
            Section("History") {
                ForEach(versions) { v in
                    HStack {
                        VStack(alignment: .leading) {
                            Text("v\(v.version)\(v.version == active ? " (active)" : "")").bold()
                            Text(v.changeNote.isEmpty ? v.createdAt.shortDate : "\(v.changeNote) · \(v.createdAt.shortDate)").font(.caption)
                        }
                        Spacer()
                        if v.version != active { Button("Activate") { Task { await activate(v.version) } }.buttonStyle(.borderless) }
                        Button("Load") { text = v.contentYaml }.buttonStyle(.borderless)
                    }
                }
            }
        }
        .navigationTitle(playbook.name)
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func load() async {
        versions = (try? await APIClient.shared.request("GET", "playbooks/\(playbook.key)/versions")) ?? []
        let books: [Playbook] = (try? await APIClient.shared.request("GET", "playbooks")) ?? []
        active = books.first { $0.key == playbook.key }?.activeVersion ?? playbook.activeVersion
        if text.isEmpty { text = versions.first { $0.version == active }?.contentYaml ?? versions.first?.contentYaml ?? "" }
    }

    private func save() async {
        struct Body: Encodable { let contentYaml: String; let changeNote: String; let activate: Bool }
        do {
            let v: PlaybookVersion = try await APIClient.shared.request("POST", "playbooks/\(playbook.key)/versions",
                                                                        body: Body(contentYaml: text, changeNote: note, activate: true))
            saved = "Saved and activated v\(v.version)"; error = nil; note = ""
            await load()
        } catch { self.error = error.localizedDescription }
    }

    private func activate(_ v: Int) async {
        do { let _: Playbook = try await APIClient.shared.request("POST", "playbooks/\(playbook.key)/activate/\(v)"); await load() }
        catch { self.error = error.localizedDescription }
    }
}

struct TemplatesView: View {
    struct Template: Codable, Identifiable { let id: String; let category: String; let filename: String; let active: Bool }
    @State private var templates: [Template] = []
    @State private var category = "own_damage"
    @State private var importing = false
    @State private var error: String?

    var body: some View {
        Form {
            Section {
                Picker("Category", selection: $category) {
                    Text("All categories (default)").tag("default")
                    ForEach(CaseCategory.allCases) { Text($0.title).tag($0.rawValue) }
                }
                Button("Upload reference .docx (e.g. OD_report.docx)") { importing = true }
            } footer: {
                Text("The uploaded report's letterhead, header/footer, margins and styles become the base for new reports in this category. Its text is not reused.")
            }
            ErrorBanner(message: error)
            Section("Uploaded") {
                ForEach(templates) { t in
                    HStack { Text(t.filename); Spacer(); Text(t.category.humanized).font(.caption); if t.active { Image(systemName: "checkmark").foregroundStyle(.green) } }
                }
            }
        }
        .navigationTitle("Report formats")
        .task { await load() }
        .fileImporter(isPresented: $importing, allowedContentTypes: [UTType(filenameExtension: "docx") ?? .data]) { result in
            if case .success(let url) = result { Task { await upload(url) } }
        }
    }

    private func load() async { templates = (try? await APIClient.shared.request("GET", "templates")) ?? [] }

    private func upload(_ url: URL) async {
        let ok = url.startAccessingSecurityScopedResource(); defer { if ok { url.stopAccessingSecurityScopedResource() } }
        do {
            let boundary = "BID-\(UUID().uuidString)"
            var d = Data()
            d.append("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"\(url.lastPathComponent)\"\r\nContent-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n".data(using: .utf8)!)
            d.append(try Data(contentsOf: url))
            d.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
            _ = try await APIClient.shared.raw("POST", "templates/\(category)", multipart: (d, boundary))
            await load()
        } catch { self.error = error.localizedDescription }
    }
}
