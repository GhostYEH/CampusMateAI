import Foundation

public struct RecordCollection: Sendable {
    public private(set) var items: [JSONValue] = []
    public private(set) var nextPage = 1
    public private(set) var hasMore = false
    public private(set) var total = 0
    public init() { }

    public mutating func apply(_ page: RecordPage, reset: Bool) {
        if reset { items = []; nextPage = 1; hasMore = false; total = 0 }
        var positions: [String: Int] = [:]
        for (index, item) in items.enumerated() {
            if let id = item["id"].string?.nonEmpty { positions[id] = index }
        }
        let previousCount = items.count
        for item in page.items {
            if let id = item["id"].string?.nonEmpty {
                if let position = positions[id] { items[position] = item }
                else { positions[id] = items.count; items.append(item) }
            } else { items.append(item) }
        }
        let advanced = page.nextPage > nextPage
        nextPage = max(nextPage, page.nextPage); total = page.total
        hasMore = page.hasMore && !page.items.isEmpty && advanced && (reset || items.count > previousCount)
    }
}

public struct ImportReview: Sendable {
    public private(set) var drafts: [JSONValue]
    public init(json: JSONValue) {
        drafts = json["tasks"].items.map { item in
            var fields = item.object ?? [:]
            if fields["title"]?.string?.nonEmpty == nil { fields["title"] = item["task"] }
            if fields["description"] == nil { fields["description"] = item["task"] }
            if fields["selected"] == nil { fields["selected"] = .bool(item["actionable"].bool ?? true) }
            return .object(fields)
        }
    }
    public var selectedDrafts: [JSONValue] { drafts.filter { $0["selected"].bool == true && $0["title"].text.nonEmpty != nil } }
    public var hasInvalidSelection: Bool { drafts.contains { $0["selected"].bool == true && $0["title"].text.nonEmpty == nil } }
    public mutating func setSelected(_ value: Bool, at index: Int) { set(.bool(value), key: "selected", at: index) }
    public mutating func setTitle(_ value: String, at index: Int) { set(.string(value), key: "title", at: index) }
    public mutating func set(_ value: JSONValue, key: String, at index: Int) {
        guard drafts.indices.contains(index) else { return }
        var fields = drafts[index].object ?? [:]; fields[key] = value; drafts[index] = .object(fields)
    }
}
