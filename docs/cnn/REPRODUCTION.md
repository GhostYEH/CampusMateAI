# 复现指南

本文档说明如何从零复现 CampusMateAI CNN 面部表情识别训练与评估。

## 1. 环境要求

- Python ≥ 3.10
- 操作系统：Windows / Linux / macOS 均可（本工程在 Windows 11 + Python 3.10.11 验证）
- CPU 可训练（MobileNetV3-Small 在 CPU 上单 epoch 约数分钟，建议有 GPU 时开启 `train.amp`）
- 可选 GPU：CUDA 11.8/12.1，按 [pytorch.org](https://pytorch.org/get-started/locally/) 安装对应 torch

## 2. 安装依赖

```bash
cd ml/expression_recognition
pip install -r requirements.txt
```

可选 TFLite 导出链路（环境支持时才装）：

```bash
pip install onnx2tf tensorflow ai-edge-litert sng4onnx onnx_graphsurgeon
```

> TFLite 导出依赖较重，不装也能完成训练/评估/ONNX 导出；导出脚本会自动跳过并记录原因。

## 3. 准备 FER2013 数据

本工程**不自动下载**来历不明的数据。请从合法来源获取 FER2013，例如：

- Kaggle: `msambare/fer2013`（CSV 版）或 `msambare/fer2013`（image_dir 版）
- 原 FER2013 ICML 2013 竞赛数据

支持两种格式：

### 3.1 CSV 格式（`data.format: fer2013_csv`）

放置文件：

```
<dataset_root>/fer2013.csv
```

CSV 列：`emotion`（0..6）、`pixels`（2304 个空格分隔整数）、`Usage`
（Training / PublicTest / PrivateTest）。

### 3.2 image_dir 格式（`data.format: image_dir`）

放置文件：

```
<dataset_root>/train/{angry,disgust,fear,happy,sad,surprise,neutral}/*.png
<dataset_root>/val/  {angry,...}/*.png
<dataset_root>/test/ {angry,...}/*.png
```

若未划分，也支持 `<dataset_root>/{label}/*.png`，由脚本分层随机划分。

## 4. 配置实验

编辑 [`experiment_config.yaml`](../../ml/expression_recognition/experiment_config.yaml)：

```yaml
data:
  dataset_root: "/path/to/fer2013"   # 你的数据集根目录
  format: fer2013_csv                 # 或 image_dir

model:
  name: mobilenet_v3_small            # 主部署候选
  pretrained: true
  freeze_backbone: true
  unfreeze_at_epoch: 5
```

## 5. 运行

### 5.1 全流程

```bash
python -m expression_recognition --config experiment_config.yaml run_all
```

依次执行：`prepare_data → train → evaluate(test) → export → benchmark`。

### 5.2 分步

```bash
# 仅解析与划分数据，输出 data_split_summary.json
python -m expression_recognition --config experiment_config.yaml prepare_data

# 训练
python -m expression_recognition --config experiment_config.yaml train

# 在测试集评估（输出 metrics.json / per_class_metrics.csv / confusion_matrix.png）
python -m expression_recognition --config experiment_config.yaml evaluate --split test

# 导出 PyTorch/ONNX/TFLite + labels.json + preprocess.json + 一致性测试
python -m expression_recognition --config experiment_config.yaml export

# 单张 CPU 推理延迟、参数量、模型大小
python -m expression_recognition --config experiment_config.yaml benchmark
```

命令行参数可覆盖配置：

```bash
python -m expression_recognition --config experiment_config.yaml \
    --dataset-root /path/to/data --output-dir runs/exp1 train
```

## 6. 输出文件

`output_dir` 下生成：

| 文件 | 内容 |
| --- | --- |
| `data_split_summary.json` | 数据划分摘要（方法、各类计数、防泄漏说明） |
| `best_model.pt` | 最佳检查点（按 monitor 指标） |
| `last_model.pt` | 末轮检查点 |
| `training_history.csv` | 每 epoch 的 train/val loss、val_acc、val_f1、lr |
| `training_summary.json` | 训练摘要（best_metric、参数量、检查点路径） |
| `metrics.json` | 测试集完整指标 |
| `per_class_metrics.csv` | 每类 P/R/F1/support |
| `confusion_matrix.png` | 混淆矩阵图 |
| `evaluate_summary.json` | 评估元信息（检查点 SHA-256、大小、split） |
| `model.onnx` | ONNX 模型 |
| `model.tflite` | TFLite 模型（环境支持时） |
| `labels.json` | 标签顺序契约 |
| `preprocess.json` | 预处理参数契约（input_size/normalization/label_order） |
| `consistency.json` | PyTorch/ONNX/TFLite 一致性测试结果 |
| `benchmark.json` | 推理延迟、参数量、模型大小 |
| `export_summary.json` | 导出汇总 |

## 7. 切换模型

修改 `model.name`：

- `custom_cnn`：浅层 CNN 基线，1 通道 48×48，CPU 友好。同时把 `input.size: 48`、`input.channels: 1`、`input.mean: [0.5]`、`input.std: [0.5]`。
- `resnet18`：ResNet18 迁移学习，3 通道 224×224，ImageNet 归一化。
- `mobilenet_v3_small`：MobileNetV3-Small 迁移学习，3 通道 224×224，**主部署候选**。

## 8. 单元测试

```bash
cd ml/expression_recognition
python -m pytest -v
```

torch 相关测试在无 torch 环境会优雅跳过；安装 torch 后全部运行。

## 9. 防泄漏说明

- 优先使用 FER2013 官方 `Usage` 列划分（Training/PublicTest/PrivateTest）。
- 数据未自带 Usage 时，按分层随机划分（按类别比例，独立种子，可复现）。
- 数据增强**仅作用于训练集**；验证/测试集只做 resize + 归一化。
- FER2013 不提供受试者 ID，无法做严格的同源样本隔离；如未来获得带 subject ID 的数据，
  应改为按 subject 划分以进一步防泄漏。详见 [`data/split.py`](../../ml/expression_recognition/expression_recognition/data/split.py) 的 `LEAKAGE_NOTE`。

## 10. 接入 Flutter 端

导出的 `model.tflite` + `labels.json` + `preprocess.json` 供 Flutter 端
`LiteRtExpressionRecognitionService` 加载。预处理需严格按 `preprocess.json`：

1. 摄像头帧转灰度。
2. resize 到 `(height, width)`。
3. 若 `channels=3`，复制到三通道。
4. `x = x / 255.0`（`pixel_scale`）。
5. `x = (x - mean) / std`（逐通道）。

低置信度（`confidence < 阈值`）时显示"暂时无法稳定判断当前表情。"，且**不得**触发
情绪安慰。多帧平滑与提醒冷却由 Flutter 端 `expression_smoother` 实现。
