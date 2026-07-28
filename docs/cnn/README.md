# CampusMateAI CNN 面部表情识别工程

本目录是 CampusMateAI 的 CNN 面部表情识别训练与评估工程，为 Flutter 端
LiteRT/TFLite 推理提供**真实模型**。工程位于
[`ml/expression_recognition/`](../../ml/expression_recognition/)。

## 目录

- [科学边界](./SCIENTIFIC_BOUNDARIES.md) — 强制约束：识别表情，不诊断心理状态。
- [复现指南](./REPRODUCTION.md) — 安装、数据准备、训练、评估、导出全流程。
- [实验报告](./REPORT.md) — 真实训练状态、指标、SHA-256、未验证项（诚实声明）。

## 工程概览

| 项 | 说明 |
| --- | --- |
| 任务 | 面部表情七分类（FER2013：angry/disgust/fear/happy/sad/surprise/neutral） |
| 候选模型 | 自定义浅层 CNN、ResNet18（迁移）、**MobileNetV3-Small（迁移，主部署候选）** |
| 数据 | FER2013（CSV 或 image_dir 两种格式），不自动下载 |
| 输出 | PyTorch 权重 / ONNX / TFLite + labels.json + preprocess.json |
| 评估 | Accuracy / Macro-F1 / 各类 P/R / 混淆矩阵 / 参数量 / 模型大小 / CPU 延迟 |
| 一致性 | PyTorch ↔ ONNX ↔ TFLite Top-1 标签一致性测试 |
| 命令 | `prepare_data` / `train` / `evaluate` / `export` / `benchmark` / `run_all` |

## 关键命令

```bash
cd ml/expression_recognition
pip install -r requirements.txt

# 编辑 experiment_config.yaml，填入 data.dataset_root 后：
python -m expression_recognition --config experiment_config.yaml run_all
```

详细步骤见 [复现指南](./REPRODUCTION.md)。

## 当前状态摘要

- ✅ 可复现训练工程（数据/模型/训练/评估/导出/基准/一致性）已实现。
- ✅ 单元测试已覆盖：数据解析、前向传播、输出维度、标签顺序、检查点、ONNX、TFLite（条件）、指标、无数据错误。
- ✅ 非 torch 测试 35 项全部通过；torch 相关测试在无 torch 环境优雅跳过。
- ⚠️ **尚未完成真实训练**：本机无 torch、无 FER2013 数据，未产生真实权重与指标。详见 [实验报告](./REPORT.md)。

## 科学边界（强制）

本工程识别的是**可观察到的面部表情**，不是人员身份识别。FER2013 不包含疲劳、
注意力、焦虑症或心理疾病类别。任何把这些类别作为 FER2013 分类结果的行为都被禁止。
识别结果仅供辅助参考，不进行疾病诊断，不替代专业心理咨询。详见
[科学边界](./SCIENTIFIC_BOUNDARIES.md)。
