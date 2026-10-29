import Foundation

extension APIClient {
    /// For screens that filter/group locally, a first-page subset is not a complete data source.
    public func allRecords(path: String, query: [String: String] = [:]) async throws -> [JSONValue] {
        var records = RecordCollection()
        let userID = currentSession?.user.id
        repeat {
            try Task.checkCancellation()
            guard currentSession?.user.id == userID else { throw CancellationError() }
            var parameters = query
            parameters["page"] = String(records.nextPage)
            parameters["page_size"] = "100"
            let page = try RecordPage(json: await request(path: path, query: parameters))
            guard currentSession?.user.id == userID else { throw CancellationError() }
            records.apply(page, reset: records.nextPage == 1)
        } while records.hasMore
        return records.items
    }
}
