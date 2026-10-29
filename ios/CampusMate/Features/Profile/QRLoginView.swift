import SwiftUI
import CampusCore

struct QRLoginView: View {
    @Environment(AppModel.self) private var app
    @State private var input = ""
    @State private var payload: QRLoginPayload?
    @State private var device: JSONValue = .null
    @State private var trustDevice = false
    @State private var working = false
    @State private var error: String?
    @State private var completed = false

    var body: some View {
        Form {
            if let payload {
                Section("确认网页登录") {
                    Label("确认是你正在使用的电脑", systemImage: "laptopcomputer")
                    if let name = device["device_label"].string ?? device["browser_name"].string { LabeledContent("设备", value: name) }
                    if let system = device["os_name"].string { LabeledContent("系统", value: system) }
                    Toggle("信任这台设备", isOn: $trustDevice)
                    Button(working ? "正在确认…" : "确认登录") { decide(payload, confirm: true) }.disabled(working)
                    Button("取消登录", role: .destructive) { decide(payload, confirm: false) }.disabled(working)
                }
            } else {
                Section {
                    TextField("粘贴 CampusMate 二维码内容", text: $input, axis: .vertical).lineLimit(3...6).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Button(working ? "正在识别…" : "识别并查看设备", action: scan).disabled(working || input.isEmpty)
                } header: { Text("登录二维码") } footer: { Text("仅识别 CampusMate 网页登录二维码。确认前请核对设备；二维码过期后需在电脑上刷新。") }
            }
        }.campusWorkflowChrome("扫码登录").errorAlert($error)
        .alert("登录请求已处理", isPresented: $completed) { Button("好", role: .cancel) { } }
    }
    private func scan() {
        working = true
        Task {
            defer { working = false }
            do {
                let value = try QRLoginPayload(input)
                device = try await app.client.request(.post, path: "auth/qr/scan", body: value.body)
                payload = value
            } catch { self.error = error.localizedDescription }
        }
    }
    private func decide(_ payload: QRLoginPayload, confirm: Bool) {
        working = true
        Task {
            defer { working = false }
            do {
                var body = payload.body.object ?? [:]
                if confirm { body["trust_device"] = .bool(trustDevice) }
                _ = try await app.client.request(.post, path: "auth/qr/\(confirm ? "confirm" : "cancel")", body: .object(body))
                self.payload = nil; input = ""; completed = true
            } catch { self.error = error.localizedDescription }
        }
    }
}
