import SwiftUI

@MainActor
struct InventoryView: View {
    let model: CaseModel
    @State private var filter = "all"
    @State private var summary: InventorySummary?

    private let filters = [("all", "All"), ("processed", "Processed"), ("problems", "Unreadable / problems"),
                           ("pending", "Pending"), ("duplicate", "Duplicates")]

    var body: some View {
        List {
            if let s = summary {
                Section {
                    HStack {
                        stat("Processed", s.processed, .green)
                        stat("Problems", s.unreadable, .red)
                        stat("Pending", s.pending, .blue)
                        stat("Duplicates", s.duplicates, .orange)
                    }
                }
                if !s.missingDocuments.isEmpty {
                    Section("Missing documents (per playbook)") {
                        ForEach(s.missingDocuments, id: \.itemId) { m in
                            Label(m.label, systemImage: "doc.questionmark").foregroundStyle(.red)
                        }
                    }
                }
            }
            Section {
                Picker("Show", selection: $filter) { ForEach(filters.indices, id: \.self) { i in Text(filters[i].1).tag(filters[i].0) } }
                    .pickerStyle(.menu)
            }
            Section("\(shown.count) file(s)") {
                ForEach(shown) { d in
                    NavigationLink { DocumentDetailView(model: model, documentId: d.id, focusPage: 0) } label: { DocumentRow(d: d) }
                }
            }
        }
        .navigationTitle("Document inventory")
        .refreshable { await reload() }
        .task { await reload() }
    }

    private func reload() async {
        await model.load()
        summary = try? await APIClient.shared.request("GET", "cases/\(model.caseId)/inventory")
    }

    private var shown: [CaseDocument] {
        model.documents.filter { d in
            switch filter {
            case "processed": ["processed", "partial"].contains(d.status)
            case "problems": ["unreadable", "password_protected", "corrupted", "unsupported", "error", "partial"].contains(d.status)
            case "pending": ["pending", "processing"].contains(d.status)
            case "duplicate": d.status == "duplicate"
            default: true
            }
        }
    }

    private func stat(_ t: String, _ n: Int, _ c: Color) -> some View {
        VStack { Text("\(n)").font(.title3.bold()).foregroundStyle(c); Text(t).font(.caption2) }.frame(maxWidth: .infinity)
    }
}

struct DocumentRow: View {
    let d: CaseDocument
    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(d.ref).font(.caption.monospaced().bold()).foregroundStyle(Theme.navy)
                Text(d.originalFilename).lineLimit(1)
                Spacer()
                StatusBadge(status: d.status)
            }
            HStack {
                Text(d.docType.humanized)
                if d.pageCount > 0 { Text("· \(d.pageCount) p.") }
                if !d.languages.isEmpty { Text("· \(d.languages.joined(separator: ", "))") }
            }
            .font(.caption).foregroundStyle(.secondary)
            if !d.sourcePath.isEmpty { Text(d.sourcePath).font(.caption2).foregroundStyle(.tertiary).lineLimit(1) }
            if !d.statusDetail.isEmpty { Text(d.statusDetail).font(.caption2).foregroundStyle(Theme.statusColor(d.status)) }
        }
    }
}

struct DocumentDetailView: View {
    let model: CaseModel
    let documentId: String
    let focusPage: Int
    @State private var doc: CaseDocument?
    @State private var showOriginal = false
    @State private var editingPage: DocumentPage?
    @State private var docType = ""
    @State private var preview: FileItem?
    @State private var error: String?

    private let types = ["policy_schedule", "policy_wording", "previous_policy", "claim_form", "fir", "police_report",
                         "mvi_report", "postmortem_report", "death_certificate", "mlc", "discharge_summary", "medical_record",
                         "driving_licence", "registration_certificate", "permit", "fitness_certificate", "fastag_statement",
                         "google_timeline", "bank_statement", "salary_slip", "attendance_record", "invoice", "towing_bill",
                         "garage_job_card", "survey_report", "fire_report", "photograph", "whatsapp_export",
                         "witness_statement", "identity_document", "cctv_record", "unknown"]

    var body: some View {
        List {
            if let d = doc {
                Section {
                    LabeledText(label: "Reference", value: d.ref)
                    LabeledText(label: "File", value: d.originalFilename)
                    LabeledText(label: "Folder", value: d.sourcePath)
                    LabeledText(label: "Modified", value: d.sourceModifiedAt.shortDate)
                    HStack { Text("Status"); Spacer(); StatusBadge(status: d.status) }
                    LabeledText(label: "Detail", value: d.statusDetail)
                    Picker("Document type", selection: $docType) { ForEach(types, id: \.self) { Text($0.humanized).tag($0) } }
                        .onChange(of: docType) { old, new in if !old.isEmpty && new != d.docType { Task { await saveType(new) } } }
                    Button { Task { await openOriginal(d) } } label: { Label("View original file", systemImage: "eye") }
                }
                if case .object(let exif)? = d.metadataJson["exif"], !exif.isEmpty {
                    Section("Photo metadata (EXIF)") {
                        ForEach(exif.sorted { $0.key < $1.key }, id: \.key) { k, v in LabeledText(label: k, value: v.display) }
                    }
                }
                Section {
                    Toggle("Show original-language text", isOn: $showOriginal)
                }
                ForEach(d.pages ?? [], id: \.pageNo) { p in
                    Section {
                        if !p.userCorrectedText.isEmpty {
                            Label("Corrected by investigator", systemImage: "pencil.circle.fill").font(.caption).foregroundStyle(.orange)
                            Text(p.userCorrectedText).textSelection(.enabled)
                        } else {
                            Text(showOriginal || p.textEnglish.isEmpty ? p.textOriginal : p.textEnglish)
                                .font(.callout).textSelection(.enabled)
                        }
                        if !p.visualDescription.isEmpty {
                            Text(p.visualDescription).font(.callout.italic()).foregroundStyle(.secondary)
                        }
                        Button("Correct this page") { editingPage = p }.font(.caption)
                    } header: {
                        HStack {
                            Text("Page \(p.pageNo)\(p.label.isEmpty ? "" : " – \(p.label)")")
                            if p.pageNo == focusPage { Image(systemName: "arrowtriangle.left.fill").foregroundStyle(Theme.gold) }
                            Spacer()
                            Text(p.method.humanized + (p.language.isEmpty ? "" : " · \(p.language)"))
                            if !p.legible { Image(systemName: "eye.slash").foregroundStyle(.red) }
                        }
                    }
                }
            }
            ErrorBanner(message: error)
        }
        .navigationTitle(doc?.ref ?? "Document")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .sheet(item: $editingPage) { p in
            CorrectionSheet(page: p) { text in Task { await savePage(p.pageNo, text) } }
        }
        .sheet(item: $preview) { f in NavigationStack { QuickLookPreview(url: f.url).ignoresSafeArea() } }
    }

    private func load() async {
        do { doc = try await APIClient.shared.request("GET", "documents/\(documentId)"); docType = doc?.docType ?? "" }
        catch { self.error = error.localizedDescription }
    }

    private func saveType(_ t: String) async {
        do { doc = try await APIClient.shared.request("PATCH", "documents/\(documentId)", body: ["doc_type": t]) }
        catch { self.error = error.localizedDescription }
    }

    private func savePage(_ n: Int, _ text: String) async {
        struct Body: Encodable { let pageCorrections: [String: String] }
        do { doc = try await APIClient.shared.request("PATCH", "documents/\(documentId)", body: Body(pageCorrections: ["\(n)": text])) }
        catch { self.error = error.localizedDescription }
    }

    private func openOriginal(_ d: CaseDocument) async {
        do { preview = FileItem(url: try await APIClient.shared.download(path: "documents/\(d.id)/content", query: [], filename: "\(d.ref)_\(d.originalFilename)")) }
        catch { self.error = error.localizedDescription }
    }
}

extension DocumentPage: Identifiable { var id: Int { pageNo } }
struct FileItem: Identifiable { let url: URL; var id: String { url.absoluteString } }

struct CorrectionSheet: View {
    let page: DocumentPage
    var onSave: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var text = ""
    var body: some View {
        NavigationStack {
            TextEditor(text: $text).padding().font(.callout)
                .navigationTitle("Correct page \(page.pageNo)").navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                    ToolbarItem(placement: .confirmationAction) { Button("Save") { onSave(text); dismiss() } }
                }
                .onAppear { text = page.userCorrectedText.isEmpty ? (page.textEnglish.isEmpty ? page.textOriginal : page.textEnglish) : page.userCorrectedText }
        }
    }
}
