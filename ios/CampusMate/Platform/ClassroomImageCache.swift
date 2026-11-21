import Observation
import SwiftUI
import UIKit
import CampusCore

/// 画布图片缓存：内联 data URI 在后台解码，经典课堂的站内媒体地址走
/// 已鉴权的 APIClient 下载。按「账号+舞台+场景+元素」索引，总字节受限。
@MainActor
@Observable
final class ClassroomImageCache {
    static let shared = ClassroomImageCache()

    /// 视图在 body 里读取图片缓存时，后台解码完成会通过这个版本号触发重绘。
    private(set) var revision = 0
    private let cache = NSCache<NSString, UIImage>()
    @ObservationIgnored private var preloadTask: Task<Void, Never>?

    private init() {
        cache.totalCostLimit = 48 * 1024 * 1024
        cache.countLimit = 300
    }

    /// `scope` 必须包含账号、课程、工作台与舞台；scene id 只在舞台内唯一，
    /// 跨课堂复用 key 会把别的课件图片画到当前页。
    func image(sceneID: String, element: ClassroomCanvas.ImageElement, scope: String = "") -> UIImage? {
        _ = revision
        guard element.data != nil || element.source?.isEmpty == false else { return nil }
        let key = classroomImageCacheKey(scope: scope, sceneID: sceneID, elementID: element.id) as NSString
        return cache.object(forKey: key)
    }

    /// 邻页图片在后台解码，主线程只接收成品；翻页时不再做同步解码。
    func preload(sceneID: String, canvas: ClassroomCanvas, scope: String = "", client: APIClient? = nil, mediaBasePath: String? = nil) {
        let cachedKey: (String) -> NSString = { id in
            classroomImageCacheKey(scope: scope, sceneID: sceneID, elementID: id) as NSString
        }
        let pending: [PendingImage] = canvas.elements.compactMap { element in
            guard case .image(let image) = element,
                  image.data != nil || image.source?.isEmpty == false,
                  cache.object(forKey: cachedKey(image.id)) == nil
            else { return nil }
            return PendingImage(id: image.id, data: image.data, source: image.source)
        }
        guard !pending.isEmpty else { return }
        preloadTask?.cancel()
        preloadTask = Task.detached(priority: .utility) { [weak self] in
            for item in pending {
                if Task.isCancelled { return }
                var decoded: UIImage?
                var byteCount = 0
                if let data = item.data {
                    decoded = UIImage(data: data)
                    byteCount = data.count
                } else if let source = item.source, let client,
                          let path = classroomMediaPath(source, mediaBasePath: mediaBasePath),
                          let resource = try? await client.download(path: path) {
                    if Task.isCancelled {
                        try? FileManager.default.removeItem(at: resource.url)
                        return
                    }
                    let size = (try? resource.url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0
                    if size > 0, size <= 6 * 1024 * 1024,
                       let data = try? Data(contentsOf: resource.url) {
                        decoded = UIImage(data: data)
                        byteCount = data.count
                    }
                    try? FileManager.default.removeItem(at: resource.url)
                }
                guard let image = decoded else { continue }
                let boxed = SendableImage(image: image)
                let key = classroomImageCacheKey(scope: scope, sceneID: sceneID, elementID: item.id)
                await MainActor.run {
                    guard let self, !Task.isCancelled else { return }
                    self.cache.setObject(boxed.image, forKey: key as NSString, cost: byteCount)
                    self.revision &+= 1
                }
            }
        }
    }

    /// 翻页/退出时丢弃仍在进行或排队的邻页预取。
    func cancelPreloads() {
        preloadTask?.cancel()
        preloadTask = nil
    }

    func removeAll() {
        cancelPreloads()
        cache.removeAllObjects()
    }

}

/// `UIImage` 不是 Sendable；解码发生在后台，交给主线程时用这个盒子显式承担所有权。
private struct SendableImage: @unchecked Sendable {
    let image: UIImage
}

private struct PendingImage: Sendable {
    let id: String
    let data: Data?
    let source: String?
}

private func classroomImageCacheKey(scope: String, sceneID: String, elementID: String) -> String {
    "\(scope)|\(sceneID)|\(elementID)"
}

/// `/api/v1/courses/.../media/...` → APIClient 相对路径；绝对外链不再自行请求。
private func classroomMediaPath(_ source: String, mediaBasePath: String?) -> String? {
    // 经典课件也可能带绝对外链；这些地址没有经过本站授权，不能拿本地 token 去拉。
    if source.hasPrefix("http://") || source.hasPrefix("https://") || source.hasPrefix("//") { return nil }
    if let range = source.range(of: "/api/v1/") {
        let path = String(source[range.upperBound...])
        if let mediaBasePath, !path.hasPrefix(mediaBasePath) { return nil }
        return path
    }
    var relative = source
    while relative.hasPrefix("/") { relative.removeFirst() }
    guard !relative.isEmpty else { return nil }
    if let mediaBasePath {
        if relative.hasPrefix("media/media/") {
            relative.removeFirst("media/".count)
        }
        guard relative.hasPrefix("media/") || relative.hasPrefix("audio/") else { return nil }
        return mediaBasePath + relative
    }
    return relative
}
