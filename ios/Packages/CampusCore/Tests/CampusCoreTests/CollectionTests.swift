import Testing
@testable import CampusCore

@Suite("Collection and confirmation semantics")
struct CollectionTests {
    @Test func paginationUpdatesDuplicateRecordWithoutDuplicatingRows() throws {
        var records = RecordCollection()
        records.apply(try RecordPage(json: ["items": [["id": "one", "title": "old"]], "page": 1, "has_more": true]), reset: true)
        records.apply(try RecordPage(json: ["items": [["id": "one", "title": "new"], ["id": "two", "title": "two"]], "page": 2, "has_more": false]), reset: false)
        #expect(records.items.count == 2)
        #expect(records.items.first?["title"].text == "new")
        #expect(records.nextPage == 3)
        #expect(!records.hasMore)
    }

    @Test func emptyPageCannotCauseInfinitePagination() throws {
        var records = RecordCollection()
        records.apply(try RecordPage(json: ["items": [], "page": 1, "has_more": true]), reset: true)
        #expect(!records.hasMore)
    }

    @Test func importOnlySendsExplicitlySelectedDrafts() {
        var review = ImportReview(json: ["tasks": [["title": "保留", "selected": true], ["title": "忽略", "selected": false]]])
        #expect(review.selectedDrafts.count == 1)
        review.setTitle("修改后的标题", at: 0)
        #expect(review.selectedDrafts.first?["title"].text == "修改后的标题")
        review.setSelected(false, at: 0)
        #expect(review.selectedDrafts.isEmpty)
    }
}
