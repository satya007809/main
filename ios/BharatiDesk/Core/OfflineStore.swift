import Foundation
import Network
import Observation

/// Offline support:
///  * caches the last-known cases, documents, notes and analyses so they can be read without internet;
///  * keeps an outbox of notes and evidence uploads made offline and syncs them when the network returns.
/// All files are written with complete data protection (encrypted while the phone is locked).
@MainActor
@Observable
final class OfflineStore {
    static let shared = OfflineStore()

    private(set) var isOnline = true
    private(set) var pendingNotes: [String: [NoteInput]] = [:]     // caseId -> notes
    private(set) var pendingUploads: [PendingUpload] = []
    private(set) var syncError: String?

    struct PendingUpload: Codable, Identifiable, Hashable {
        var id: String { clientUUID }
        let caseId: String
        let localPath: String
        let filename: String
        let mimeType: String
        let clientUUID: String
    }

    private let monitor = NWPathMonitor()
    private let root: URL
    private let enc = JSONEncoder()
    private let dec = JSONDecoder()

    private init() {
        root = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("BharatiOffline", isDirectory: true)
        try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        var rv = URLResourceValues(); rv.isExcludedFromBackup = true
        var r = root; try? r.setResourceValues(rv)
        pendingNotes = load("outbox_notes.json") ?? [:]
        pendingUploads = load("outbox_uploads.json") ?? []
        monitor.pathUpdateHandler = { [weak self] path in
            guard let self else { return }
            Task { @MainActor in
                let was = self.isOnline
                self.isOnline = path.status == .satisfied
                if self.isOnline && !was { await self.sync() }
            }
        }
        monitor.start(queue: DispatchQueue(label: "bid.network"))
    }

    // MARK: cache

    func cache<T: Encodable>(_ value: T, as name: String) {
        guard let data = try? enc.encode(value) else { return }
        try? data.write(to: root.appendingPathComponent(name), options: [.atomic, .completeFileProtection])
    }

    func load<T: Decodable>(_ name: String) -> T? {
        guard let data = try? Data(contentsOf: root.appendingPathComponent(name)) else { return nil }
        return try? dec.decode(T.self, from: data)
    }

    // MARK: outbox

    func queueNote(_ note: NoteInput, caseId: String) {
        pendingNotes[caseId, default: []].append(note)
        cache(pendingNotes, as: "outbox_notes.json")
    }

    func queueUpload(caseId: String, from url: URL, filename: String, mimeType: String) throws -> PendingUpload {
        let id = UUID().uuidString
        let dest = root.appendingPathComponent("upload_\(id)")
        try FileManager.default.copyItem(at: url, to: dest)
        try (dest as NSURL).setResourceValue(URLFileProtection.complete, forKey: .fileProtectionKey)
        let p = PendingUpload(caseId: caseId, localPath: dest.lastPathComponent, filename: filename, mimeType: mimeType, clientUUID: id)
        pendingUploads.append(p)
        cache(pendingUploads, as: "outbox_uploads.json")
        return p
    }

    func notesPending(for caseId: String) -> [NoteInput] { pendingNotes[caseId] ?? [] }
    func uploadsPending(for caseId: String) -> [PendingUpload] { pendingUploads.filter { $0.caseId == caseId } }

    /// Idempotent: the server de-duplicates by client UUID, so a retry after a dropped connection is safe.
    func sync() async {
        syncError = nil
        for (caseId, notes) in pendingNotes {
            var remaining: [NoteInput] = []
            for n in notes {
                do { let _: CaseNote = try await APIClient.shared.request("POST", "cases/\(caseId)/notes", body: n) }
                catch { remaining.append(n); syncError = error.localizedDescription }
            }
            pendingNotes[caseId] = remaining.isEmpty ? nil : remaining
        }
        cache(pendingNotes, as: "outbox_notes.json")
        var left: [PendingUpload] = []
        for u in pendingUploads {
            let url = root.appendingPathComponent(u.localPath)
            do {
                _ = try await APIClient.shared.upload(caseId: u.caseId, fileURL: url, filename: u.filename,
                                                      mimeType: u.mimeType, clientUUID: u.clientUUID)
                try? FileManager.default.removeItem(at: url)
            } catch { left.append(u); syncError = error.localizedDescription }
        }
        pendingUploads = left
        cache(pendingUploads, as: "outbox_uploads.json")
    }

    func wipe() {
        try? FileManager.default.removeItem(at: root)
        try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        pendingNotes = [:]; pendingUploads = []
    }
}
