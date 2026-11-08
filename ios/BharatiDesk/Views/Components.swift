import QuickLook
import SwiftUI

struct StatusBadge: View {
    let status: String
    var body: some View {
        Text(status.humanized)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(Theme.statusColor(status).opacity(0.15), in: Capsule())
            .foregroundStyle(Theme.statusColor(status))
    }
}

struct SourceChips: View {
    let sources: [SourceRef]
    var body: some View {
        if !sources.isEmpty {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(sources, id: \.self) { s in
                        NavigationLink(value: SourceLink(ref: s.ref, page: s.page)) {
                            Label(s.label, systemImage: s.ref.hasPrefix("N") ? "note.text" : "doc.text")
                                .font(.caption2.monospaced())
                                .padding(.horizontal, 6).padding(.vertical, 2)
                                .background(Theme.navy.opacity(0.08), in: RoundedRectangle(cornerRadius: 5))
                        }
                    }
                }
            }
        }
    }
}

/// Navigation value used to open the cited document/page from any finding.
struct SourceLink: Hashable { let ref: String; let page: Int }

struct JobProgressCard: View {
    let job: Job
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(title).font(.subheadline.weight(.semibold))
                Spacer()
                StatusBadge(status: job.status)
            }
            ProgressView(value: job.progress)
            Text(job.status == "failed" ? job.error : job.message)
                .font(.caption).foregroundStyle(job.status == "failed" ? .red : .secondary).lineLimit(3)
        }
        .padding()
        .background(Theme.paper, in: RoundedRectangle(cornerRadius: 12))
    }
    var title: String {
        switch job.kind {
        case "scan": "Scanning case folder"
        case "analyze": "Running investigation"
        case "report": "Generating Word report"
        case "extract": "Reading uploaded file"
        default: job.kind.humanized
        }
    }
}

struct ErrorBanner: View {
    let message: String?
    var body: some View {
        if let message {
            Label(message, systemImage: "exclamationmark.triangle.fill")
                .font(.footnote).foregroundStyle(.white)
                .padding(10).frame(maxWidth: .infinity, alignment: .leading)
                .background(.red.gradient, in: RoundedRectangle(cornerRadius: 10))
        }
    }
}

struct OfflineBanner: View {
    @Environment(OfflineStore.self) private var offline
    var body: some View {
        if !offline.isOnline {
            Label("Offline – showing saved data. Notes and uploads will sync automatically.", systemImage: "wifi.slash")
                .font(.caption).padding(8).frame(maxWidth: .infinity)
                .background(.orange.opacity(0.2))
        }
    }
}

/// QuickLook preview for DOCX/PDF files (read-only preview inside the app).
struct QuickLookPreview: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> QLPreviewController {
        let c = QLPreviewController(); c.dataSource = context.coordinator; return c
    }
    func updateUIViewController(_ vc: QLPreviewController, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator(url: url) }
    final class Coordinator: NSObject, QLPreviewControllerDataSource {
        let url: URL
        init(url: URL) { self.url = url }
        func numberOfPreviewItems(in controller: QLPreviewController) -> Int { 1 }
        func previewController(_ controller: QLPreviewController, previewItemAt index: Int) -> QLPreviewItem { url as NSURL }
    }
}

/// Full iOS share sheet: Save to Files, Open in Word, Mail, WhatsApp, AirDrop...
struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }
    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}

struct LabeledText: View {
    let label: String
    let value: String
    var body: some View {
        if !value.isEmpty {
            LabeledContent(label) { Text(value).multilineTextAlignment(.trailing).textSelection(.enabled) }
        }
    }
}
