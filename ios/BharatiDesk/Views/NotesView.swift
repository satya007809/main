import SwiftUI

/// Field observations, verification results (hospital, police, RTO, FASTag, GPS) and corrections.
/// These notes are the ONLY way an external verification enters the analysis, so the app records who
/// verified and when. Notes made offline are queued and synced automatically.
struct NotesView: View {
    let model: CaseModel
    @Environment(OfflineStore.self) private var offline
    @State private var adding = false
    @State private var editing: CaseNote?

    var body: some View {
        List {
            let pending = offline.notesPending(for: model.caseId)
            if !pending.isEmpty {
                Section("Waiting to sync") {
                    ForEach(pending, id: \.clientUuid) { n in NoteRowContent(kind: n.kind, title: n.title, bodyText: n.body, ref: "…") }
                }
            }
            Section {
                if model.notes.isEmpty { Text("No notes yet.").foregroundStyle(.secondary) }
                ForEach(model.notes) { n in
                    Button { editing = n } label: {
                        NoteRowContent(kind: n.kind, title: n.title, bodyText: n.body, ref: n.ref,
                                       footer: [n.verifiedBy, n.verifiedOn].filter { !$0.isEmpty }.joined(separator: " · "))
                    }
                    .buttonStyle(.plain)
                }
                .onDelete { idx in Task { for i in idx { await delete(model.notes[i]) } } }
            } footer: {
                Text("After adding verification results, rerun the investigation so the findings and report use them.")
            }
        }
        .navigationTitle("Notes & verification")
        .toolbar { ToolbarItem(placement: .topBarTrailing) { Button { adding = true } label: { Image(systemName: "plus") } } }
        .sheet(isPresented: $adding) { NoteEditor(model: model, existing: nil) }
        .sheet(item: $editing) { n in NoteEditor(model: model, existing: n) }
        .refreshable { await model.load() }
    }

    private func delete(_ n: CaseNote) async {
        _ = try? await APIClient.shared.raw("DELETE", "notes/\(n.id)")
        await model.load()
    }
}

struct NoteRowContent: View {
    let kind: String; let title: String; let bodyText: String; let ref: String
    var footer: String = ""
    var body: some View {
        let k = NoteKind(rawValue: kind)
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Label(k?.title ?? kind.humanized, systemImage: k?.icon ?? "note.text").font(.caption.bold()).foregroundStyle(Theme.navy)
                Spacer()
                Text(ref).font(.caption.monospaced())
            }
            if !title.isEmpty { Text(title).bold() }
            Text(bodyText).lineLimit(4)
            if !footer.isEmpty { Text(footer).font(.caption).foregroundStyle(.secondary) }
        }
    }
}

struct NoteEditor: View {
    let model: CaseModel
    let existing: CaseNote?
    @Environment(\.dismiss) private var dismiss
    @Environment(OfflineStore.self) private var offline
    @State private var note = NoteInput(kind: NoteKind.fieldObservation.rawValue, body: "")
    @State private var verifiedOn = Date()
    @State private var error: String?

    private var isVerification: Bool { note.kind.hasSuffix("_verification") }

    var body: some View {
        NavigationStack {
            Form {
                Picker("Type", selection: $note.kind) { ForEach(NoteKind.allCases) { Label($0.title, systemImage: $0.icon).tag($0.rawValue) } }
                TextField("Title (optional)", text: $note.title)
                Section(isVerification ? "Verification result" : "Details") {
                    TextEditor(text: $note.body).frame(minHeight: 160)
                }
                if isVerification {
                    Section {
                        TextField("Verified by (name / officer / hospital staff)", text: $note.verifiedBy)
                        DatePicker("Verified on", selection: $verifiedOn, displayedComponents: .date)
                    } footer: { Text("Record exactly what was confirmed and by whom. The report will cite this as a field verification.") }
                }
                if note.kind == "correction" {
                    TextField("What does this correct? e.g. D004 page 2, driver name", text: $note.target)
                }
                ErrorBanner(message: error)
            }
            .navigationTitle(existing == nil ? "Add note" : "Edit \(existing!.ref)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Save") { Task { await save() } }.disabled(note.body.trimmingCharacters(in: .whitespaces).isEmpty) }
            }
            .onAppear {
                if let e = existing {
                    note = NoteInput(kind: e.kind, title: e.title, body: e.body, verifiedBy: e.verifiedBy, verifiedOn: e.verifiedOn,
                                     target: e.target, clientUuid: e.clientUuid)
                    if let d = try? Date(e.verifiedOn + "T00:00:00Z", strategy: .iso8601) { verifiedOn = d }
                }
            }
        }
    }

    private func save() async {
        if isVerification { note.verifiedOn = verifiedOn.formatted(.iso8601.year().month().day()) }
        do {
            if let e = existing {
                let _: CaseNote = try await APIClient.shared.request("PUT", "notes/\(e.id)", body: note)
            } else {
                let _: CaseNote = try await APIClient.shared.request("POST", "cases/\(model.caseId)/notes", body: note)
            }
            await model.load()
            dismiss()
        } catch let e as APIError where e.isOffline && existing == nil {
            offline.queueNote(note, caseId: model.caseId)   // draft kept; syncs when back online
            dismiss()
        } catch { self.error = error.localizedDescription }
    }
}
