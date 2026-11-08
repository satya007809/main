import XCTest
@testable import BharatiDesk

/// Decodes JSON in the exact shape produced by the backend (see backend/tests) to catch API drift.
final class ModelDecodingTests: XCTestCase {
    let decoder: JSONDecoder = { let d = JSONDecoder(); d.keyDecodingStrategy = .convertFromSnakeCase; return d }()

    func testAnalysisRunDecodes() throws {
        let json = """
        {"id":"a1","run_no":2,"status":"completed","model":"claude-opus-5-5",
         "playbooks_used":[{"key":"global_rules","version":1},{"key":"own_damage","version":3}],
         "document_refs":["D001"],"note_refs":[],"error":"","created_at":"2026-03-20T10:00:00",
         "validation":{"errors":[],"warnings":["Policy wording not supplied"],"ok":true},
         "result":{"case_summary":"s","detected_aspects":[{"key":"close_proximity","reason":"r"}],
           "findings":[{"id":"F1","category":"verified_fact","statement":"x","sources":[{"ref":"D001","page":1}],"significance":"material"}],
           "chronology":[{"date":"14.03.2026","time":"22:30","event":"e","sources":[],"certainty":"stated"}],
           "discrepancies":[{"id":"X1","point":"p","version_a":"a","sources_a":[{"ref":"D001","page":1}],"version_b":"b","sources_b":[{"ref":"D002","page":1}],"significance":"material","resolution":""}],
           "checklist":[{"item_id":"rc","label":"RC","status":"available","refs":["D002"],"remarks":""}],
           "question_answers":[],"photo_observations":[{"ref":"D004","observation":"o","metadata_note":"m"}],
           "external_checks":[{"source":"fastag","status":"pending","basis_refs":[],"remarks":""}],
           "pending_verifications":[{"item":"i","reason":"r","impact":"could_change_opinion"}],
           "policy_analysis":{"wording_available":false,"clauses":[{"clause_ref":"c","quoted_text":"q","sources":[],"application":"a"}],"coverage_position":"p"},
           "anomalies":[],"opinion":{"verdict":"insufficient_evidence","summary":"s","decisive_evidence":[{"point":"p","sources":[{"ref":"D001","page":1}]}],"limitations":["l"]}}}
        """
        let run = try decoder.decode(AnalysisRun.self, from: Data(json.utf8))
        XCTAssertEqual(run.result?.discrepancies.first?.sourcesB.first?.ref, "D002")
        XCTAssertEqual(run.result?.opinion.verdictTitle, "Evidence insufficient for a reliable conclusion")
        XCTAssertEqual(run.playbooksUsed.last?.version, 3)
    }

    func testRunningAnalysisWithEmptyResult() throws {
        let json = #"{"id":"a","run_no":1,"status":"running","model":"","playbooks_used":[],"validation":{},"error":"","created_at":"x","result":{}}"#
        let run = try decoder.decode(AnalysisRun.self, from: Data(json.utf8))
        XCTAssertNil(run.result)
    }

    func testInvoiceRoundTripFromCaseRecord() throws {
        let dict: [String: JSONValue] = ["invoiceNumber": .string("BI/1"), "items": .array([.object(["description": .string("Fee"), "amount": .number(6000)])])]
        let inv = EditCaseView.invoice(from: dict)
        XCTAssertEqual(inv.invoiceNumber, "BI/1")
        XCTAssertEqual(inv.items.first?.amount, 6000)
        XCTAssertEqual(inv.billTo, "")
    }
}
