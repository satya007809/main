import SwiftUI

/// Dashboard → New Investigation → Case details → Folder link → Case type → (Create & scan)
@MainActor
struct NewCaseView: View {
    var onCreated: (CaseRecord) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var input = CaseInput()
    @State private var investigationDate = Date()
    @State private var aspects: [Aspect] = []
    @State private var connectors: [Connector] = []
    @State private var busy = false
    @State private var error: String?
    @State private var auth = WebAuthenticator()

    var body: some View {
        NavigationStack {
            Form {
                CaseDetailsSection(input: $input, investigationDate: $investigationDate)

                Section {
                    Picker("Case type", selection: $input.category) {
                        ForEach(CaseCategory.allCases) { Text($0.title).tag($0.rawValue) }
                    }
                    AspectPicker(all: aspects, category: input.category, selected: $input.additionalAspects)
                } header: { Text("Case type & playbook") } footer: {
                    Text("The matching investigation playbook is applied automatically. Add aspects such as hire & reward or close proximity if they are already alleged; the engine also flags aspects it detects.")
                }

                Section {
                    TextField("Paste Google Drive / OneDrive folder link", text: $input.sourceLink, axis: .vertical)
                        .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    if let p = provider, let c = connectors.first(where: { $0.provider == p }) {
                        if c.connected {
                            Label("Connected as \(c.accountEmail)", systemImage: "checkmark.circle.fill").foregroundStyle(.green).font(.footnote)
                        } else {
                            Button { Task { await connect(p) } } label: {
                                Label("Connect \(p == "google_drive" ? "Google Drive" : "OneDrive")", systemImage: "link.badge.plus")
                            }
                            .disabled(!c.configured)
                        }
                    }
                } header: { Text("Case folder") } footer: {
                    Text("Only folders your own account can open are read. The folder is never made public.")
                }

                ReportOptionsSection(input: $input)
                ErrorBanner(message: error).listRowBackground(Color.clear)
            }
            .navigationTitle("New Investigation")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(input.sourceLink.isEmpty ? "Create" : "Create & Scan") { Task { await create() } }
                        .disabled(busy || (input.claimNumber.isEmpty && input.insuredName.isEmpty))
                }
            }
            .task {
                aspects = (try? await APIClient.shared.request("GET", "playbooks/aspects")) ?? []
                connectors = (try? await APIClient.shared.request("GET", "connectors")) ?? []
            }
            .overlay { if busy { ProgressView().controlSize(.large) } }
        }
    }

    private var provider: String? {
        let l = input.sourceLink.lowercased()
        if l.contains("drive.google.com") || l.contains("docs.google.com") { return "google_drive" }
        if l.contains("1drv.ms") || l.contains("onedrive") || l.contains("sharepoint.com") { return "onedrive" }
        return nil
    }

    private func connect(_ p: String) async {
        do { try await auth.connect(provider: p); connectors = try await APIClient.shared.request("GET", "connectors") }
        catch { self.error = error.localizedDescription }
    }

    private func create() async {
        busy = true; error = nil
        defer { busy = false }
        input.investigationDate = investigationDate.formatted(.iso8601.year().month().day())
        do {
            let c: CaseRecord = try await APIClient.shared.request("POST", "cases", body: input)
            if !c.sourceLink.isEmpty {
                let _: Job = try await APIClient.shared.request("POST", "cases/\(c.id)/scan")
            }
            onCreated(c)
        } catch { self.error = error.localizedDescription }
    }
}

struct CaseDetailsSection: View {
    @Binding var input: CaseInput
    @Binding var investigationDate: Date
    var body: some View {
        Section("Case details") {
            TextField("Insured's name", text: $input.insuredName).textContentType(.name)
            TextField("Claim number", text: $input.claimNumber).textInputAutocapitalization(.characters)
            TextField("Policy number", text: $input.policyNumber).textInputAutocapitalization(.characters)
            if CaseCategory(rawValue: input.category)?.needsVehicle ?? true {
                TextField("Vehicle registration (e.g. AP 39 AB 1234)", text: $input.vehicleRegistration)
                    .textInputAutocapitalization(.characters)
            }
            TextField("Insurer", text: $input.insurerName)
            TextField("Investigation reference", text: $input.investigationReference)
            DatePicker("Investigation date", selection: $investigationDate, displayedComponents: .date)
        }
    }
}

struct AspectPicker: View {
    let all: [Aspect]
    let category: String
    @Binding var selected: [String]
    var body: some View {
        let options = all.filter { $0.key != category && $0.key != "general" }
        if !options.isEmpty {
            DisclosureGroup("Additional aspects (\(selected.count))") {
                ForEach(options) { a in
                    Toggle(a.name, isOn: Binding(
                        get: { selected.contains(a.key) },
                        set: { on in if on { selected.append(a.key) } else { selected.removeAll { $0 == a.key } } }))
                }
            }
        }
    }
}

struct ReportOptionsSection: View {
    @Binding var input: CaseInput
    var body: some View {
        Section {
            Stepper("Page limit: \(input.pageLimit)", value: $input.pageLimit, in: 3...10)
            Toggle("Include invoice", isOn: $input.includeInvoice)
            if input.includeInvoice {
                TextField("Invoice number", text: $input.invoice.invoiceNumber)
                TextField("Invoice date (YYYY-MM-DD)", text: $input.invoice.invoiceDate)
                TextField("Bill to (insurer office)", text: $input.invoice.billTo)
                TextField("Insurer GSTIN (optional)", text: $input.invoice.billToGstin)
                ForEach($input.invoice.items) { $item in
                    HStack {
                        TextField("Description", text: $item.description)
                        TextField("Amount", value: $item.amount, format: .number).keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing).frame(width: 90)
                    }
                }
                .onDelete { input.invoice.items.remove(atOffsets: $0) }
                Button("Add invoice line") { input.invoice.items.append(InvoiceItem(description: "Investigation fee", amount: 0)) }
                TextField("GST %", value: Binding(get: { input.invoice.gstPercent ?? 0 }, set: { input.invoice.gstPercent = $0 }),
                          format: .number).keyboardType(.decimalPad)
            }
        } header: { Text("Report") } footer: {
            Text("Default 7 pages; select up to 10 for complex cases. Invoice amounts are never filled in automatically.")
        }
    }
}
