# 面部表情识别训练与 LiteRT 部署

该模块实现多数据集自动检测、统一标签映射、哈希去重、分层划分、四模型训练、验证/测试评估、LiteRT 导出和 Android 部署资产生成。识别对象是画面中可观察到的面部表情，不是心理状态、疲劳程度或疾病诊断。

## 固定契约

- 类别顺序：`angry, disgust, fear, happy, neutral, sad, surprise`
- Android 映射：`ANGRY, DISGUST, FEAR, HAPPY, NEUTRAL, SAD, SURPRISE`
- 最终模型输入：`1 × 96 × 96 × 3`，NHWC、RGB、float32
- 像素处理：`[0,255] → [0,1]`，再按 ImageNet mean `[0.485,0.456,0.406]` 和 std `[0.229,0.224,0.225]` 归一化
- `NO_FACE` 由 Android ML Kit 人脸检测产生；`UNKNOWN` 由置信度、分散概率或多帧不稳定产生
- 部署置信度阈值：`0.70`，依据清洗后 validation 的覆盖率/选择性准确率确定

## 目录

- `configs/`：Baseline CNN、ResNet18、MobileNetV3-Small、EfficientNet-B0 固定配置
- `src/expression_recognition/`：清单构建、训练、评估、导出实现
- `scripts/`：从零复现训练与重新导出入口
- `tests/`：审计、指标和模型单元测试
- `manifests_v2/`：多数据集统一清单（included/excluded/quarantined + dataset_inventory.json）
- `runs_v2/`：v2 checkpoint、逐 epoch 日志和解析后配置
- `reports/generated_v2/`：真实指标、混淆矩阵、曲线和预测分布
- `exports_v2/resnet18/`：float32/动态 int8 LiteRT、SHA-256、元数据和最佳 checkpoint

v1 旧训练结果保留在 `manifests/`、`runs/`、`reports/generated/`、`exports/` 中，不被覆盖。

生成物目录默认不进入 Git；Android 实际运行所需的模型和元数据复制到 `android/app/src/main/assets/`。

## 数据集

训练数据位于 `K:\人脸数据集`，包含 3 个自动检测到的数据集：

| 数据集 | 图片数 | 尺寸 | 通道 | 标签格式 |
|---|---:|---|---|---|
| 2013 (FER2013) | 35,887 | 48×48 | 1 | 类别文件夹 |
| DATASET (RAF-DB aligned) | 15,339 | 100×100 | 3 | 数值 1-7 |
| archive (3) | 30,626 | 96×96 | 3 | 文件夹名 + CSV |

`unified_manifest.py` 自动识别三种布局（类别文件夹、train/test/val 目录、CSV 标签），统一映射为七类，使用 SHA-256 全局去重，按类别分层划分 train/val/test。合计 81,852 张，去重后 included 76,137。

## 从零复现

要求 Windows、`uv`、可用的 NVIDIA 驱动，以及只读数据源 `K:\人脸数据集`。脚本在本模块内创建 Python 3.12 独立环境，不修改系统 Python 或后端虚拟环境。

```powershell
Set-Location F:\demo1\ml\expression_recognition
.\scripts\reproduce_training.ps1 -DatasetRoot 'K:\人脸数据集'
```

这会安装官方 CUDA 13.0 PyTorch wheel、运行环境自检与 pytest、构建多数据集统一清单、依次执行四个模型的 smoke test 和完整训练与评估。

## 恢复中断训练

下面示例从 ResNet18 的 `last.pt` 恢复；恢复时继续沿用 checkpoint 内保存的模型、优化器、调度器、AMP scaler、epoch、早停计数和历史：

```powershell
& .\.venv\Scripts\python.exe -m expression_recognition.train --config configs\resnet18.yaml --manifest manifests_v2\included.csv --run-dir runs_v2\full_resnet18 --resume runs_v2\full_resnet18\last.pt
```

## 评估

候选模型只在 validation 上比较。架构和阈值锁定后，test 仅用于最终评估及已锁定导出模型的数值回归：

```powershell
& .\.venv\Scripts\python.exe -m expression_recognition.evaluate --checkpoint runs_v2\full_resnet18\best.pt --manifest manifests_v2\included.csv --split validation --output-dir reports\generated_v2\resnet18
```

## LiteRT 导出与验证

```powershell
.\scripts\export_litert_v2.ps1
```

脚本优先尝试官方 AI Edge Torch。当前 Windows 环境缺少官方 `torch_xla` wheel，因此 `auto` 会记录原始失败原因，并使用 TensorFlow 中的同构 ResNet18 权重转移 + 官方 TensorFlow Lite Converter。只有 PyTorch↔TensorFlow 固定样本 logit 对齐通过后才继续生成 LiteRT。没有使用第三方 ONNX 转换链。

当前真实结果和限制见 [训练报告](reports/TRAINING_REPORT.md)。

## 目标域高精度提升流程

CPM 场景的新数据必须先提供 `annotations.csv`，字段为
`path,label,subject_id,session_id,device,platform,lighting,pose,occlusion,consent`。
`target_manifest.build_target_manifest` 会拒绝未授权或元数据不完整的样本、隔离跨标签重复图片，并按人物整体分配
train/validation/test，防止同一人不同会话泄漏。

目标域训练使用公开数据保持泛化、目标域数据修正前摄分布，且 validation 只读取目标域：

```powershell
& .\.venv\Scripts\python.exe -m expression_recognition.train `
  --config configs\resnet18_target_finetune.yaml `
  --manifest manifests_v2\included.csv `
  --target-manifest manifests_target\included.csv `
  --run-dir runs_target\resnet18_target
```

校准会对 SAD/ANGRY/FEAR/DISGUST 使用 90% Precision 目标，其他类别使用 85%。某个类别无法在 validation
达到目标或有效样本不足时，该类别阈值写为 `1.01` 并标记为 disabled；不得为了提高覆盖率降低生产精度门禁。
