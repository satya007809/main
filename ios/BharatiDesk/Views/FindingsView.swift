import SwiftUI

struct FindingsView: View {
    let model: CaseModel
    @State private var tab = "opinion"
    private let tabs = [("opinion", "Opinion"), ("findings", "Evidence"), ("chronology", "Chronology"),
                        ("discrepancies", "Discrepancies"), ("pending", "Pending"), ("policy", "Policy")]

    var body: some View {
        Group {
            if let run = model.latest, let r = run.result {
                List {
                    Section {
                        Picker("Section", selection: $tab) { ForEach(tabs.indices, id: \.self) { i in Text(tabs[i].1).tag(tabs[i].0) } }
                            .pickerStyle(.segmented)
                    }
                    .listRowBackground(Color.clear)
                    if let v = run.validation, !v.errors.isEmpty || !v.warnings.isEmpty { validation(v) }
                    switch tab {
                    case "findings": findings(r)
                    case "chronology": chronology(r)
                    case "discrepancies": discrepancies(r)
                    case "pending": pending(r)
                    case "policy": policy(r)
                    default: opinion(r, run)
                    }
                }
            } else {
                ContentUnavailableView("No analysis yet", systemImage: "magnifyingglass", description: Text("Run the investigation first."))
            }
        }
        .navigationTitle("Findings")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func validation(_ v: ValidationReport) -> some View {
        Section {
            ForEach(v.errors, id: \.self) { Label($0, systemImage: "xmark.octagon.fill").foregroundStyle(.red).font(.caption) }
            ForEach(v.warnings, id: \.self) { Label($0, systemImage: "exclamationmark.triangle").foregroundStyle(.orange).font(.caption) }
        } header: { Text("Validation") } footer: {
            if !v.errors.isEmpty { Text("A report cannot be generated until the analysis passes validation. Add evidence or notes and rerun.") }
        }
    }

    @ViewBuilder private func opinion(_ r: AnalysisResult, _ run: AnalysisRun) -> some View {
        Section {
            Text(r.opinion.verdictTitle).font(.title3.bold())
                .foregroundStyle(r.opinion.verdict == "genuine_admissible" ? .green :
                                    r.opinion.verdict == "insufficient_evidence" ? .orange : .red)
            Text(r.opinion.summary)
        } header: { Text("Final opinion") }
        Section("Decisive evidence") {
            ForEach(r.opinion.decisiveEvidence, id: \.self) { e in
                VStack(alignment: .leading, spacing: 4) { Text(e.point); SourceChips(sources: e.sources) }
            }
        }
        if !r.opinion.limitations.isEmpty {
            Section("Limitations") { ForEach(r.opinion.limitations, id: \.self) { Text($0) } }
        }
        if !r.detectedAspects.isEmpty {
            Section("Additional aspects detected") {
                ForEach(r.detectedAspects, id: \.self) { a in
                    VStack(alignment: .leading) { Text(a.key.humanized).bold(); Text(a.reason).font(.caption) }
                }
            }
        }
        if !r.anomalies.isEmpty {
            Section("Anomalies") { ForEach(r.anomalies, id: \.self) { Label($0, systemImage: "exclamationmark.shield").font(.caption) } }
        }
        Section("Run details") {
            LabeledText(label: "Run", value: "#\(run.runNo) · \(run.createdAt.shortDate)")
            LabeledText(label: "Playbooks", value: run.playbooksUsed.map { "\($0.key.humanized) v\($0.version)" }.joined(separator: ", "))
            LabeledText(label: "Model", value: run.model)
        }
    }

    @ViewBuilder private func findings(_ r: AnalysisResult) -> some View {
        let groups: [(String, String)] = [("verified_fact", "Verified facts"), ("documentary_evidence", "Documentary evidence"),
                                          ("field_verification", "Field verification"), ("technical_observation", "Technical observations"),
                                          ("claimant_statement", "Claimant statements"), ("third_party_statement", "Third-party statements"),
                                          ("ai_inference", "AI inferences")]
        ForEach(groups.indices, id: \.self) { gi in
            let (key, title) = groups[gi]
            let items = r.findings.filter { $0.category == key }
            if !items.isEmpty {
                Section(title) {
                    ForEach(items) { f in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack(alignment: .top) {
                                Text(f.statement)
                                Spacer()
                                if f.significance == "material" { StatusBadge(status: "material") }
                            }
                            SourceChips(sources: f.sources)
                        }
                    }
                }
            }
        }
        if !r.photoObservations.isEmpty {
            Section("Photographs") {
                ForEach(r.photoObservations, id: \.self) { p in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(p.observation)
                        if !p.metadataNote.isEmpty { Text(p.metadataNote).font(.caption).foregroundStyle(.secondary) }
                        SourceChips(sources: [SourceRef(ref: p.ref, page: 1)])
                    }
                }
            }
        }
        if !r.questionAnswers.isEmpty {
            Section("Investigation questions") {
                ForEach(r.questionAnswers, id: \.self) { q in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack { Text(q.question).font(.subheadline.bold()); Spacer(); StatusBadge(status: q.basis) }
                        Text(q.answer).font(.callout)
                        SourceChips(sources: q.sources)
                    }
                }
            }
        }
        Section("Document checklist") {
            ForEach(r.checklist, id: \.self) { c in
                HStack { Text(c.label); Spacer(); StatusBadge(status: c.status) }
            }
        }
    }

    private func chronology(_ r: AnalysisResult) -> some View {
        Section("Chronology") {
            ForEach(Array(r.chronology.enumerated()), id: \.offset) { _, c in
                VStack(alignment: .leading, spacing: 3) {
                    HStack { Text("\(c.date) \(c.time)").font(.caption.monospaced().bold()); Spacer(); StatusBadge(status: c.certainty) }
                    Text(c.event)
                    SourceChips(sources: c.sources)
                }
            }
        }
    }

    private func discrepancies(_ r: AnalysisResult) -> some View {
        Section("Discrepancies") {
            if r.discrepancies.isEmpty { Text("No discrepancies identified.") }
            ForEach(r.discrepancies) { d in
                VStack(alignment: .leading, spacing: 6) {
                    HStack { Text(d.point).bold(); Spacer(); StatusBadge(status: d.significance) }
                    Text("A: \(d.versionA)").font(.callout); SourceChips(sources: d.sourcesA)
                    Text("B: \(d.versionB)").font(.callout); SourceChips(sources: d.sourcesB)
                    if !d.resolution.isEmpty { Text("Resolution: \(d.resolution)").font(.caption).foregroundStyle(.secondary) }
                }
            }
        }
    }

    @ViewBuilder private func pending(_ r: AnalysisResult) -> some View {
        Section {
            ForEach(r.pendingVerifications, id: \.self) { p in
                VStack(alignment: .leading) {
                    HStack { Text(p.item).bold(); Spacer(); if p.impact == "could_change_opinion" { StatusBadge(status: "material") } }
                    Text(p.reason).font(.caption)
                }
            }
        } header: { Text("Pending verifications") } footer: {
            Text("Record the result under Field notes & verification results, then rerun the investigation.")
        }
        Section("External sources") {
            ForEach(r.externalChecks, id: \.self) { e in
                VStack(alignment: .leading) {
                    HStack { Text(e.source.humanized); Spacer(); StatusBadge(status: e.status) }
                    if !e.remarks.isEmpty { Text(e.remarks).font(.caption) }
                    if !e.basisRefs.isEmpty { SourceChips(sources: e.basisRefs.map { SourceRef(ref: $0, page: 0) }) }
                }
            }
        }
    }

    @ViewBuilder private func policy(_ r: AnalysisResult) -> some View {
        Section {
            if !r.policyAnalysis.wordingAvailable {
                Label("Policy wording not in folder – coverage position is provisional", systemImage: "exclamationmark.triangle").foregroundStyle(.orange)
            }
            Text(r.policyAnalysis.coveragePosition)
        } header: { Text("Coverage position") }
        Section("Clauses") {
            ForEach(r.policyAnalysis.clauses, id: \.self) { c in
                VStack(alignment: .leading, spacing: 4) {
                    Text(c.clauseRef).bold()
                    Text("“\(c.quotedText)”").font(.callout.italic())
                    Text(c.application).font(.callout)
                    SourceChips(sources: c.sources)
                }
            }
        }
    }
}
