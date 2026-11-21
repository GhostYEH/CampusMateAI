import CampusCore
import SwiftUI

/// 待办详情中的作业复习面板。生成只提交 scope，完成后的课堂在原生阅读器中学习，
/// 不依赖 CampusMate Web 路由或登录态桥。
struct ChaoxingAssignmentReviewSection: View {
    @Environment(AppModel.self) private var app
    let task: TaskItem

    @State private var content: ChaoxingAssignmentContent?
    @State private var review: ChaoxingAssignmentReview?
    @State private var lesson: ChaoxingLesson?
    @State private var loading = true
    @State private var lessonLoading = false
    @State private var busyScope: String?
    @State private var error: String?
    @State private var showLesson = false
    @State private var showWrongList = false

    private var service: ChaoxingAssignmentService { ChaoxingAssignmentService(client: app.client) }

    var body: some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 9) {
                HStack(alignment: .firstTextBaseline) {
                    Text("作业复习").campusFont(.subtitle).foregroundStyle(CampusJournal.ink)
                    Spacer(minLength: 8)
                    if let content, content.resultsComplete {
                        CampusStatusTag(text: content.wrongCount > 0 ? "\(content.wrongCount) 道错题" : "全部正确",
                                        tone: content.wrongCount > 0 ? .warning : .success)
                    }
                }
                Text("全部题目复习保留原题重做与变式；错题复习只出变式，不再出现原题。")
                    .campusFont(.caption).foregroundStyle(CampusJournal.muted)

                if loading {
                    HStack(spacing: 8) {
                        ProgressView().controlSize(.small).tint(CampusJournal.clay)
                        Text("正在读取作业题目…").campusFont(.caption).foregroundStyle(CampusJournal.muted)
                    }
                } else if let content {
                    contentBody(content)
                } else {
                    Text(error ?? "暂时无法读取作业题目，请返回课程同步后重试。")
                        .campusFont(.caption).foregroundStyle(Color(hex: 0x974D42))
                }

                if let review { reviewBody(review) }
                if let error, content != nil {
                    Text(error).campusFont(.caption).foregroundStyle(Color(hex: 0x974D42))
                }
            }
        }
        .task(id: task.id) { await loadContent() }
        .task(id: review?.pollKey) { await pollJob() }
        .fullScreenCover(isPresented: $showLesson) {
            if let lesson { ChaoxingLessonReader(lesson: lesson) }
        }
    }

    @ViewBuilder
    private func contentBody(_ content: ChaoxingAssignmentContent) -> some View {
        if !content.available {
            Text("还没有题目快照。请先到课程页同步学习通作业，再回来复习。")
                .campusFont(.caption).foregroundStyle(CampusJournal.muted)
        } else {
            Text("已同步 \(content.questions.count) 道题。")
                .campusFont(.caption).foregroundStyle(CampusJournal.muted)
            if content.resultsComplete {
                Text(content.wrongCount > 0
                     ? "已批改：错题 \(content.wrongCount) 道，可以只生成错题变式讲解。"
                     : "已批改：本次作业全部正确，没有需要单独整理的错题。")
                    .campusFont(.caption).foregroundStyle(CampusJournal.muted)
            } else if content.hasPartialResults {
                Text("已取得部分批改结果：已批改 \(content.gradedCount)/\(content.questions.count) 道，发现错题 \(content.wrongCount) 道；其余题目尚未批改。")
                    .campusFont(.caption).foregroundStyle(CampusJournal.muted)
            } else {
                Text("尚未取得逐题批改结果，暂不能单独生成错题课；可以先按全部题目复习。")
                    .campusFont(.caption).foregroundStyle(CampusJournal.muted)
            }
            if !wrongQuestions(content).isEmpty {
                Button {
                    showWrongList.toggle()
                } label: {
                    Text(showWrongList ? "收起错题清单" : "查看错题清单（\(wrongQuestions(content).count)）")
                        .campusFont(.caption).foregroundStyle(CampusJournal.blue)
                }
                .buttonStyle(.plain)
                if showWrongList {
                    VStack(alignment: .leading, spacing: 5) {
                        ForEach(wrongQuestions(content)) { question in
                            Text("第 \(question.number) 题 · \(question.stem)")
                                .font(.system(size: 12)).foregroundStyle(CampusJournal.ink)
                        }
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.white.opacity(0.55), in: RoundedRectangle(cornerRadius: 9))
                }
            }
            if !content.canGenerate {
                Text("作业截止后开放复习；截止时间未知时请先同步学习通。")
                    .campusFont(.caption).foregroundStyle(CampusJournal.muted)
            }
            if !content.current {
                Text("题目快照与当前提交状态不一致，建议先同步作业。")
                    .campusFont(.caption).foregroundStyle(CampusJournal.clay)
            }
            HStack(spacing: 8) {
                CampusPrimaryButton(title: "全部题目复习", systemImage: "rectangle.stack",
                                    loading: busyScope == "all",
                                    enabled: content.canGenerate && busyScope == nil) {
                    generate("all")
                }
                if content.canGenerateWrong {
                    CampusSecondaryButton(title: "错题讲解", systemImage: "target",
                                          enabled: busyScope == nil) {
                        generate("wrong")
                    }
                }
            }
        }
    }

    private func wrongQuestions(_ content: ChaoxingAssignmentContent) -> [ChaoxingAssignmentQuestion] {
        content.questions.filter { $0.isCorrect == false }
    }

    @ViewBuilder
    private func reviewBody(_ review: ChaoxingAssignmentReview) -> some View {
        switch review.jobStatus {
        case "queued", "running":
            VStack(alignment: .leading, spacing: 5) {
                ProgressView(value: Double(review.jobProgress), total: 100)
                    .tint(CampusJournal.clay)
                Text("课堂生成中：\(review.jobProgress)% 。可以保持此页面等待，或稍后重新生成。")
                    .campusFont(.caption).foregroundStyle(CampusJournal.muted)
            }
        case "completed":
            VStack(alignment: .leading, spacing: 6) {
                Text(review.scope == "wrong" ? "错题变式课堂已生成。" : "作业讲解与练习已生成。")
                    .campusFont(.caption).foregroundStyle(CampusJournal.blue)
                if lessonLoading {
                    Text("正在读取课堂内容…").campusFont(.caption).foregroundStyle(CampusJournal.muted)
                } else if lesson != nil {
                    CampusSecondaryButton(title: "进入原生课堂阅读", systemImage: "book") {
                        showLesson = true
                    }
                }
            }
        default:
            VStack(alignment: .leading, spacing: 5) {
                Text("课堂生成未完成，可以重试这次任务。")
                    .campusFont(.caption).foregroundStyle(Color(hex: 0x974D42))
                Button { retry(review) } label: {
                    Text(busyScope == "retry" ? "正在重试…" : "重试生成")
                        .campusFont(.caption).foregroundStyle(CampusJournal.blue)
                }
                .buttonStyle(.plain)
                .disabled(busyScope != nil)
            }
        }
    }

    private func loadContent() async {
        loading = true
        do {
            content = try await service.content(taskID: task.id)
            error = nil
        } catch {
            self.error = ChaoxingAssignmentPresentation.message(for: error, fallback: "作业题目读取失败")
        }
        loading = false
    }

    private func generate(_ scope: String) {
        guard busyScope == nil else { return }
        busyScope = scope
        error = nil
        Task {
            do {
                let response = try await service.generate(taskID: task.id, scope: scope)
                review = response
            } catch {
                self.error = ChaoxingAssignmentPresentation.message(for: error, fallback: "课堂生成请求被拒绝")
            }
            busyScope = nil
        }
    }

    private func retry(_ response: ChaoxingAssignmentReview) {
        guard busyScope == nil, let jobID = response.jobID else { return }
        busyScope = "retry"
        error = nil
        Task {
            do {
                let job = try await service.retryJob(courseID: response.courseID, jobID: jobID)
                var current = response
                current.jobStatus = job.status
                current.jobProgress = job.progress
                review = current
            } catch {
                self.error = ChaoxingAssignmentPresentation.message(for: error, fallback: "课堂重试失败")
            }
            busyScope = nil
        }
    }

    private func pollJob() async {
        guard let jobID = review?.jobID else { return }
        while !Task.isCancelled {
            guard var current = review, current.isRunning else { break }
            try? await Task.sleep(for: .seconds(2))
            do {
                let job = try await service.job(courseID: current.courseID, jobID: jobID)
                current.jobStatus = job.status
                current.jobProgress = job.progress
                review = current
            } catch {
                self.error = ChaoxingAssignmentPresentation.message(for: error, fallback: "课堂进度查询失败")
                return
            }
        }
        if let current = review, current.isCompleted { await loadLesson(current) }
    }

    private func loadLesson(_ response: ChaoxingAssignmentReview) async {
        lessonLoading = true
        do {
            var stageID = response.stageID
            if stageID == nil {
                for _ in 0..<3 {
                    stageID = try await service.latestStageID(courseID: response.courseID, workspaceID: response.workspaceID)
                    if stageID != nil { break }
                    try? await Task.sleep(for: .seconds(1))
                }
            }
            guard let stageID else {
                error = "课堂已生成，但还没有找到可阅读的舞台"
                lessonLoading = false
                return
            }
            let parsed = try await service.lesson(courseID: response.courseID, workspaceID: response.workspaceID, stageID: stageID)
            lesson = parsed
            showLesson = true
            error = nil
        } catch {
            self.error = ChaoxingAssignmentPresentation.message(for: error, fallback: "课堂内容读取失败")
        }
        lessonLoading = false
    }
}

private struct ChaoxingLessonReader: View {
    @Environment(\.dismiss) private var dismiss
    let lesson: ChaoxingLesson

    var body: some View {
        ZStack {
            JournalBackdrop()
            VStack(spacing: 0) {
                HStack(alignment: .top, spacing: 12) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(lesson.title).font(.system(size: 22, weight: .heavy)).foregroundStyle(CampusJournal.ink)
                        Text("\(lesson.quizCount) 道练习 · 先做题，再展开参考解析")
                            .font(.system(size: 12)).foregroundStyle(CampusJournal.muted)
                    }
                    Spacer()
                    Button { dismiss() } label: {
                        Image(systemName: "xmark").font(.system(size: 15, weight: .bold))
                            .foregroundStyle(CampusJournal.ink).frame(width: 36, height: 36)
                            .background(Color.white.opacity(0.6), in: Circle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("关闭课堂")
                }
                .padding(16)
                Rectangle().fill(CampusJournal.blue.opacity(0.35)).frame(height: 1)
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("参考解析由 AI 根据作业快照生成，不是教师官方答案；简答题不自动判分。")
                            .font(.system(size: 12)).foregroundStyle(CampusJournal.muted)
                        ForEach(lesson.scenes) { scene in
                            ChaoxingLessonSceneCard(scene: scene)
                        }
                    }
                    .padding(16)
                    .frame(maxWidth: 720)
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .campusImmersive()
    }
}

private struct ChaoxingLessonSceneCard: View {
    let scene: ChaoxingLessonScene

    var body: some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 9) {
                HStack {
                    Text(scene.title).font(.system(size: 16, weight: .bold)).foregroundStyle(CampusJournal.ink)
                    Spacer()
                    Text(scene.kind == "quiz" ? "练习" : "讲解")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundStyle(scene.kind == "quiz" ? CampusJournal.clay : CampusJournal.blue)
                }
                if let body = scene.body, !body.isEmpty {
                    Text(body).font(.system(size: 13)).foregroundStyle(CampusJournal.ink)
                }
                ForEach(scene.blocks.indices, id: \.self) { index in
                    let block = scene.blocks[index]
                    if let heading = block.heading {
                        Text(heading).font(.system(size: 13, weight: .semibold)).foregroundStyle(CampusJournal.clay)
                    }
                    ForEach(block.bullets, id: \.self) { bullet in
                        Text("· \(bullet)").font(.system(size: 13)).foregroundStyle(CampusJournal.ink)
                    }
                }
                ForEach(scene.questions) { question in
                    ChaoxingQuestionCard(question: question)
                }
            }
        }
    }
}

private struct ChaoxingQuestionCard: View {
    let question: ChaoxingLessonQuestion
    @State private var selected: Set<String> = []
    @State private var submitted = false
    @State private var visibleHints = 0
    @State private var shortAnswer = ""

    private var correctLabels: [String] {
        question.options.filter { question.answer.contains($0.value) }.map(\.label)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(spacing: 6) {
                Text(question.roleLabel).font(.system(size: 10, weight: .bold)).foregroundStyle(CampusJournal.clay)
                if let number = question.sourceNumber {
                    Text("对应原题 \(number)").font(.system(size: 10)).foregroundStyle(CampusJournal.muted)
                }
                if question.isMultiple { Text("多选").font(.system(size: 10)).foregroundStyle(CampusJournal.muted) }
            }
            Text(question.prompt).font(.system(size: 14, weight: .semibold)).foregroundStyle(CampusJournal.ink)

            if question.isChoice {
                ForEach(question.options) { option in
                    optionRow(option)
                }
            } else {
                TextField("先自己写出思路或答案，再核对参考解析", text: $shortAnswer, axis: .vertical)
                    .lineLimit(2...5)
                    .font(.system(size: 13))
                    .padding(10)
                    .background(Color.white.opacity(0.55), in: RoundedRectangle(cornerRadius: 9))
                    .disabled(submitted)
            }

            if !question.hints.isEmpty && !submitted {
                Button {
                    visibleHints = min(visibleHints + 1, question.hints.count)
                } label: {
                    Label(visibleHints == 0 ? "查看提示" : "再展开一条提示",
                          systemImage: visibleHints < question.hints.count ? "chevron.down" : "chevron.up")
                        .font(.system(size: 12, weight: .semibold)).foregroundStyle(CampusJournal.blue)
                }
                .buttonStyle(.plain)
                .disabled(visibleHints >= question.hints.count)
                ForEach(0..<visibleHints, id: \.self) { index in
                    Text("提示 \(index + 1)：\(question.hints[index])")
                        .font(.system(size: 12)).foregroundStyle(CampusJournal.muted)
                }
            }

            if !submitted {
                Button {
                    submitted = true
                } label: {
                    Text(question.isChoice ? "提交并查看解析" : "查看参考解析")
                        .font(.system(size: 12, weight: .bold)).foregroundStyle(.white)
                        .frame(maxWidth: .infinity).frame(height: 38)
                        .background(CampusJournal.blue, in: RoundedRectangle(cornerRadius: 9))
                }
                .buttonStyle(.plain)
                .disabled(question.isChoice ? selected.isEmpty : shortAnswer.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            } else {
                if question.isChoice {
                    let correct = selected == Set(question.answer)
                    Text(correct ? "回答正确" : "回答不正确；正确选项：\(correctLabels.isEmpty ? "见解析" : correctLabels.joined(separator: "、"))")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(correct ? Color(hex: 0x3D7A52) : Color(hex: 0x974D42))
                }
                Text(question.analysis).font(.system(size: 13)).foregroundStyle(CampusJournal.ink)
            }
        }
        .padding(.top, 2)
    }

    private func optionRow(_ option: ChaoxingLessonOption) -> some View {
        let isSelected = selected.contains(option.value)
        let isCorrect = question.answer.contains(option.value)
        let fill: Color = {
            if submitted && isCorrect { return Color(hex: 0xE1F0E5) }
            if submitted && isSelected && !isCorrect { return Color(hex: 0xF6DAD8) }
            if isSelected { return CampusJournal.blue.opacity(0.12) }
            return Color.white.opacity(0.55)
        }()
        return Button {
            guard !submitted else { return }
            if question.isMultiple {
                if isSelected { selected.remove(option.value) } else { selected.insert(option.value) }
            } else {
                selected = [option.value]
            }
        } label: {
            HStack {
                Text(option.label).font(.system(size: 13)).foregroundStyle(CampusJournal.ink)
                Spacer()
                if submitted && isCorrect {
                    Text("正确").font(.system(size: 10)).foregroundStyle(Color(hex: 0x3D7A52))
                }
            }
            .padding(.horizontal, 10).padding(.vertical, 8)
            .background(fill, in: RoundedRectangle(cornerRadius: 9))
            .overlay(RoundedRectangle(cornerRadius: 9).strokeBorder(
                isSelected ? CampusJournal.blue : CampusJournal.blue.opacity(0.22), lineWidth: 1))
        }
        .buttonStyle(.plain)
    }
}
