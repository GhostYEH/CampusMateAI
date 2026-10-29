import Foundation

/// Dynamic protocol fields (artifacts, graphs and provider payloads) retain their JSON types.
public enum JSONValue: Codable, Sendable, Equatable, Hashable {
    case object([String: JSONValue])
    case array([JSONValue])
    case string(String)
    case number(Double)
    case bool(Bool)
    case null

    public init(from decoder: any Decoder) throws {
        let value = try decoder.singleValueContainer()
        if value.decodeNil() { self = .null }
        else if let item = try? value.decode(Bool.self) { self = .bool(item) }
        else if let item = try? value.decode(Double.self) { self = .number(item) }
        else if let item = try? value.decode(String.self) { self = .string(item) }
        else if let item = try? value.decode([JSONValue].self) { self = .array(item) }
        else { self = .object(try value.decode([String: JSONValue].self)) }
    }

    public func encode(to encoder: any Encoder) throws {
        var value = encoder.singleValueContainer()
        switch self {
        case .object(let item): try value.encode(item)
        case .array(let item): try value.encode(item)
        case .string(let item): try value.encode(item)
        case .number(let item): try value.encode(item)
        case .bool(let item): try value.encode(item)
        case .null: try value.encodeNil()
        }
    }

    public init(data: Data) throws { self = try JSONDecoder().decode(Self.self, from: data) }
    public func encoded() throws -> Data { try JSONEncoder().encode(self) }
    public subscript(_ key: String) -> JSONValue { object?[key] ?? .null }
    public var object: [String: JSONValue]? { if case .object(let value) = self { value } else { nil } }
    public var array: [JSONValue]? { if case .array(let value) = self { value } else { nil } }
    public var string: String? {
        switch self {
        case .string(let value): value
        case .number(let value): value.isFinite && value.rounded() == value ? String(format: "%.0f", value) : String(value)
        default: nil
        }
    }
    public var bool: Bool? {
        switch self {
        case .bool(let value): value
        case .number(let value): value != 0
        default: nil
        }
    }
    public var double: Double? { if case .number(let value) = self { value } else { nil } }
    public var int: Int? { double.flatMap { $0.isFinite && $0 >= Double(Int.min) && $0 < Double(Int.max) ? Int($0) : nil } }
    public var text: String { string ?? "" }
    public var items: [JSONValue] { array ?? self["items"].array ?? [] }
    public var prettyPrinted: String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return (try? String(decoding: encoder.encode(self), as: UTF8.self)) ?? ""
    }
}

extension JSONValue: ExpressibleByStringLiteral, ExpressibleByIntegerLiteral, ExpressibleByBooleanLiteral, ExpressibleByDictionaryLiteral, ExpressibleByArrayLiteral {
    public init(stringLiteral value: String) { self = .string(value) }
    public init(integerLiteral value: Int) { self = .number(Double(value)) }
    public init(booleanLiteral value: Bool) { self = .bool(value) }
    public init(dictionaryLiteral elements: (String, JSONValue)...) { self = .object(Dictionary(elements, uniquingKeysWith: { _, last in last })) }
    public init(arrayLiteral elements: JSONValue...) { self = .array(elements) }
}

public extension String {
    var pathComponent: String {
        addingPercentEncoding(withAllowedCharacters: CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_~"))) ?? ""
    }
    var nonEmpty: String? { trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : self }
}
