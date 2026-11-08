import SwiftUI
import UniformTypeIdentifiers

@MainActor
struct ReportsView: View {
    let model: CaseModel
    @State private var pageLimit = 7
    @State private var preview: FileItem?
    @State private var share: FileItem?
    @State private var exportURL: URL?
    @State private var showExporter = false
    @State private var busy: String?
    @State private var message: String?
    @State private var error: String?

    var body: some View {
        List {
            if let job = model.tracker.job, job.kind == "report", job.isActive {
                Section { JobProgressCard(job: job) }.listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
            }
            Section {
                Stepper("Page limit: \(pageLimit)", value: $pageLimit, in: 3...10)
                Button {
                    Task { await model.start("cases/\(model.caseId)/reports", body: ["page_limit": pageLimit]) }
                } label: {
                    Label(model.reports.isEmpty ? "Generate Word report" : "Regenerate report (new version)", systemImage: "doc.badge.gearshape")
                }
                .disabled(!canGenerate || model.tracker.job?.isActive == true)
            } header: { Text("Generate") } footer: {
                if let v = model.latest?.validation, !v.errors.isEmpty {
                    Text("The latest analysis has validation errors. Rerun the investigation first.").foregroundStyle(.red)
                } else {
                    Text("Uses the latest investigation analysis (run #\(model.latest?.runNo ?? 0)). Earlier versions are kept.")
                }
            }
            ErrorBanner(message: error)
            if let message { Label(message, systemImage: "checkmark.circle").foregroundStyle(.green) }
            Section("Versions") {
                if model.reports.isEmpty { Text("No reports yet.").foregroundStyle(.secondary) }
                ForEach(model.reports) { r in
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("Version \(r.version)").bold()
                            Spacer()
                            StatusBadge(status: r.status)
                        }
                        Text("\(r.pageCount) pages (limit \(r.pageLimit)) · \(r.createdAt.shortDate)").font(.caption).foregroundStyle(.secondary)
                        ForEach(r.warnings, id: \.self) { Label($0, systemImage: "exclamationmark.triangle").font(.caption).foregroundStyle(.orange) }
                        if !r.error.isEmpty { Text(r.error).font(.caption).foregroundStyle(.red) }
                        if r.status == "completed" {
                            HStack {
                                Button { Task { await fetch(r, "docx") { preview = FileItem(url: $0) } } } label: { Label("Preview", systemImage: "eye") }
                                Spacer()
                                Button { Task { await fetch(r, "docx") { share = FileItem(url: $0) } } } label: { Label("Share / Word", systemImage: "square.and.arrow.up") }
                                Spacer()
                                Menu {
                                    Button("Save DOCX to Files") { Task { await fetch(r, "docx") { exportURL = $0; showExporter = true } } }
                                    if r.hasPdf {
                                        Button("Share PDF") { Task { await fetch(r, "pdf") { share = FileItem(url: $0) } } }
                                        Button("Save PDF to Files") { Task { await fetch(r, "pdf") { exportURL = $0; showExporter = true } } }
                                    }
                                    if model.record?.sourceProvider == "google_drive" || model.record?.sourceProvider == "onedrive" {
                                        Button("Upload to case folder") { Task { await uploadToDrive(r) } }
                                    }
                                } label: { Image(systemName: "ellipsis.circle") }
                            }
                            .buttonStyle(.borderless)
                            if !r.driveFileId.isEmpty { Label("Uploaded to case folder", systemImage: "icloud.and.arrow.up").font(.caption).foregroundStyle(.green) }
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
            Section {
                Text("Tip: in the share sheet choose “Open in Word” to edit the report in Microsoft Word for iPhone, then save it back to Files or OneDrive.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
        .navigationTitle("Word report")
        .overlay { if let busy { ProgressView(busy).padding().background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12)) } }
        .onAppear { pageLimit = model.record?.pageLimit ?? 7 }
        .refreshable { await model.load() }
        .sheet(item: $preview) { f in NavigationStack { QuickLookPreview(url: f.url).ignoresSafeArea() } }
        .sheet(item: $share) { f in ShareSheet(items: [f.url]).presentationDetents([.medium, .large]) }
        .fileExporter(isPresented: $showExporter, item: exportURL, contentTypes: [.data],
                      defaultFilename: exportURL?.lastPathComponent) { _ in }
    }

    private var canGenerate: Bool { model.latest != nil && (model.latest?.validation?.errors.isEmpty ?? true) }

    private func fetch(_ r: ReportVersion, _ fmt: String, then: (URL) -> Void) async {
        busy = "Downloading…"; defer { busy = nil }
        do {
            let url = try await APIClient.shared.download(path: "reports/\(r.id)/download", query: [.init(name: "format", value: fmt)],
                                                          filename: "\(r.filename).\(fmt)")
            then(url)
        } catch { self.error = error.localizedDescription }
    }

    private func uploadToDrive(_ r: ReportVersion) async {
        busy = "Uploading…"; defer { busy = nil }
        do { _ = try await APIClient.shared.raw("POST", "reports/\(r.id)/upload-to-drive"); message = "Uploaded to case folder"; await model.load() }
        catch { self.error = error.localizedDescription }
    }
}
