import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

@MainActor
@Observable
final class CaseModel {
    let caseId: String
    var record: CaseRecord?
    var documents: [CaseDocument] = []
    var notes: [CaseNote] = []
    var analyses: [AnalysisRun] = []
    var latest: AnalysisRun?
    var reports: [ReportVersion] = []
    var error: String?
    let tracker = JobTracker()

    init(caseId: String, initial: CaseRecord?) { self.caseId = caseId; record = initial }

    private var store: OfflineStore { OfflineStore.shared }
    private func key(_ s: String) -> String { "case_\(caseId)_\(s).json" }

    func load() async {
        do {
            async let rec: CaseRecord = APIClient.shared.request("GET", "cases/\(caseId)")
            async let docs: [CaseDocument] = APIClient.shared.request("GET", "cases/\(caseId)/documents")
            async let ns: [CaseNote] = APIClient.shared.request("GET", "cases/\(caseId)/notes")
            async let runs: [AnalysisRun] = APIClient.shared.request("GET", "cases/\(caseId)/analyses")
            async let reps: [ReportVersion] = APIClient.shared.request("GET", "cases/\(caseId)/reports")
            async let jobs: [Job] = APIClient.shared.request("GET", "cases/\(caseId)/jobs")
            record = try await rec; documents = try await docs; notes = try await ns
            analyses = try await runs; reports = try await reps
            if let done = analyses.first(where: { $0.status == "completed" }) {
                latest = try await APIClient.shared.request("GET", "analyses/\(done.id)")
            }
            if let active = try await jobs.first(where: \.isActive), tracker.job?.id != active.id {
                track(active)
            }
            error = nil
            store.cache(record, as: key("record")); store.cache(documents, as: key("docs"))
            store.cache(notes, as: key("notes")); store.cache(latest, as: key("analysis"))
            store.cache(reports, as: key("reports"))
        } catch {
            record = (store.load(key("record")) as CaseRecord?) ?? record
            documents = store.load(key("docs")) ?? documents
            notes = store.load(key("notes")) ?? notes
            latest = (store.load(key("analysis")) as AnalysisRun?) ?? latest
            reports = store.load(key("reports")) ?? reports
            self.error = (error as? APIError)?.isOffline == true ? nil : error.localizedDescription
        }
    }

    func start(_ path: String, body: (any Encodable)? = nil) async {
        do {
            let job: Job = try await APIClient.shared.request("POST", path, body: body)
            track(job)
        } catch { self.error = error.localizedDescription }
    }

    func track(_ job: Job) {
        tracker.track(job) { [weak self] _ in
            guard let self else { return }
            Task { await self.load() }
        }
    }

    func document(ref: String) -> CaseDocument? { documents.first { $0.ref == ref } }
    func note(ref: String) -> CaseNote? { notes.first { $0.ref == ref } }
}

@MainActor
struct CaseDetailView: View {
    @Environment(OfflineStore.self) private var offline
    @State private var model: CaseModel
    @State private var showEdit = false
    @State private var showFileImporter = false
    @State private var photoItems: [PhotosPickerItem] = []

    init(caseId: String, initial: CaseRecord?) { _model = State(initialValue: CaseModel(caseId: caseId, initial: initial)) }

    var body: some View {
        List {
            if let c = model.record { header(c) }
            if let job = model.tracker.job, job.isActive || job.status == "failed" {
                Section { JobProgressCard(job: job) }.listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
            }
            ErrorBanner(message: model.error)
            workflow
            Section("Evidence") {
                PhotosPicker(selection: $photoItems, maxSelectionCount: 20, matching: .images) {
                    Label("Add photographs", systemImage: "photo.on.rectangle.angled")
                }
                Button { showFileImporter = true } label: { Label("Add documents (PDF, Word, Excel…)", systemImage: "doc.badge.plus") }
                let pending = offline.uploadsPending(for: model.caseId).count + offline.notesPending(for: model.caseId).count
                if pending > 0 { Label("\(pending) item(s) waiting to sync", systemImage: "arrow.triangle.2.circlepath").foregroundStyle(.orange) }
            }
            Section {
                NavigationLink { AuditView(caseId: model.caseId) } label: { Label("Audit trail", systemImage: "list.bullet.clipboard") }
            }
        }
        .navigationTitle(model.record?.title ?? "Case")
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .top) { OfflineBanner() }
        .refreshable { await model.load() }
        .task { await model.load() }
        .onDisappear { model.tracker.stop() }
        .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Edit") { showEdit = true }.disabled(model.record == nil) } }
        .sheet(isPresented: $showEdit) {
            if let c = model.record { EditCaseView(record: c) { updated in model.record = updated; showEdit = false } }
        }
        .navigationDestination(for: SourceLink.self) { link in SourceDestination(model: model, link: link) }
        .onChange(of: photoItems) { _, items in Task { await importPhotos(items) } }
        .fileImporter(isPresented: $showFileImporter, allowedContentTypes: [.pdf, .image, .data, .spreadsheet, .text, .zip],
                      allowsMultipleSelection: true) { result in
            if case .success(let urls) = result { Task { await importFiles(urls) } }
        }
    }

    @ViewBuilder private func header(_ c: CaseRecord) -> some View {
        Section {
            HStack { Text(c.categoryTitle).font(.headline); Spacer(); StatusBadge(status: c.status) }
            LabeledText(label: "Claim no.", value: c.claimNumber)
            LabeledText(label: "Policy no.", value: c.policyNumber)
            LabeledText(label: "Vehicle", value: c.vehicleRegistration)
            LabeledText(label: "Insurer", value: c.insurerName)
            LabeledText(label: "Reference", value: c.investigationReference)
            if !c.additionalAspects.isEmpty { LabeledText(label: "Aspects", value: c.additionalAspects.map(\.humanized).joined(separator: ", ")) }
        }
    }

    private var workflow: some View {
        Section("Investigation workflow") {
            let c = model.record
            let busy = model.tracker.job?.isActive == true
            Button { Task { await model.start("cases/\(model.caseId)/scan") } } label: {
                StepRow(n: 1, title: model.documents.isEmpty ? "Scan case folder" : "Rescan folder for new files",
                        detail: c?.sourceLink.isEmpty == false ? (c?.sourceProvider.humanized ?? "") : "Add a folder link via Edit",
                        done: !model.documents.isEmpty)
            }
            .disabled(busy || c?.sourceLink.isEmpty != false)
            NavigationLink { InventoryView(model: model) } label: {
                StepRow(n: 2, title: "Review document inventory", detail: inventoryDetail, done: !model.documents.isEmpty)
            }
            NavigationLink { NotesView(model: model) } label: {
                StepRow(n: 3, title: "Field notes & verification results", detail: "\(model.notes.count) recorded", done: !model.notes.isEmpty)
            }
            Button { Task { await model.start("cases/\(model.caseId)/analyses") } } label: {
                StepRow(n: 4, title: model.analyses.isEmpty ? "Run investigation" : "Rerun investigation with latest evidence",
                        detail: model.latest.map { "Last run #\($0.runNo) · \($0.createdAt.shortDate)" } ?? "Applies the case playbook",
                        done: model.latest != nil)
            }
            .disabled(busy || model.documents.isEmpty)
            NavigationLink { FindingsView(model: model) } label: {
                StepRow(n: 5, title: "Review findings", detail: model.latest?.result?.opinion.verdictTitle ?? "Not yet analysed",
                        done: model.latest != nil)
            }
            .disabled(model.latest == nil)
            NavigationLink { ReportsView(model: model) } label: {
                StepRow(n: 6, title: "Word report", detail: model.reports.first.map { "v\($0.version) · \($0.pageCount) pages" } ?? "Generate, edit, share",
                        done: !model.reports.isEmpty)
            }
        }
    }

    private var inventoryDetail: String {
        let ok = model.documents.filter { ["processed", "partial"].contains($0.status) }.count
        let bad = model.documents.filter { ["unreadable", "password_protected", "corrupted", "unsupported", "error"].contains($0.status) }.count
        return model.documents.isEmpty ? "No documents yet" : "\(ok) readable · \(bad) problem(s)"
    }

    private func importPhotos(_ items: [PhotosPickerItem]) async {
        for (i, item) in items.enumerated() {
            guard let data = try? await item.loadTransferable(type: Data.self) else { continue }
            let ext = item.supportedContentTypes.first?.preferredFilenameExtension ?? "jpg"
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("photo_\(Int(Date().timeIntervalSince1970))_\(i).\(ext)")
            try? data.write(to: url, options: .completeFileProtection)
            _ = try? offline.queueUpload(caseId: model.caseId, from: url, filename: url.lastPathComponent,
                                         mimeType: item.supportedContentTypes.first?.preferredMIMEType ?? "image/jpeg")
            try? FileManager.default.removeItem(at: url)
        }
        photoItems = []
        await offline.sync()
        await model.load()
    }

    private func importFiles(_ urls: [URL]) async {
        for url in urls {
            let ok = url.startAccessingSecurityScopedResource()
            defer { if ok { url.stopAccessingSecurityScopedResource() } }
            let mime = UTType(filenameExtension: url.pathExtension)?.preferredMIMEType ?? "application/octet-stream"
            _ = try? offline.queueUpload(caseId: model.caseId, from: url, filename: url.lastPathComponent, mimeType: mime)
        }
        await offline.sync()
        await model.load()
    }
}

struct StepRow: View {
    let n: Int; let title: String; let detail: String; let done: Bool
    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                Circle().fill(done ? Color.green : Theme.navy.opacity(0.15)).frame(width: 28, height: 28)
                if done { Image(systemName: "checkmark").font(.caption.bold()).foregroundStyle(.white) }
                else { Text("\(n)").font(.caption.bold()).foregroundStyle(Theme.navy) }
            }
            VStack(alignment: .leading) {
                Text(title).foregroundStyle(.primary)
                Text(detail).font(.caption).foregroundStyle(.secondary).lineLimit(1)
            }
        }
    }
}

/// Opens the document page or note a finding cites.
struct SourceDestination: View {
    let model: CaseModel
    let link: SourceLink
    var body: some View {
        if let d = model.document(ref: link.ref) {
            DocumentDetailView(model: model, documentId: d.id, focusPage: link.page)
        } else if let n = model.note(ref: link.ref) {
            List { Section(n.ref + " · " + n.kind.humanized) { Text(n.title).bold(); Text(n.body); LabeledText(label: "Verified by", value: n.verifiedBy); LabeledText(label: "On", value: n.verifiedOn) } }
        } else {
            ContentUnavailableView("Source \(link.ref) not found", systemImage: "questionmark.folder")
        }
    }
}

struct EditCaseView: View {
    let record: CaseRecord
    var onSaved: (CaseRecord) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var input = CaseInput()
    @State private var date = Date()
    @State private var aspects: [Aspect] = []
    @State private var status = ""
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                CaseDetailsSection(input: $input, investigationDate: $date)
                Section("Case type") {
                    Picker("Case type", selection: $input.category) { ForEach(CaseCategory.allCases) { Text($0.title).tag($0.rawValue) } }
                    AspectPicker(all: aspects, category: input.category, selected: $input.additionalAspects)
                }
                Section("Folder link") { TextField("Folder link", text: $input.sourceLink, axis: .vertical).textInputAutocapitalization(.never) }
                ReportOptionsSection(input: $input)
                Section("Case status") {
                    Picker("Status", selection: $status) {
                        Text("No change").tag("")
                        Text("Pending verification").tag("pending_verification")
                        Text("Report ready").tag("report_ready")
                        Text("Completed").tag("completed")
                    }
                }
                ErrorBanner(message: error)
            }
            .navigationTitle("Edit case").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Save") { Task { await save() } } }
            }
            .task {
                input = CaseInput(insuredName: record.insuredName, claimNumber: record.claimNumber, policyNumber: record.policyNumber,
                                  vehicleRegistration: record.vehicleRegistration, insurerName: record.insurerName,
                                  investigationReference: record.investigationReference, investigationDate: record.investigationDate,
                                  category: record.category, additionalAspects: record.additionalAspects, sourceLink: record.sourceLink,
                                  pageLimit: record.pageLimit, includeInvoice: record.includeInvoice,
                                  invoice: Self.invoice(from: record.invoice), notes: record.notes)
                if let d = try? Date(record.investigationDate + "T00:00:00Z", strategy: .iso8601) { date = d }
                aspects = (try? await APIClient.shared.request("GET", "playbooks/aspects")) ?? []
            }
        }
    }

    nonisolated static func invoice(from dict: [String: JSONValue]) -> Invoice {
        guard let data = try? JSONEncoder().encode(dict), let inv = try? JSONDecoder().decode(Invoice.self, from: data) else { return Invoice() }
        return inv
    }

    private func save() async {
        input.investigationDate = date.formatted(.iso8601.year().month().day())
        struct Patch: Encodable { let base: CaseInput; let status: String?
            func encode(to encoder: Encoder) throws {
                try base.encode(to: encoder)
                if let status { var c = encoder.container(keyedBy: K.self); try c.encode(status, forKey: .status) }
            }
            enum K: String, CodingKey { case status }
        }
        do {
            let updated: CaseRecord = try await APIClient.shared.request("PATCH", "cases/\(record.id)",
                                                                         body: Patch(base: input, status: status.isEmpty ? nil : status))
            onSaved(updated)
        } catch { self.error = error.localizedDescription }
    }
}

struct AuditView: View {
    let caseId: String
    @State private var entries: [AuditEntry] = []
    var body: some View {
        List(entries, id: \.self) { e in
            VStack(alignment: .leading) { Text(e.action.replacingOccurrences(of: ".", with: " › ").humanized); Text(e.at).font(.caption).foregroundStyle(.secondary) }
        }
        .navigationTitle("Audit trail")
        .task { entries = (try? await APIClient.shared.request("GET", "cases/\(caseId)/audit")) ?? [] }
    }
}
