import SwiftUI
import CampusCore

@MainActor @Observable
final class PagedResource {
    private(set) var collection = RecordCollection()
    var isLoading = false
    var error: String?
    var items: [JSONValue] { collection.items }
    var hasMore: Bool { collection.hasMore }
    private var requestID = UUID()
    private var queryIdentity = ""

    func load(client: APIClient, path: String, query: [String: String] = [:], reset: Bool = true) async {
        let identity = key(path: path, query: query)
        if !reset && (isLoading || identity != queryIdentity) { return }
        let id = UUID(); requestID = id; queryIdentity = identity
        isLoading = true; error = nil
        defer { if requestID == id { isLoading = false } }
        var parameters = query
        parameters["page"] = String(reset ? 1 : collection.nextPage)
        parameters["page_size"] = parameters["page_size"] ?? "50"
        do {
            let result = try await client.request(path: path, query: parameters)
            let page = try RecordPage(json: result)
            guard !Task.isCancelled, requestID == id else { return }
            collection.apply(page, reset: reset)
        } catch is CancellationError { }
        catch { if requestID == id { self.error = error.localizedDescription } }
    }

    func loadRemaining(client: APIClient, path: String, query: [String: String] = [:]) async {
        let identity = key(path: path, query: query)
        while !Task.isCancelled && hasMore && error == nil && !isLoading && queryIdentity == identity {
            await load(client: client, path: path, query: query, reset: false)
        }
    }
    private func key(path: String, query: [String: String]) -> String { path + query.sorted { $0.key < $1.key }.map { "\($0.key)=\($0.value)" }.joined(separator: "&") }
}

struct PagedStatusView: View {
    let resource: PagedResource
    var emptyTitle = "暂无内容"
    var emptyMessage = "新的内容会显示在这里。"
    var icon = "tray"
    var retry: (() async -> Void)?

    var body: some View {
        if resource.items.isEmpty && resource.isLoading { ProgressView("正在加载…").frame(maxWidth: .infinity).padding(24) }
        else if let error = resource.error {
            ContentUnavailableView {
                Label("暂时无法加载", systemImage: "wifi.exclamationmark")
            } description: { Text(error) } actions: {
                if let retry { Button("重试") { Task { await retry() } }.buttonStyle(.bordered) }
            }
        } else if resource.items.isEmpty { ContentUnavailableView(emptyTitle, systemImage: icon, description: Text(emptyMessage)) }
    }
}

struct LoadMoreRow: View {
    let resource: PagedResource
    let action: () async -> Void
    var body: some View {
        if resource.hasMore {
            Button { Task { await action() } } label: {
                HStack { Spacer(); if resource.isLoading { ProgressView() } else { Text("加载更多") }; Spacer() }
            }.disabled(resource.isLoading)
        }
    }
}
