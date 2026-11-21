import Foundation

/// 作业复习的受管接口。生成请求只提交 scope；题型、变式与查重都发生在服务端，
/// 客户端不会把原题重新包装成练习，也不会持有 magic class 上游凭据。
public struct ChaoxingAssignmentService: Sendable {
    private let client: APIClient

    public init(client: APIClient) { self.client = client }

    public func content(taskID: String) async throws -> ChaoxingAssignmentContent {
        let json = try await client.request(path: "chaoxing/assignments/\(taskID.pathComponent)/content")
        return try ChaoxingAssignmentContent(json: json)
    }

    public func generate(taskID: String, scope: String) async throws -> ChaoxingAssignmentReview {
        let json = try await client.request(
            .post,
            path: "chaoxing/assignments/\(taskID.pathComponent)/classroom",
            body: ["scope": .string(scope)]
        )
        return try ChaoxingAssignmentReview(json: json)
    }

    public func job(courseID: String, jobID: String) async throws -> ChaoxingGenerationJob {
        let json = try await client.request(path: "courses/\(courseID.pathComponent)/jobs/\(jobID.pathComponent)")
        return try ChaoxingGenerationJob(json: json)
    }

    public func retryJob(courseID: String, jobID: String) async throws -> ChaoxingGenerationJob {
        let json = try await client.request(
            .post,
            path: "courses/\(courseID.pathComponent)/jobs/\(jobID.pathComponent)/retry"
        )
        return try ChaoxingGenerationJob(json: json)
    }

    public func stages(courseID: String, workspaceID: String) async throws -> [JSONValue] {
        let json = try await client.request(
            path: "courses/\(courseID.pathComponent)/workspaces/\(workspaceID.pathComponent)/stages",
            query: ["limit": "50"]
        )
        return json["items"].array ?? []
    }

    public func stage(courseID: String, workspaceID: String, stageID: String) async throws -> JSONValue {
        try await client.request(
            path: "courses/\(courseID.pathComponent)/workspaces/\(workspaceID.pathComponent)/stages/\(stageID.pathComponent)"
        )
    }

    /// Provider 异步完成时 job 不携带 stage_id；完成后按更新时间选最新舞台。
    public func latestStageID(courseID: String, workspaceID: String) async throws -> String? {
        try await stages(courseID: courseID, workspaceID: workspaceID)
            .max { left, right in
                let leftDate = left["updated_at"].string ?? left["created_at"].string ?? ""
                let rightDate = right["updated_at"].string ?? right["created_at"].string ?? ""
                return leftDate < rightDate
            }?["id"].string?.nonEmpty
    }

    public func lesson(courseID: String, workspaceID: String, stageID: String) async throws -> ChaoxingLesson {
        let stage = try await stage(courseID: courseID, workspaceID: workspaceID, stageID: stageID)
        guard let document = stage["document"].object else {
            throw ChaoxingAssignmentError.invalidResponse("课堂舞台缺少 document")
        }
        return try ChaoxingLesson(document: .object(document))
    }
}
