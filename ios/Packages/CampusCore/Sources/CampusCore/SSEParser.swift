import Foundation

public struct SSEEvent: Sendable, Equatable {
    public let event: String
    public let data: String
    public let id: String?
    public init(event: String = "message", data: String, id: String? = nil) { self.event = event; self.data = data; self.id = id }
    public var json: JSONValue { (try? JSONValue(data: Data(data.utf8))) ?? .null }
}

public struct SSEParser: Sendable {
    private var buffer = Data()
    private var eventName = "message"
    private var dataLines: [String] = []
    private var eventID: String?
    public init() { }

    public mutating func feed(_ chunk: Data) -> [SSEEvent] {
        buffer.append(chunk)
        var result: [SSEEvent] = []
        while let newline = buffer.firstIndex(of: 10) {
            var lineData = buffer.prefix(upTo: newline)
            if lineData.last == 13 { lineData = lineData.dropLast() }
            let line = String(decoding: lineData, as: UTF8.self)
            buffer.removeSubrange(...newline)
            if line.isEmpty {
                if !dataLines.isEmpty { result.append(SSEEvent(event: eventName, data: dataLines.joined(separator: "\n"), id: eventID)) }
                eventName = "message"; dataLines = []
            } else if !line.hasPrefix(":") {
                let parts = line.split(separator: ":", maxSplits: 1, omittingEmptySubsequences: false)
                var value = parts.count == 2 ? String(parts[1]) : ""
                if value.hasPrefix(" ") { value.removeFirst() }
                switch String(parts[0]) {
                case "event": eventName = value.isEmpty ? "message" : value
                case "data": dataLines.append(value)
                case "id": if !value.contains("\0") { eventID = value }
                default: break
                }
            }
        }
        return result
    }
}
