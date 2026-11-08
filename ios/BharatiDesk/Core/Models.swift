import Foundation

// MARK: - Generic JSON (for free-form metadata)

enum JSONValue: Codable, Hashable {
    case string(String), number(Double), bool(Bool), object([String: JSONValue]), array([JSONValue]), null

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let b = try? c.decode(Bool.self) { self = .bool(b) }
        else if let n = try? c.decode(Double.self) { self = .number(n) }
        else if let s = try? c.decode(String.self) { self = .string(s) }
        else if let a = try? c.decode([JSONValue].self) { self = .array(a) }
        else { self = .object(try c.decode([String: JSONValue].self)) }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .string(let s): try c.encode(s)
        case .number(let n): try c.encode(n)
        case .bool(let b): try c.encode(b)
        case .object(let o): try c.encode(o)
        case .array(let a): try c.encode(a)
        case .null: try c.encodeNil()
        }
    }

    var display: String {
        switch self {
        case .string(let s): return s
        case .number(let n): return n == n.rounded() ? String(Int(n)) : String(n)
        case .bool(let b): return b ? "Yes" : "No"
        case .object(let o): return o.sorted { $0.key < $1.key }.map { "\($0.key): \($0.value.display)" }.joined(separator: "\n")
        case .array(let a): return a.map(\.display).joined(separator: ", ")
        case .null: return "—"
        }
    }
}

// MARK: - Auth

struct TokenPair: Codable { let accessToken: String; let refreshToken: String; let expiresIn: Int }

struct UserProfile: Codable {
    let id: String
    let email: String
    var fullName: String
    let isAdmin: Bool
    var investigatorProfile: [String: String]
}

// MARK: - Cases

enum CaseCategory: String, CaseIterable, Identifiable, Codable {
    case ownDamage = "own_damage", paInjury = "pa_injury", paDeath = "pa_death", theft, fire
    case roadAccident = "road_accident", general
    var id: String { rawValue }
    var title: String {
        switch self {
        case .ownDamage: "Own Damage (Motor OD)"
        case .paInjury: "PA – Injury"
        case .paDeath: "PA – Death"
        case .theft: "Vehicle Theft"
        case .fire: "Fire"
        case .roadAccident: "Road Accident"
        case .general: "Other / Special"
        }
    }
    var needsVehicle: Bool { [.ownDamage, .theft, .roadAccident, .fire].contains(self) }
}

struct InvoiceItem: Codable, Hashable, Identifiable {
    var id = UUID()
    var description: String
    var amount: Double
    enum CodingKeys: String, CodingKey { case description, amount }
}

struct Invoice: Codable, Hashable {
    var invoiceNumber: String = ""
    var invoiceDate: String = ""
    var billTo: String = ""
    var billToGstin: String = ""
    var items: [InvoiceItem] = []
    var gstPercent: Double? = 18

    init() {}
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        invoiceNumber = try c.decodeIfPresent(String.self, forKey: .invoiceNumber) ?? ""
        invoiceDate = try c.decodeIfPresent(String.self, forKey: .invoiceDate) ?? ""
        billTo = try c.decodeIfPresent(String.self, forKey: .billTo) ?? ""
        billToGstin = try c.decodeIfPresent(String.self, forKey: .billToGstin) ?? ""
        items = try c.decodeIfPresent([InvoiceItem].self, forKey: .items) ?? []
        gstPercent = try c.decodeIfPresent(Double.self, forKey: .gstPercent)
    }
    enum CodingKeys: String, CodingKey { case invoiceNumber, invoiceDate, billTo, billToGstin, items, gstPercent }
}

struct CaseRecord: Codable, Identifiable, Hashable {
    let id: String
    var insuredName: String
    var claimNumber: String
    var policyNumber: String
    var vehicleRegistration: String
    var insurerName: String
    var investigationReference: String
    var investigationDate: String
    var category: String
    var additionalAspects: [String]
    var sourceProvider: String
    var sourceLink: String
    var status: String
    var pageLimit: Int
    var includeInvoice: Bool
    var invoice: [String: JSONValue]
    var retentionDays: Int
    var notes: String
    var createdAt: String
    var updatedAt: String
    var documentCount: Int

    var title: String { insuredName.isEmpty ? (claimNumber.isEmpty ? "Untitled case" : claimNumber) : insuredName }
    var categoryTitle: String { CaseCategory(rawValue: category)?.title ?? category }
}

struct CaseInput: Codable {
    var insuredName = ""
    var claimNumber = ""
    var policyNumber = ""
    var vehicleRegistration = ""
    var insurerName = ""
    var investigationReference = ""
    var investigationDate = ""
    var category = CaseCategory.ownDamage.rawValue
    var additionalAspects: [String] = []
    var sourceLink = ""
    var pageLimit = 7
    var includeInvoice = false
    var invoice: Invoice = Invoice()
    var notes = ""
}

struct Dashboard: Codable { let groups: [String: Int] }

// MARK: - Documents

struct DocumentPage: Codable, Hashable {
    let pageNo: Int
    let label: String
    let method: String
    let language: String
    let textOriginal: String
    let textEnglish: String
    let visualDescription: String
    let legible: Bool
    var userCorrectedText: String
}

struct CaseDocument: Codable, Identifiable, Hashable {
    let id: String
    let ref: String
    let parentId: String?
    let origin: String
    let sourcePath: String
    let originalFilename: String
    let mimeType: String
    let sizeBytes: Int
    let sourceModifiedAt: String
    let status: String
    let statusDetail: String
    let duplicateOfId: String?
    var docType: String
    let docTypeConfidence: Double
    let docTypeCorrected: Bool
    let languages: [String]
    let pageCount: Int
    let metadataJson: [String: JSONValue]
    var pages: [DocumentPage]?

    var displayPath: String { sourcePath.isEmpty ? originalFilename : "\(sourcePath)/\(originalFilename)" }
}

struct InventorySummary: Codable {
    let processed: Int
    let unreadable: Int
    let pending: Int
    let duplicates: Int
    let missingDocuments: [ChecklistItem]
}

// MARK: - Notes

enum NoteKind: String, CaseIterable, Identifiable, Codable {
    case fieldObservation = "field_observation", hospitalVerification = "hospital_verification"
    case policeVerification = "police_verification", rtoVerification = "rto_verification"
    case fastagVerification = "fastag_verification", gpsVerification = "gps_verification"
    case otherVerification = "other_verification", correction, instruction
    var id: String { rawValue }
    var title: String {
        switch self {
        case .fieldObservation: "Field observation"
        case .hospitalVerification: "Hospital verification result"
        case .policeVerification: "Police verification result"
        case .rtoVerification: "RTO / RTA verification result"
        case .fastagVerification: "FASTag verification result"
        case .gpsVerification: "GPS / Timeline verification result"
        case .otherVerification: "Other verification result"
        case .correction: "Correction to extracted information"
        case .instruction: "Case-specific instruction"
        }
    }
    var icon: String {
        switch self {
        case .fieldObservation: "binoculars"
        case .hospitalVerification: "cross.case"
        case .policeVerification: "shield"
        case .rtoVerification: "car"
        case .fastagVerification: "road.lanes"
        case .gpsVerification: "location"
        case .otherVerification: "checkmark.seal"
        case .correction: "pencil"
        case .instruction: "text.bubble"
        }
    }
}

struct NoteInput: Codable, Hashable {
    var kind: String
    var title: String = ""
    var body: String
    var verifiedBy: String = ""
    var verifiedOn: String = ""
    var target: String = ""
    var clientUuid: String = UUID().uuidString
}

struct CaseNote: Codable, Identifiable, Hashable {
    let id: String
    let ref: String
    let kind: String
    let title: String
    let body: String
    let verifiedBy: String
    let verifiedOn: String
    let target: String
    let clientUuid: String
    let createdAt: String
}

// MARK: - Jobs

struct Job: Codable, Identifiable, Hashable {
    let id: String
    let caseId: String?
    let kind: String
    let status: String
    let progress: Double
    let message: String
    let error: String
    let attempts: Int
    let createdAt: String
    var isActive: Bool { status == "queued" || status == "running" }
}

// MARK: - Analysis (mirrors backend engine/schema.py)

struct SourceRef: Codable, Hashable { let ref: String; let page: Int
    var label: String { page > 0 ? "\(ref) p.\(page)" : ref }
}

struct Finding: Codable, Hashable, Identifiable {
    let id: String
    let category: String
    let statement: String
    let sources: [SourceRef]
    let significance: String
}

struct ChronologyEntry: Codable, Hashable { let date: String; let time: String; let event: String; let sources: [SourceRef]; let certainty: String }

struct Discrepancy: Codable, Hashable, Identifiable {
    let id: String
    let point: String
    let versionA: String
    let sourcesA: [SourceRef]
    let versionB: String
    let sourcesB: [SourceRef]
    let significance: String
    let resolution: String
}

struct ChecklistItem: Codable, Hashable { let itemId: String; let label: String; let status: String; let refs: [String]; let remarks: String }
struct QuestionAnswer: Codable, Hashable { let question: String; let answer: String; let sources: [SourceRef]; let basis: String }
struct PhotoObservation: Codable, Hashable { let ref: String; let observation: String; let metadataNote: String }
struct ExternalCheck: Codable, Hashable { let source: String; let status: String; let basisRefs: [String]; let remarks: String }
struct PendingVerification: Codable, Hashable { let item: String; let reason: String; let impact: String }
struct PolicyClause: Codable, Hashable { let clauseRef: String; let quotedText: String; let sources: [SourceRef]; let application: String }
struct PolicyAnalysis: Codable, Hashable { let wordingAvailable: Bool; let clauses: [PolicyClause]; let coveragePosition: String }
struct DecisiveEvidence: Codable, Hashable { let point: String; let sources: [SourceRef] }
struct Opinion: Codable, Hashable {
    let verdict: String
    let summary: String
    let decisiveEvidence: [DecisiveEvidence]
    let limitations: [String]
    var verdictTitle: String {
        switch verdict {
        case "genuine_admissible": "Claim appears genuine / admissible"
        case "not_genuine_or_breach_established": "Not genuine / policy breach established"
        default: "Evidence insufficient for a reliable conclusion"
        }
    }
}
struct DetectedAspect: Codable, Hashable { let key: String; let reason: String }

struct AnalysisResult: Codable, Hashable {
    let caseSummary: String
    let detectedAspects: [DetectedAspect]
    let findings: [Finding]
    let chronology: [ChronologyEntry]
    let discrepancies: [Discrepancy]
    let checklist: [ChecklistItem]
    let questionAnswers: [QuestionAnswer]
    let photoObservations: [PhotoObservation]
    let externalChecks: [ExternalCheck]
    let pendingVerifications: [PendingVerification]
    let policyAnalysis: PolicyAnalysis
    let anomalies: [String]
    let opinion: Opinion
}

struct ValidationReport: Codable, Hashable { let errors: [String]; let warnings: [String] }
struct PlaybookUse: Codable, Hashable { let key: String; let version: Int }

struct AnalysisRun: Codable, Identifiable, Hashable {
    let id: String
    let runNo: Int
    let status: String
    let model: String
    let playbooksUsed: [PlaybookUse]
    let validation: ValidationReport?
    let error: String
    let createdAt: String
    var result: AnalysisResult?

    enum CodingKeys: String, CodingKey { case id, runNo, status, model, playbooksUsed, validation, error, createdAt, result }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        runNo = try c.decode(Int.self, forKey: .runNo)
        status = try c.decode(String.self, forKey: .status)
        model = try c.decode(String.self, forKey: .model)
        playbooksUsed = (try? c.decode([PlaybookUse].self, forKey: .playbooksUsed)) ?? []
        validation = try? c.decode(ValidationReport.self, forKey: .validation)
        error = try c.decode(String.self, forKey: .error)
        createdAt = try c.decode(String.self, forKey: .createdAt)
        result = try? c.decode(AnalysisResult.self, forKey: .result)  // empty {} while running
    }
}

// MARK: - Reports, playbooks, connectors

struct ReportVersion: Codable, Identifiable, Hashable {
    let id: String
    let analysisRunId: String
    let version: Int
    let status: String
    let filename: String
    let pageCount: Int
    let pageLimit: Int
    let templateKey: String
    let warnings: [String]
    let hasPdf: Bool
    let driveFileId: String
    let error: String
    let createdAt: String
}

struct Playbook: Codable, Identifiable, Hashable { let key: String; let name: String; let kind: String; let activeVersion: Int; var id: String { key } }
struct PlaybookVersion: Codable, Identifiable, Hashable { let version: Int; let contentYaml: String; let changeNote: String; let createdAt: String; var id: Int { version } }
struct Aspect: Codable, Identifiable, Hashable { let key: String; let name: String; let kind: String; var id: String { key } }
struct Connector: Codable, Identifiable, Hashable { let provider: String; let connected: Bool; let accountEmail: String; let configured: Bool; var id: String { provider } }
struct AuthorizeResponse: Codable { let authorizeUrl: String; let callbackScheme: String }
struct AuditEntry: Codable, Hashable { let at: String; let action: String }
struct AppConfig: Codable { let aiMode: String }
struct AgentTokenInfo: Codable, Identifiable, Hashable { let id: String; let name: String; let createdAt: String; let lastUsedAt: String? }
struct NewAgentToken: Codable { let id: String; let name: String; let token: String }

extension String {
    var humanized: String { replacingOccurrences(of: "_", with: " ").capitalized }
    /// Undoes `.convertFromSnakeCase`, which JSONDecoder also applies to `[String: _]` dictionary keys
    /// ("reports_ready" arrives as "reportsReady").
    var snakeCased: String {
        reduce(into: "") { out, ch in
            if ch.isUppercase { out += "_" + ch.lowercased() } else { out.append(ch) }
        }
    }
    /// "2026-03-14T10:22:01.123" -> "14 Mar 2026"
    var shortDate: String {
        let f = ISO8601DateFormatter(); f.formatOptions = [.withFullDate]
        guard count >= 10, let d = f.date(from: String(prefix(10))) else { return self }
        return d.formatted(date: .abbreviated, time: .omitted)
    }
}
