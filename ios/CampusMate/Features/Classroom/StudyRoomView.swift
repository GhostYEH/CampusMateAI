import Foundation
import SwiftUI
import CampusCore

/// 多人在线自习室（互相监督）界面：成员在线状态 + 共享番茄钟 + 房内鼓励。
/// 入口在「专注自习」页；纯轮询，无音视频。契约见 docs/api/05-study.md。
struct StudyRoomView: View {
    @Environment(AppModel.self) private var app
    @State private var model = StudyRoomModel()
    @State private var title = ""
    @State private var inviteUID = ""
    @State private var draft = ""
    @State private var statusMessage = ""

    private let ink = Color(hex: 0x203A31)
    private let paper = Color(hex: 0xF8F3E8)
    private let line = Color(hex: 0xD5D2C3)
    private let copper = Color(hex: 0xAA7548)

    private let states: [(String, String, Color)] = [
        ("focus", "专注中", Color(hex: 0x2E8B57)),
        ("break", "休息中", Color(hex: 0xC9832B)),
        ("away", "离开", Color(hex: 0x8A8F98)),
        ("idle", "待命", Color(hex: 0x4A6FB5)),
    ]
    private func stateLabel(_ key: String) -> String { states.first { $0.0 == key }?.1 ?? "待命" }
    private func stateColor(_ key: String) -> Color { states.first { $0.0 == key }?.2 ?? Color(hex: 0x8A8F98) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("多人自习室").font(.title2).bold().foregroundStyle(ink)
                Text("和同学进同一个自习室，互相看见谁在专注、共用一个番茄钟、发一句鼓励。不开启摄像头或音视频。")
                    .font(.caption).foregroundStyle(ink.opacity(0.7))
                if let error = model.error {
                    Text(error).font(.caption).foregroundStyle(.red)
                }
                if model.hasRoom { liveRoom } else { entry }
            }
            .padding(16)
            .frame(maxWidth: 760)
            .frame(maxWidth: .infinity)
        }
        .background(paper.ignoresSafeArea())
        .navigationTitle("多人自习室")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await model.refreshLists(client: app.client)
            while !Task.isCancelled {
                await model.poll(client: app.client)
                try? await Task.sleep(for: .seconds(5))
            }
        }
    }

    private var entry: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                TextField("自习室名称，如：期末冲刺", text: $title)
                    .textFieldStyle(.roundedBorder)
                Button("创建") { Task { await model.create(title: title, client: app.client); title = "" } }
                    .buttonStyle(.borderedProminent).tint(copper)
            }
            if !model.myUID.isEmpty {
                Text("我的 UID：\(model.myUID)").font(.caption).foregroundStyle(ink.opacity(0.7))
            }
            if !model.invitations.isEmpty {
                Text("待接受的邀请").font(.headline).foregroundStyle(ink)
                ForEach(Array(model.invitations.enumerated()), id: \.offset) { _, invitation in
                    HStack {
                        Text("\(invitation["host_name"].text) 邀请你进入「\(invitation["title"].text)」").font(.subheadline)
                        Spacer()
                        Button("接受") { Task { await model.accept(id: invitation["room_id"].text, client: app.client) } }
                        Button("拒绝") { Task { await model.decline(id: invitation["room_id"].text, client: app.client) } }
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 6)
                    Divider()
                }
            }
            if !model.rooms.isEmpty {
                Text("我的自习室").font(.headline).foregroundStyle(ink)
                ForEach(Array(model.rooms.enumerated()), id: \.offset) { _, item in
                    HStack {
                        Text(item["title"].text).font(.subheadline)
                        Text("\(item["member_count"].int ?? 0) 人").font(.caption).foregroundStyle(.secondary)
                        Spacer()
                        Button("进入") { Task { await model.join(id: item["id"].text, client: app.client) } }
                    }
                    .padding(.vertical, 6)
                    Divider()
                }
            }
            if model.rooms.isEmpty && model.invitations.isEmpty {
                Text("创建自习室后，用同学的 UID 邀请他们加入。").font(.caption).foregroundStyle(ink.opacity(0.6))
            }
        }
        .padding(16)
        .background(Color.white.opacity(0.7), in: RoundedRectangle(cornerRadius: 18))
    }

    private var liveRoom: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(model.room["title"].text).font(.title3).bold().foregroundStyle(ink)
            timerCard
            membersCard
            myStateCard
            if model.isHost { inviteCard }
            messagesCard
            Button(model.isHost ? "结束自习室" : "离开自习室") {
                Task { await model.leave(client: app.client) }
            }
            .buttonStyle(.bordered).tint(.red)
            .frame(maxWidth: .infinity)
        }
    }

    private var timerCard: some View {
        TimelineView(.periodic(from: .now, by: 1)) { _ in
            let phase = model.room["timer"]["phase"].text
            let running = model.room["timer"]["running"].bool ?? false
            let paused = model.room["timer"]["paused"].bool ?? false
            let baseRemaining = model.room["timer"]["remaining_seconds"].int ?? 0
            let elapsed = running ? Int(Date().timeIntervalSince(model.fetchedAt)) : 0
            let remaining = max(0, baseRemaining - elapsed)
            VStack(spacing: 6) {
                Text((phase == "focus" ? "专注中" : phase == "break" ? "休息中" : "待开始") + (paused ? " · 已暂停" : ""))
                    .font(.caption).foregroundStyle(ink.opacity(0.7))
                Text(String(format: "%02d:%02d", remaining / 60, remaining % 60))
                    .font(.system(size: 44, weight: .bold, design: .rounded)).monospacedDigit()
                    .foregroundStyle(ink)
                Text("\(model.room["focus_minutes"].int ?? 25) 分钟专注 / \(model.room["break_minutes"].int ?? 5) 分钟休息")
                    .font(.caption2).foregroundStyle(ink.opacity(0.6))
                timerControls(phase: phase, paused: paused)
            }
            .frame(maxWidth: .infinity)
            .padding(16)
            .background(Color.white.opacity(0.8), in: RoundedRectangle(cornerRadius: 18))
        }
    }

    @ViewBuilder private func timerControls(phase: String, paused: Bool) -> some View {
        if model.isHost {
            HStack(spacing: 8) {
                switch phase {
                case "idle":
                    Button("开始专注") { Task { await model.controlTimer("start_focus", client: app.client) } }
                case "focus":
                    Button(paused ? "继续" : "暂停") { Task { await model.controlTimer(paused ? "resume" : "pause", client: app.client) } }
                    Button("开始休息") { Task { await model.controlTimer("start_break", client: app.client) } }
                case "break":
                    Button(paused ? "继续" : "暂停") { Task { await model.controlTimer(paused ? "resume" : "pause", client: app.client) } }
                default: EmptyView()
                }
                if phase != "idle" { Button("重置") { Task { await model.controlTimer("reset", client: app.client) } }.foregroundStyle(.secondary) }
            }
            .buttonStyle(.bordered)
        } else {
            Text("由发起人控制计时").font(.caption2).foregroundStyle(ink.opacity(0.6))
        }
    }

    private var membersCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("成员").font(.headline).foregroundStyle(ink)
            ForEach(Array(model.room["members"].items.enumerated()), id: \.offset) { _, member in
                if member["status"].text == "accepted" {
                    let online = member["online"].bool ?? false
                    let state = online ? member["study_state"].text : "away"
                    HStack(spacing: 8) {
                        Text(online ? stateLabel(state) : "离开")
                            .font(.caption2)
                            .padding(.horizontal, 8).padding(.vertical, 2)
                            .background(stateColor(state).opacity(0.2), in: Capsule())
                        Text(member["name"].text + (member["uid"].text == model.room["host_uid"].text ? "（发起人）" : ""))
                            .font(.subheadline)
                        Spacer()
                        if !member["status_message"].text.isEmpty {
                            Text(member["status_message"].text).font(.caption).foregroundStyle(ink.opacity(0.6))
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(Color.white.opacity(0.7), in: RoundedRectangle(cornerRadius: 18))
    }

    private var myStateCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("我的状态").font(.headline).foregroundStyle(ink)
            let mine = model.room["members"].items.first { $0["uid"].text == model.myUID }
            HStack(spacing: 8) {
                ForEach(states, id: \.0) { chip in
                    Button(chip.1) { Task { await model.setState(chip.0, message: nil, client: app.client) } }
                        .buttonStyle(.bordered)
                        .tint(mine?["study_state"].text == chip.0 ? chip.2 : .gray)
                }
            }
            HStack(spacing: 8) {
                TextField("状态语（可选），如：冲刺数学", text: $statusMessage).textFieldStyle(.roundedBorder)
                Button("保存状态语") { Task { await model.setState("focus", message: statusMessage, client: app.client) } }
            }
        }
        .padding(16)
        .background(Color.white.opacity(0.7), in: RoundedRectangle(cornerRadius: 18))
    }

    private var inviteCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("邀请同学").font(.headline).foregroundStyle(ink)
            HStack(spacing: 8) {
                TextField("同学 UID", text: $inviteUID).textFieldStyle(.roundedBorder)
                Button("邀请") { Task { await model.invite(uid: inviteUID, client: app.client); inviteUID = "" } }
                    .buttonStyle(.borderedProminent).tint(copper)
                    .disabled(inviteUID.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(16)
        .background(Color.white.opacity(0.7), in: RoundedRectangle(cornerRadius: 18))
    }

    private var messagesCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("互相鼓励").font(.headline).foregroundStyle(ink)
            if model.messages.isEmpty {
                Text("还没有消息，发一句鼓励吧。").font(.caption).foregroundStyle(ink.opacity(0.6))
            } else {
                ForEach(Array(model.messages.enumerated()), id: \.offset) { _, message in
                    HStack(alignment: .top, spacing: 8) {
                        Text(message["name"].text).font(.caption).bold().foregroundStyle(copper)
                        Text(message["content"].text).font(.subheadline)
                    }
                }
            }
            HStack(spacing: 8) {
                TextField("说点什么鼓励大家…", text: $draft).textFieldStyle(.roundedBorder)
                Button("发送") {
                    Task { if await model.send(draft, client: app.client) { draft = "" } }
                }
                .buttonStyle(.borderedProminent).tint(copper)
                .disabled(draft.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(16)
        .background(Color.white.opacity(0.7), in: RoundedRectangle(cornerRadius: 18))
    }
}
