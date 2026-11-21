import Foundation

// MARK: - Colour

/// 课件里的颜色按 CSS 语法出现（`#153B34` / `rgb(21, 59, 52)` / `rgba(...)`）。
/// 解析失败返回 nil，渲染层退回默认色，绝不猜一个不同的颜色。
public struct ClassroomColor: Sendable, Equatable {
    public let red: Double
    public let green: Double
    public let blue: Double
    public let alpha: Double

    public init(red: Double, green: Double, blue: Double, alpha: Double = 1) {
        self.red = min(max(red, 0), 1)
        self.green = min(max(green, 0), 1)
        self.blue = min(max(blue, 0), 1)
        self.alpha = min(max(alpha, 0), 1)
    }

    public init?(css: String) {
        let text = css.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !text.isEmpty else { return nil }
        if text.hasPrefix("#") {
            let hex = String(text.dropFirst())
            guard let value = Self.hex(hex) else { return nil }
            self = value
            return
        }
        if text.hasPrefix("rgb") {
            guard let open = text.firstIndex(of: "("), let close = text.lastIndex(of: ")"), open < close else { return nil }
            let body = text[text.index(after: open)..<close]
            let parts = body.split(whereSeparator: { $0 == "," || $0 == "/" }).map { $0.trimmingCharacters(in: .whitespaces) }
            guard parts.count == 3 || parts.count == 4,
                  let red = Self.channel(parts[0]), let green = Self.channel(parts[1]), let blue = Self.channel(parts[2])
            else { return nil }
            let alpha = parts.count == 4 ? (Double(parts[3]) ?? 1) : 1
            self.init(red: red, green: green, blue: blue, alpha: alpha)
            return
        }
        switch text {
        case "black": self.init(red: 0, green: 0, blue: 0)
        case "white": self.init(red: 1, green: 1, blue: 1)
        case "transparent": self.init(red: 0, green: 0, blue: 0, alpha: 0)
        case "gray", "grey": self.init(red: 0.5, green: 0.5, blue: 0.5)
        default: return nil
        }
    }

    private static func hex(_ value: String) -> ClassroomColor? {
        let scalars = Array(value)
        func component(_ pair: String) -> Double? {
            guard let number = UInt8(pair, radix: 16) else { return nil }
            return Double(number) / 255
        }
        switch scalars.count {
        case 3, 4:
            let expanded = scalars.map { "\($0)\($0)" }
            guard let red = component(String(expanded[0])),
                  let green = component(String(expanded[1])),
                  let blue = component(String(expanded[2]))
            else { return nil }
            let alpha = expanded.count == 4 ? component(String(expanded[3])) ?? 1 : 1
            return ClassroomColor(red: red, green: green, blue: blue, alpha: alpha)
        case 6, 8:
            guard let red = component(String(scalars[0...1])),
                  let green = component(String(scalars[2...3])),
                  let blue = component(String(scalars[4...5]))
            else { return nil }
            let alpha = scalars.count == 8 ? component(String(scalars[6...7])) ?? 1 : 1
            return ClassroomColor(red: red, green: green, blue: blue, alpha: alpha)
        default:
            return nil
        }
    }

    private static func channel(_ text: String) -> Double? {
        if text.hasSuffix("%"), let value = Double(text.dropLast()) { return value / 100 }
        guard let value = Double(text) else { return nil }
        return value > 1 ? value / 255 : value
    }
}

// MARK: - Geometry

public struct ClassroomRect: Sendable, Equatable {
    public let x: Double
    public let y: Double
    public let width: Double
    public let height: Double

    public init(x: Double, y: Double, width: Double, height: Double) {
        self.x = x
        self.y = y
        self.width = max(0, width)
        self.height = max(0, height)
    }

    public var centerX: Double { x + width / 2 }
    public var centerY: Double { y + height / 2 }
}

public enum ClassroomTextAlignment: String, Sendable, Equatable {
    case leading
    case center
    case trailing
    case justified

    public init(style: String?) {
        switch style?.lowercased() {
        case "center": self = .center
        case "right", "end": self = .trailing
        case "justify": self = .justified
        default: self = .leading
        }
    }
}

public enum ClassroomVerticalAlignment: String, Sendable, Equatable {
    case top
    case middle
    case bottom
}

// MARK: - Rich text

public struct ClassroomTextStyle: Sendable, Equatable {
    public var fontSize: Double
    public var bold: Bool
    public var color: ClassroomColor?
    public var alignment: ClassroomTextAlignment
    public var lineHeight: Double
    public var isHeading: Bool

    public init(fontSize: Double, bold: Bool = false, color: ClassroomColor? = nil,
                alignment: ClassroomTextAlignment = .leading, lineHeight: Double = 1.4, isHeading: Bool = false) {
        self.fontSize = fontSize
        self.bold = bold
        self.color = color
        self.alignment = alignment
        self.lineHeight = lineHeight
        self.isHeading = isHeading
    }
}

public struct ClassroomParagraph: Sendable, Equatable, Identifiable {
    public let id: Int
    public let text: String
    public let style: ClassroomTextStyle
    public let marker: String?

    public var accessibilityText: String { marker.map { "\($0) \(text)" } ?? text }
}

/// 课件正文是画布里的 HTML 片段。原生渲染只保留真正影响阅读的排版：
/// 段落、列表、换行、字号、颜色、粗细、对齐和行高；其余标签被忽略。
public enum ClassroomRichTextParser {
    private enum ListMode { case none, bullet, ordered }

    public static func parse(html: String, baseFontSize: Double, baseColor: ClassroomColor?,
                             baseLineHeight: Double = 1.4, baseAlignment: ClassroomTextAlignment = .leading) -> [ClassroomParagraph] {
        var paragraphs: [ClassroomParagraph] = []
        var buffer = ""
        var style = ClassroomTextStyle(fontSize: baseFontSize, color: baseColor, alignment: baseAlignment, lineHeight: baseLineHeight)
        var listMode: ListMode = .none
        var orderedIndex = 0
        var boldDepth = 0
        var marker: String?
        var isHeading = false
        var characterBudget = 6000

        func flush() {
            var text = normalize(buffer)
            buffer = ""
            if text.isEmpty { return }
            if text.count > characterBudget { text = String(text.prefix(characterBudget)) }
            characterBudget -= text.count
            var resolved = style
            resolved.bold = resolved.bold || boldDepth > 0
            resolved.isHeading = isHeading
            paragraphs.append(ClassroomParagraph(id: paragraphs.count, text: text, style: resolved, marker: marker))
        }

        func beginBlock(attributes: String, forcedHeading: Bool) {
            flush()
            style = baseStyle(attributes: attributes, fallback: ClassroomTextStyle(
                fontSize: baseFontSize, color: baseColor, alignment: baseAlignment, lineHeight: baseLineHeight))
            isHeading = forcedHeading
            if forcedHeading { style.bold = true }
        }

        var index = html.startIndex
        while index < html.endIndex {
            guard let open = html[index...].firstIndex(of: "<") else {
                buffer.append(contentsOf: html[index...])
                break
            }
            if open > index { buffer.append(contentsOf: html[index..<open]) }
            guard let close = html[open...].firstIndex(of: ">") else {
                buffer.append(contentsOf: html[open...])
                break
            }
            let rawTag = String(html[html.index(after: open)..<close])
            index = html.index(after: close)
            guard let tag = Tag(raw: rawTag) else { continue }
            switch tag.name {
            case "br":
                buffer.append("\n")
            case "p", "div":
                if tag.isClosing { flush() } else { beginBlock(attributes: tag.attributes, forcedHeading: false) }
            case "h1", "h2", "h3", "h4", "h5", "h6":
                if tag.isClosing { flush() } else { beginBlock(attributes: tag.attributes, forcedHeading: true) }
            case "ul":
                flush(); listMode = tag.isClosing ? .none : .bullet; orderedIndex = 0
            case "ol":
                flush(); listMode = tag.isClosing ? .none : .ordered; orderedIndex = 0
            case "li":
                if tag.isClosing {
                    flush(); marker = nil; style = baseStyle(attributes: "", fallback: ClassroomTextStyle(
                        fontSize: baseFontSize, color: baseColor, alignment: baseAlignment, lineHeight: baseLineHeight))
                    isHeading = false
                } else {
                    flush()
                    style = baseStyle(attributes: tag.attributes, fallback: ClassroomTextStyle(
                        fontSize: baseFontSize, color: baseColor, alignment: baseAlignment, lineHeight: baseLineHeight))
                    isHeading = false
                    if listMode == .ordered {
                        orderedIndex += 1
                        marker = "\(orderedIndex)."
                    } else {
                        marker = "•"
                    }
                }
            case "strong", "b":
                boldDepth = tag.isClosing ? max(0, boldDepth - 1) : boldDepth + 1
            default:
                continue
            }
        }
        flush()
        return paragraphs
    }

    public static func plainText(_ paragraphs: [ClassroomParagraph]) -> String {
        paragraphs.map(\.accessibilityText).joined(separator: "\n")
    }

    private static func baseStyle(attributes: String, fallback: ClassroomTextStyle) -> ClassroomTextStyle {
        var style = fallback
        style.bold = false
        guard let raw = attribute(named: "style", in: attributes) else { return style }
        for declaration in raw.split(separator: ";") {
            let pair = declaration.split(separator: ":", maxSplits: 1).map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            guard pair.count == 2 else { continue }
            let key = pair[0].lowercased()
            let value = pair[1].lowercased()
            switch key {
            case "font-size":
                if let size = fontSize(value) { style.fontSize = size }
            case "color":
                if let color = ClassroomColor(css: value) { style.color = color }
            case "font-weight":
                if value == "bold" || value == "bolder" || (Int(value) ?? 0) >= 600 { style.bold = true }
            case "text-align":
                style.alignment = ClassroomTextAlignment(style: value)
            case "line-height":
                if let height = Double(value), height > 0.9, height < 3 { style.lineHeight = height }
            default:
                continue
            }
        }
        return style
    }

    private static func fontSize(_ value: String) -> Double? {
        if value.hasSuffix("px"), let size = Double(value.dropLast(3)), size > 0 { return min(size, 220) }
        if value.hasSuffix("em"), let size = Double(value.dropLast(2)), size > 0 { return min(size * 16, 220) }
        if value.hasSuffix("pt"), let size = Double(value.dropLast(2)), size > 0 { return min(size * 4 / 3, 220) }
        if let size = Double(value), size > 0 { return min(size, 220) }
        return nil
    }

    private static func attribute(named name: String, in attributes: String) -> String? {
        guard let range = attributes.range(of: name + "=", options: [.caseInsensitive]) else { return nil }
        var rest = attributes[range.upperBound...]
        while rest.first == " " { rest = rest.dropFirst() }
        guard let quote = rest.first, quote == "\"" || quote == "'" else {
            let value = rest.prefix { !$0.isWhitespace }
            return value.isEmpty ? nil : String(value)
        }
        rest = rest.dropFirst()
        guard let end = rest.firstIndex(of: quote) else { return nil }
        return String(rest[..<end])
    }

    private static func normalize(_ text: String) -> String {
        var value = decodeEntities(text.replacingOccurrences(of: "\u{00A0}", with: " "))
        while value.contains("  ") { value = value.replacingOccurrences(of: "  ", with: " ") }
        value = value.split(separator: "\n", omittingEmptySubsequences: false)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .joined(separator: "\n")
        return value.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func decodeEntities(_ text: String) -> String {
        var value = text
        let named: [String: String] = [
            "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": "\"",
            "&#39;": "'", "&apos;": "'", "&mdash;": "—", "&ndash;": "–", "&hellip;": "…",
            "&times;": "×", "&divide;": "÷", "&le;": "≤", "&ge;": "≥", "&middot;": "·",
        ]
        for (entity, replacement) in named { value = value.replacingOccurrences(of: entity, with: replacement) }
        parseNumericEntities(&value)
        return value
    }

    private static func parseNumericEntities(_ text: inout String) {
        var result = ""
        var index = text.startIndex
        while let start = text[index...].range(of: "&#")?.lowerBound {
            result.append(contentsOf: text[index..<start])
            let rest = text[text.index(after: start)...]
            guard let semicolon = rest.firstIndex(of: ";") else {
                result.append(contentsOf: text[start...])
                text = result
                return
            }
            let body = rest[..<semicolon]
            var scalarValue: UInt32?
            if body.hasPrefix("x") || body.hasPrefix("X") {
                scalarValue = UInt32(body.dropFirst(), radix: 16)
            } else {
                scalarValue = UInt32(body, radix: 10)
            }
            if let scalarValue, let scalar = Unicode.Scalar(scalarValue) {
                result.append(Character(scalar))
            } else {
                result.append(contentsOf: text[start...semicolon])
            }
            index = text.index(after: semicolon)
        }
        result.append(contentsOf: text[index...])
        text = result
    }

    private struct Tag {
        let name: String
        let attributes: String
        let isClosing: Bool

        init?(raw: String) {
            let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty, !trimmed.hasPrefix("!"), !trimmed.hasPrefix("?") else { return nil }
            var body = trimmed
            let closing = body.hasPrefix("/")
            if closing { body = String(body.dropFirst()) }
            if body.hasSuffix("/") { body = String(body.dropLast()) }
            let nameEnd = body.firstIndex { $0.isWhitespace } ?? body.endIndex
            let name = body[..<nameEnd].lowercased()
            guard !name.isEmpty, name.first?.isLetter == true else { return nil }
            self.name = name
            self.attributes = String(body[nameEnd...])
            self.isClosing = closing
        }
    }
}

// MARK: - Canvas

public struct ClassroomCanvas: Sendable, Equatable {
    public struct TextElement: Sendable, Equatable, Identifiable {
        public let id: String
        public let frame: ClassroomRect
        public let rotate: Double
        public let paragraphs: [ClassroomParagraph]
        public let verticalAlignment: ClassroomVerticalAlignment

        public var plainText: String { ClassroomRichTextParser.plainText(paragraphs) }
    }

    public struct ShapeElement: Sendable, Equatable, Identifiable {
        public let id: String
        public let frame: ClassroomRect
        public let rotate: Double
        public let fill: ClassroomColor?
        public let stroke: ClassroomColor?
        public let strokeWidth: Double
        public let cornerRadius: Double
    }

    public struct ImageElement: Sendable, Equatable, Identifiable {
        public let id: String
        public let frame: ClassroomRect
        public let rotate: Double
        public let data: Data?
        /// 经典课堂会把媒体改写成站内相对地址；必须走已鉴权的 APIClient 下载，
        /// 不能把地址直接交给 UIImage 或第三方图片库。
        public let source: String?
        public let alt: String

        public var hasImage: Bool { data != nil || source?.isEmpty == false }
    }

    /// 经典课件里的音频元素。`source` 只保留本站相对地址；外链或缺失资源保持 nil，
    /// 由界面显示实际状态，不把地址直接交给系统播放器。
    public struct AudioElement: Sendable, Equatable, Identifiable {
        public let id: String
        public let frame: ClassroomRect
        public let rotate: Double
        public let source: String?
        public let contentType: String
        public let title: String

        public var isPlayable: Bool { source != nil }
    }

    public struct VideoElement: Sendable, Equatable, Identifiable {
        public let id: String
        public let frame: ClassroomRect
        public let rotate: Double
        public let source: String?
        public let contentType: String
        public let title: String

        public var isPlayable: Bool { source != nil }
    }

    public enum Element: Sendable, Equatable, Identifiable {
        case text(TextElement)
        case shape(ShapeElement)
        case image(ImageElement)
        case audio(AudioElement)
        case video(VideoElement)
        case unknown(id: String, type: String)

        public var id: String {
            switch self {
            case .text(let item): item.id
            case .shape(let item): item.id
            case .image(let item): item.id
            case .audio(let item): item.id
            case .video(let item): item.id
            case .unknown(let id, _): id
            }
        }
    }

    public let width: Double
    public let height: Double
    public let background: ClassroomColor?
    public let backgroundGradient: [ClassroomColor]
    public let usesStockTemplate: Bool
    public let elements: [Element]

    public init?(json: JSONValue) {
        guard json.object != nil else { return nil }
        self.width = json["width"].double ?? 1000
        self.height = json["height"].double ?? 562.5
        let background = json["background"]
        let color = background["color"].string?.nonEmpty ?? json["theme"]["backgroundColor"].string?.nonEmpty
            ?? json["backgroundColor"].string ?? ""
        self.background = ClassroomColor(css: color)
        let gradient = (background["gradient"]["colors"].array ?? []).compactMap(\.string)
        self.backgroundGradient = gradient.compactMap { ClassroomColor(css: $0) }
        let rawElements = json["elements"].array ?? []
        self.usesStockTemplate = color.lowercased() == "#ffffff"
            && json["theme"]["fontColor"].string?.lowercased() == "#1f2937"
            && background["image"]["src"].string?.nonEmpty == nil && gradient.isEmpty
            && rawElements.contains { $0["id"].string == "el_title" && $0["type"].string == "text" }
            && rawElements.contains {
                $0["id"].string == "el_accent" && $0["type"].string == "shape"
                    && $0["fill"].string?.lowercased() == "#722ed1"
            }
        self.elements = rawElements.enumerated().map { index, raw in
            Self.element(raw, index: index)
        }
    }

    private static func element(_ json: JSONValue, index: Int) -> Element {
        let rawID = json["id"].string?.nonEmpty ?? "element-\(index)"
        let id = "\(index):\(rawID)"
        let frame = ClassroomRect(x: json["left"].double ?? 0, y: json["top"].double ?? 0,
                                  width: json["width"].double ?? 0, height: json["height"].double ?? 0)
        let rotate = json["rotate"].double ?? 0
        switch json["type"].string ?? "" {
        case "text":
            let paragraphs = ClassroomRichTextParser.parse(
                html: json["content"].string ?? "",
                baseFontSize: json["fontSize"].double ?? 32,
                baseColor: ClassroomColor(css: json["defaultColor"].string ?? ""),
                baseLineHeight: json["lineHeight"].double ?? 1.4)
            return .text(TextElement(id: id, frame: frame, rotate: rotate, paragraphs: paragraphs,
                                     verticalAlignment: ClassroomVerticalAlignment(rawValue: json["vAlign"].string ?? "") ?? .top))
        case "shape":
            return .shape(ShapeElement(id: id, frame: frame, rotate: rotate,
                                       fill: ClassroomColor(css: json["fill"].string ?? ""),
                                       stroke: ClassroomColor(css: json["outline"]["color"].string ?? ""),
                                       strokeWidth: max(0, json["outline"]["width"].double ?? 0),
                                       cornerRadius: json["radius"].double
                                           ?? ClassroomShapeGeometry.cornerRadius(path: json["path"].string ?? "")))
        case "image":
            let rawSource = json["dataUri"].string ?? json["src"].string ?? ""
            let data = ClassroomImageData.decode(dataURI: rawSource)
            let source = data == nil ? (json["src"].string?.nonEmpty ?? json["dataUri"].string?.nonEmpty) : nil
            return .image(ImageElement(id: id, frame: frame, rotate: rotate, data: data,
                                       source: source, alt: json["alt"].string ?? "课堂图片"))
        case "audio":
            let raw = json["src"].string?.nonEmpty ?? json["dataUri"].string?.nonEmpty
            let contentType = json["contentType"].string ?? json["mimeType"].string ?? ""
            let source = raw.flatMap { rawSource -> String? in
                guard ClassroomMediaReference.apiPath(from: rawSource) != nil else { return nil }
                return ClassroomMediaReference.isAudio(contentType: contentType, path: rawSource) ? rawSource : nil
            }
            return .audio(AudioElement(id: id, frame: frame, rotate: rotate, source: source,
                                      contentType: contentType,
                                      title: json["title"].string?.nonEmpty ?? "课堂音频"))
        case "video":
            let raw = json["src"].string?.nonEmpty ?? json["dataUri"].string?.nonEmpty
            let contentType = json["contentType"].string ?? json["mimeType"].string ?? ""
            let source = raw.flatMap { rawSource -> String? in
                guard ClassroomMediaReference.apiPath(from: rawSource) != nil else { return nil }
                return ClassroomMediaReference.isVideo(contentType: contentType, path: rawSource) ? rawSource : nil
            }
            return .video(VideoElement(id: id, frame: frame, rotate: rotate, source: source,
                                      contentType: contentType,
                                      title: json["title"].string?.nonEmpty ?? "课堂视频"))
        default:
            return .unknown(id: id, type: json["type"].string ?? "unknown")
        }
    }

    public var isEmpty: Bool { elements.isEmpty }
}

public enum ClassroomShapeGeometry {
    /// 参考渲染器用 `A r r 0 0 1 ...` 画圆角矩形；取第一个圆弧半径作为 SwiftUI 圆角。
    public static func cornerRadius(path: String) -> Double {
        let tokens = path.split(whereSeparator: { $0 == " " || $0 == "," })
        guard let arc = tokens.firstIndex(where: { $0.uppercased() == "A" }), tokens.count > arc + 2,
              let radius = Double(tokens[arc + 1]), radius.isFinite, radius > 0
        else { return 12 }
        return min(radius, 120)
    }
}

public enum ClassroomImageData {
    public static let byteLimit = 6 * 1024 * 1024

    /// `data:image/png;base64,...`。只接受位图 MIME 且限制体积，避免一个课件把内存吃满。
    public static func decode(dataURI: String) -> Data? {
        let trimmed = dataURI.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.lowercased().hasPrefix("data:"),
              let comma = trimmed.firstIndex(of: ",")
        else { return nil }
        let header = trimmed[trimmed.startIndex..<comma].lowercased()
        guard header.contains(";base64"), header.contains("image/") else { return nil }
        let payload = String(trimmed[trimmed.index(after: comma)...])
        guard payload.count <= byteLimit * 2, let data = Data(base64Encoded: payload, options: [.ignoreUnknownCharacters]),
              !data.isEmpty, data.count <= byteLimit
        else { return nil }
        return data
    }
}

// MARK: - Readable outline

/// 历史文档可能只有可读的 `slide` 源，没有画布元素。Outline 是原生播放的兜底版面，
/// 它读的是同一份内容，不额外编造要点。
public struct ClassroomSlideOutline: Sendable, Equatable {
    public struct Section: Sendable, Equatable, Identifiable {
        public let id: Int
        public let heading: String?
        public let bullets: [String]
    }

    public struct Comparison: Sendable, Equatable {
        public let left: Section
        public let right: Section
    }

    public let title: String
    public let subtitle: String?
    public let bullets: [String]
    public let sections: [Section]
    public let toc: [String]
    public let comparison: Comparison?
    public let conclusion: String?
    public let layout: String

    public static let empty = ClassroomSlideOutline(title: "", subtitle: nil, bullets: [], sections: [], toc: [],
                                                    comparison: nil, conclusion: nil, layout: "")

    public init(title: String, subtitle: String?, bullets: [String], sections: [Section], toc: [String],
                comparison: Comparison?, conclusion: String?, layout: String) {
        self.title = title
        self.subtitle = subtitle
        self.bullets = bullets
        self.sections = sections
        self.toc = toc
        self.comparison = comparison
        self.conclusion = conclusion
        self.layout = layout
    }

    public init(json: JSONValue) {
        let title = json["title"].string?.nonEmpty ?? ""
        var sections = (json["sections"].array ?? []).enumerated().compactMap { index, raw -> Section? in
            let heading = raw["heading"].string?.nonEmpty
            let bullets = raw["bullets"].array?.compactMap(\.string) ?? []
            guard heading != nil || !bullets.isEmpty else { return nil }
            return Section(id: index, heading: heading, bullets: bullets)
        }
        if sections.isEmpty, let singleHeading = json["heading"].string?.nonEmpty {
            sections = [Section(id: 0, heading: singleHeading, bullets: json["bullets"].array?.compactMap(\.string) ?? [])]
        }
        var comparison: Comparison?
        if let raw = json["comparison"].object {
            let leftJSON = [raw["left"], raw["0"]].first { $0 != .null } ?? .null
            let rightJSON = [raw["right"], raw["1"]].first { $0 != .null } ?? .null
            let left = Self.section(leftJSON, index: 0)
            let right = Self.section(rightJSON, index: 1)
            if left != nil || right != nil {
                comparison = Comparison(left: left ?? Section(id: 0, heading: nil, bullets: []),
                                        right: right ?? Section(id: 1, heading: nil, bullets: []))
            }
        }
        self.init(title: title,
                  subtitle: json["subtitle"].string?.nonEmpty ?? json["description"].string?.nonEmpty,
                  bullets: json["bullets"].array?.compactMap(\.string) ?? [],
                  sections: sections,
                  toc: json["toc"].array?.compactMap(\.string) ?? [],
                  comparison: comparison,
                  conclusion: json["conclusion"].string?.nonEmpty,
                  layout: json["layout"].string?.nonEmpty ?? "")
    }

    private static func section(_ json: JSONValue, index: Int) -> Section? {
        let heading = json["heading"].string?.nonEmpty
        let bullets = json["bullets"].array?.compactMap(\.string) ?? []
        guard heading != nil || !bullets.isEmpty else { return nil }
        return Section(id: index, heading: heading, bullets: bullets)
    }

    public var isEmpty: Bool {
        title.isEmpty && subtitle == nil && bullets.isEmpty && sections.isEmpty && toc.isEmpty
            && comparison == nil && conclusion == nil
    }
}

public struct ClassroomSlide: Sendable, Equatable {
    public let canvas: ClassroomCanvas?
    public let outline: ClassroomSlideOutline

    public init(json: JSONValue) {
        self.canvas = ClassroomCanvas(json: json["canvas"])
        self.outline = ClassroomSlideOutline(json: json["slide"].object == nil ? json : json["slide"])
    }

    public var prefersCanvas: Bool { canvas?.isEmpty == false }
    public var isEmpty: Bool { !prefersCanvas && outline.isEmpty }
}
