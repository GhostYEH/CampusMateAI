import SwiftUI
import PhotosUI
import UIKit
import CampusCore

/// Port of `ExpressionContributionScreen`. iOS uses the system photo picker
/// and camera sheet; only a single image the user explicitly selects is
/// uploaded, and the returned sample can be deleted again.
struct ExpressionContributionView: View {
    @Environment(\.campus) private var palette
    @Environment(AppModel.self) private var app
    @State private var consent = false
    @State private var photoItem: PhotosPickerItem?
    @State private var preview: UIImage?
    @State private var label: ExpressionSampleLabel?
    @State private var uploading = false
    @State private var uploadedSampleID: String?
    @State private var uploadedCount = 0
    @State private var status: String?
    @State private var statusIsError = false
    @State private var showCamera = false

    private var cameraAvailable: Bool {
        UIImagePickerController.isSourceTypeAvailable(.camera)
    }

    var body: some View {
        CampusSecondaryScaffold(title: "CNN 模型共建") {
            ScrollView {
                VStack(spacing: 12) {
                    introCard
                    consentCard
                    if !consent {
                        lockedCard
                    } else if let preview {
                        reviewCard(preview)
                    } else {
                        sourceCard
                    }
                    if let uploadedSampleID {
                        uploadedCard(uploadedSampleID)
                    }
                    if let status {
                        statusBanner(status)
                    }
                    Text("样本只用于该项目的人工复核与后续模型优化，不代表心理诊断；你可以在上传后随时删除。")
                        .campusFont(.caption).foregroundStyle(palette.muted)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .onChange(of: consent) { _, enabled in
            if !enabled { discardPreview() }
        }
        .onChange(of: photoItem) { _, item in
            guard let item else { return }
            Task {
                do {
                    guard let data = try await item.loadTransferable(type: Data.self),
                          let image = UIImage(data: data) else {
                        throw APIError(code: "IMAGE_UNREADABLE", message: "无法读取这张图片，请换一张 JPG 或 PNG。")
                    }
                    guard consent, photoItem == item else { return }
                    preview = image
                    label = nil
                    status = nil
                } catch {
                    guard consent, photoItem == item else { return }
                    statusIsError = true
                    status = error.localizedDescription
                }
            }
        }
        .fullScreenCover(isPresented: $showCamera) {
            CameraCaptureView { image in
                preview = image
                label = nil
                status = nil
            }
        }
    }

    private var introCard: some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: "lock.shield").foregroundStyle(palette.primary)
                    Text("隐私优先的单帧共建").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                }
                Text("每次只处理一张由你主动选择或拍摄的图片。你负责确认标签，上传前可重新选择，上传后也可以删除自己的样本。")
                    .campusFont(.caption).foregroundStyle(palette.muted)
                    .fixedSize(horizontal: false, vertical: true)
                Text("本次已上传 \(uploadedCount) 条")
                    .campusFont(.caption).fontWeight(.semibold).foregroundStyle(palette.primary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var consentCard: some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 8) {
                Toggle("我同意参与 CNN 表情模型共建", isOn: $consent)
                    .tint(palette.primary)
                    .campusFont(.body)
                    .accessibilityIdentifier("contribution.consent")
                Text("我理解图片会上传到项目后端，用于人工复核、数据分析和后续模型训练；这不是心理诊断，也不代表我的心理状态。")
                    .campusFont(.caption).foregroundStyle(palette.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var lockedCard: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "lock").foregroundStyle(palette.primary)
            VStack(alignment: .leading, spacing: 4) {
                Text("开启同意后才能采集").campusFont(.body).fontWeight(.semibold).foregroundStyle(palette.textPrimary)
                Text("模型共建不会在后台自动打开相机，也不会在未同意时保存或上传图片。")
                    .campusFont(.caption).foregroundStyle(palette.muted)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(palette.primary.opacity(0.10), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private var sourceCard: some View {
        let primary = palette.primary
        return CampusCard {
            VStack(alignment: .leading, spacing: 12) {
                Text("选择一张自然状态的正面照片")
                    .campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                Text("只选择你主动拍摄或从相册挑选的一张图片。支持 JPG 与 PNG。")
                    .campusFont(.caption).foregroundStyle(palette.muted)
                if cameraAvailable {
                    Button {
                        showCamera = true
                    } label: {
                        Label("拍摄照片", systemImage: "camera")
                            .campusFont(.body)
                            .frame(maxWidth: .infinity)
                            .frame(minHeight: 46)
                            .background(palette.primarySoft, in: RoundedRectangle(cornerRadius: 14))
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(palette.primary)
                    .accessibilityIdentifier("contribution.camera")
                }
                PhotosPicker(selection: $photoItem, matching: .images, photoLibrary: .shared()) {
                    Label("从相册选择", systemImage: "photo.on.rectangle")
                        .font(.system(size: 15))
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(minHeight: 46)
                        .background(primary, in: RoundedRectangle(cornerRadius: 14))
                }
                .accessibilityIdentifier("contribution.photo")
                Text("照片在设备上转换为 JPEG 后才会上传；应用不会保留相册中的原图副本。")
                    .campusFont(.caption).foregroundStyle(palette.muted)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func reviewCard(_ image: UIImage) -> some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 12) {
                Text("确认你的表情标签").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()
                    .frame(maxWidth: .infinity)
                    .frame(maxHeight: 260)
                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .accessibilityLabel("待标注的表情照片")
                Text("请选择你认为最符合当前可观察表情的标签。")
                    .campusFont(.caption).foregroundStyle(palette.muted)
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 82), spacing: 8)], alignment: .leading, spacing: 8) {
                    ForEach(ExpressionSampleLabel.allCases) { option in
                        CampusFilterChip(title: option.title, isSelected: label == option) {
                            label = option
                        }
                    }
                }
                HStack(spacing: 10) {
                    CampusSecondaryButton(title: "重新选择", systemImage: "arrow.counterclockwise", enabled: !uploading) {
                        discardPreview()
                    }
                    CampusPrimaryButton(title: uploading ? "正在上传…" : "确认并上传",
                                        systemImage: "icloud.and.arrow.up",
                                        loading: uploading,
                                        enabled: label != nil && !uploading) {
                        upload(image)
                    }
                    .accessibilityIdentifier("contribution.upload")
                }
            }
        }
    }

    private func uploadedCard(_ sampleID: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "checkmark.circle.fill").foregroundStyle(palette.success)
            VStack(alignment: .leading, spacing: 3) {
                Text("服务器已接收这条样本").campusFont(.body).fontWeight(.semibold).foregroundStyle(palette.textPrimary)
                Text("编号 \(sampleID.prefix(10)) · 可随时删除").campusFont(.caption).foregroundStyle(palette.muted)
            }
            Spacer(minLength: 0)
            Button(role: .destructive) {
                deleteSample(sampleID)
            } label: {
                Image(systemName: "trash").frame(width: 44, height: 44)
            }
            .disabled(uploading)
            .accessibilityLabel("删除云端样本")
            .accessibilityIdentifier("contribution.delete")
        }
        .padding(14)
        .background(palette.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(palette.line, lineWidth: 1))
    }

    private func statusBanner(_ message: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: statusIsError ? "exclamationmark.circle" : "info.circle")
                .foregroundStyle(statusIsError ? palette.alertErrorText : palette.alertInfoText)
            Text(message)
                .campusFont(.caption)
                .foregroundStyle(statusIsError ? palette.alertErrorText : palette.alertInfoText)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(12)
        .background(statusIsError ? palette.alertErrorBackground : palette.alertInfoBackground,
                    in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private func discardPreview() {
        preview = nil
        photoItem = nil
        label = nil
        status = nil
    }

    private func upload(_ image: UIImage) {
        guard consent else {
            statusIsError = true
            status = "请先确认参与模型共建并同意上传。"
            return
        }
        guard let label, let jpeg = image.jpegData(compressionQuality: 0.82) else {
            statusIsError = true
            status = "无法转换这张图片，请换一张 JPG 或 PNG。"
            return
        }
        uploading = true
        status = nil
        Task {
            defer { uploading = false }
            do {
                let response = try await PersonalService(client: app.client)
                    .uploadExpressionSample(image: jpeg, label: label.rawValue)
                guard let sampleID = response["sample_id"].string?.nonEmpty else {
                    throw APIError(code: "INVALID_RESPONSE", message: "样本上传响应缺少编号。")
                }
                uploadedSampleID = sampleID
                uploadedCount += 1
                preview = nil
                photoItem = nil
                self.label = nil
                statusIsError = false
                status = response["message"].string ?? "样本已上传，感谢你的共建。"
            } catch {
                statusIsError = true
                status = error.localizedDescription
            }
        }
    }

    private func deleteSample(_ sampleID: String) {
        uploading = true
        status = nil
        Task {
            defer { uploading = false }
            do {
                try await PersonalService(client: app.client).deleteExpressionSample(id: sampleID)
                uploadedSampleID = nil
                uploadedCount = max(0, uploadedCount - 1)
                statusIsError = false
                status = "这条共建样本已从服务器删除。"
            } catch {
                statusIsError = true
                status = error.localizedDescription
            }
        }
    }
}

private enum ExpressionSampleLabel: String, CaseIterable, Identifiable {
    case happy = "HAPPY"
    case neutral = "NEUTRAL"
    case sad = "SAD"
    case angry = "ANGRY"
    case fear = "FEAR"
    case surprise = "SURPRISE"
    case disgust = "DISGUST"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .happy: "开心"
        case .neutral: "中性"
        case .sad: "低落"
        case .angry: "生气"
        case .fear: "紧张"
        case .surprise: "惊讶"
        case .disgust: "厌恶"
        }
    }
}

private struct CameraCaptureView: UIViewControllerRepresentable {
    @Environment(\.dismiss) private var dismiss
    let onCapture: (UIImage) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(parent: self) }

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.cameraDevice = .front
        picker.allowsEditing = false
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ picker: UIImagePickerController, context: Context) { }

    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        private let parent: CameraCaptureView

        init(parent: CameraCaptureView) {
            self.parent = parent
        }

        func imagePickerController(_ picker: UIImagePickerController,
                                   didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            if let image = info[.originalImage] as? UIImage { parent.onCapture(image) }
            parent.dismiss()
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            parent.dismiss()
        }
    }
}
