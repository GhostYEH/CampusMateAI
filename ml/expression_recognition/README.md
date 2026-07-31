# 面部表情识别训练与 LiteRT 部署

该模块实现 FER2013 风格数据的只读审计、三模型训练、验证/测试评估、LiteRT 导出和 Android 部署资产生成。识别对象是画面中可观察到的面部表情，不是心理状态、疲劳程度或疾病诊断。

## 固定契约

- 类别顺序：`angry, disgust, fear, happy, neutral, sad, surprise`
- Android 映射：`ANGRY, DISGUST, FEAR, HAPPY, NEUTRAL, SAD, SURPRISE`
- 最终模型输入：`1 × 96 × 96 × 3`，NHWC、RGB、float32
- 像素处理：`[0,255] → [0,1]`，再按 ImageNet mean `[0.485,0.456,0.406]` 和 std `[0.229,0.224,0.225]` 归一化
- `NO_FACE` 由 Android ML Kit 人脸检测产生；`UNKNOWN` 由置信度、分散概率或多帧不稳定产生
- 部署置信度阈值：`0.70`，依据清洗后 validation 的覆盖率/选择性准确率确定

## 目录

- `configs/`：baseline、ResNet18、MobileNetV3-Small 固定配置
- `src/expression_recognition/`：审计、训练、评估、导出实现
- `scripts/`：从零复现训练与重新导出入口
- `tests/`：审计、指标和模型单元测试
- `manifests/`：生成的 included/excluded/quarantined 清单，不复制原始图片
- `runs/`：checkpoint、逐 epoch 日志和解析后配置
- `reports/generated/`：真实指标、混淆矩阵、曲线和预测分布
- `exports/resnet18/`：float32/动态 int8 LiteRT、SHA-256、元数据和最佳 checkpoint

生成物目录默认不进入 Git；Android 实际运行所需的模型和元数据复制到 `android/app/src/main/assets/`。

## 从零复现

要求 Windows、`uv`、可用的 NVIDIA 驱动，以及只读数据源 `K:\人脸数据集`。脚本在本模块内创建 Python 3.12 独立环境，不修改系统 Python 或后端虚拟环境。

```powershell
Set-Location F:\demo1\ml\expression_recognition
.\scripts\reproduce_training.ps1 -DatasetRoot 'K:\人脸数据集'
```

这会安装官方 CUDA 13.0 PyTorch wheel、运行环境自检与 pytest、重做数据审计、依次执行三个模型的 smoke test 和完整训练。不会自动使用 test 调参。

## 恢复中断训练

下面示例从 ResNet18 的 `last.pt` 恢复；恢复时继续沿用 checkpoint 内保存的模型、优化器、调度器、AMP scaler、epoch、早停计数和历史：

```powershell
& .\.venv\Scripts\python.exe -m expression_recognition.train --config configs\resnet18.yaml --manifest manifests\included.csv --run-dir runs\full_resnet18 --resume runs\full_resnet18\last.pt
```

## 评估

候选模型只在 validation 上比较。架构和阈值锁定后，test 仅用于最终评估及已锁定导出模型的数值回归：

```powershell
& .\.venv\Scripts\python.exe -m expression_recognition.evaluate --checkpoint runs\full_resnet18\best.pt --manifest manifests\included.csv --split validation --output-dir reports\generated\resnet18
```

## LiteRT 导出与验证

```powershell
.\scripts\export_litert.ps1 -Checkpoint 'runs\full_resnet18\best.pt' -Manifest 'manifests\included.csv'
```

脚本优先尝试官方 AI Edge Torch。当前 Windows 环境缺少官方 `torch_xla` wheel，因此 `auto` 会记录原始失败原因，并使用 TensorFlow 中的同构 ResNet18 权重转移 + 官方 TensorFlow Lite Converter。只有 PyTorch↔TensorFlow 固定样本 logit 对齐通过后才继续生成 LiteRT。没有使用第三方 ONNX 转换链。

当前真实结果和限制见 [训练报告](reports/TRAINING_REPORT.md) 与 [模型卡](reports/MODEL_CARD.md)。
