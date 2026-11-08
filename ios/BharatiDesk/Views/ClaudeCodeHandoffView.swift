import SwiftUI
import UIKit

/// Hands an investigation to the user's own Claude Code session (runs on their Claude plan, no API billing).
struct ClaudeCodeHandoffView: View {
    let record: CaseRecord
    let reportOnly: Bool
    @Environment(\.dismiss) private var dismiss
    @State private var copied = false

    private var prompt: String {
        let ref = record.claimNumber.isEmpty ? record.title : record.claimNumber
        if reportOnly {
            return "Use the investigate-case skill to write a new Word report for case \(ref) (case id \(record.id)) from its latest accepted analysis, page limit \(record.pageLimit)."
        }
        return "Use the investigate-case skill to investigate case \(ref) (case id \(record.id)) and write its Word report, page limit \(record.pageLimit)."
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text(prompt).font(.callout.monospaced()).textSelection(.enabled)
                    Button {
                        UIPasteboard.general.string = prompt
                        copied = true
                    } label: { Label(copied ? "Copied" : "Copy instruction", systemImage: copied ? "checkmark" : "doc.on.doc") }
                } header: { Text("Instruction for Claude Code") }
                Section("Steps") {
                    Label("Open the Claude app → Code, and start a session on the Bharati repository (environment with your server access token).", systemImage: "1.circle")
                    Label("Paste the instruction and send. Claude Code reads every document and photo, applies your playbooks and submits its findings.", systemImage: "2.circle")
                    Label("This server checks every citation and rejects anything unsupported; Claude Code corrects and resubmits.", systemImage: "3.circle")
                    Label("Come back here and pull to refresh: findings and the new report version appear on this case.", systemImage: "4.circle")
                }
                Section {
                    Text("Runs on your Claude subscription – no separate API charges. Large cases use more of your plan's usage limit.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle(reportOnly ? "Write report" : "Investigate")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
    }
}
