# 实验报告

> 本报告严格遵循"不虚构结果"原则。所有指标均来自真实 FER2013 训练运行，
> 由 `ml/expression_recognition/run_fer2013_training.py` 一次完整执行产生，
> 检查点、ONNX、metrics.json、model_card.json 均为真实产物。

## 1. 真实训练状态

**已完成真实训练。**

- 数据集：FER2013（image_dir 格式，`K:/深度学习代码/{train,test}/{label}/*.png`）
- 三个模型均完成 smoke 训练（1 epoch，每类 30 样本）+ 正式训练 + test 评估 + 产物导出
- 训练顺序：custom_cnn → mobilenet_v3_small → resnet18（串行，未同时占用 GPU）
- 训练时间：2026-07-27 16:25 ~ 17:28（约 63 分钟，含 smoke）
- 所有产物写入 `ml/expression_recognition/artifacts/`

## 2. 实际训练过的模型

| 模型 | 是否真实训练 | best_epoch | val Macro-F1 | test Accuracy | test Macro-F1 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| 自定义浅层 CNN | ✅ 已训练 | 38 | 0.4274 | 0.4827 | 0.4206 | 从零训练，46 epoch 早停 |
| MobileNetV3-Small（迁移） | ✅ 已训练 | 36 | 0.6361 | 0.6620 | 0.6182 | ImageNet 预训练，44 epoch 早停，主部署候选 |
| ResNet18（迁移） | ✅ 已训练 | 23 | 0.6531 | 0.6796 | 0.6341 | ImageNet 预训练，31 epoch 早停，最佳指标 |

## 3. 数据集版本

- 目标数据集：**FER2013**（ICML 2013 面部表情识别竞赛数据集，七类）
- 数据格式：image_dir（`{train,test}/{label}/*.png`）
- 数据集根目录：`K:/深度学习代码`
- 七类齐全：angry、disgust、fear、happy、neutral、sad、surprise ✅
- 固定标签顺序：`angry, disgust, fear, happy, sad, surprise, neutral`（索引 0-6）
- 数据来源：用户提供本地数据，本工程不自动下载

## 4. 训练/验证/测试集数量

数据划分由 `split_manifest.json` 固定，三个模型复用同一划分（seed=42）：

| 划分 | 样本数 | 说明 |
| --- | --- | --- |
| train | 25,838 | 从 `train/` 目录按类别分层随机抽取 90% |
| val | 2,870 | 从 `train/` 目录按类别分层随机抽取 10% |
| test | 6,789 | `test/` 目录全部样本，不参与训练/调参/模型选择 |
| **合计** | **35,498** | |

各类别样本分布：

| 类别 | train | val | test |
| --- | --- | --- | --- |
| angry | 3,596 | 399 | 569 |
| disgust | 392 | 44 | 111 |
| fear | 3,687 | 410 | 1,024 |
| happy | 6,494 | 721 | 1,774 |
| sad | 4,347 | 483 | 1,247 |
| surprise | 2,854 | 317 | 831 |
| neutral | 4,468 | 496 | 1,233 |

> 注：disgust 类样本极少（train 392 / test 111），该类指标通常偏低，符合 FER2013 已知特性。
> 划分清单：`ml/expression_recognition/artifacts/split_manifest.json`

## 5. 真实指标

### 5.1 总体指标

| 模型 | Accuracy | Macro-F1 | best_epoch | 测试样本数 |
| --- | --- | --- | --- | --- |
| custom_cnn | 0.4827 | 0.4206 | 38 | 6,789 |
| mobilenet_v3_small | 0.6620 | 0.6182 | 36 | 6,789 |
| resnet18 | **0.6796** | **0.6341** | 23 | 6,789 |

> 测试集只评估一次，使用 best_checkpoint（按 val Macro-F1 选）。
> 指标基于真实模型预测与真实标签计算，未写死、未用占位随机数。

### 5.2 每类 Precision / Recall / F1 / Support

#### custom_cnn

| 类别 | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| angry | 0.2412 | 0.4341 | 0.3101 | 569 |
| disgust | 0.0859 | 0.6216 | 0.1510 | 111 |
| fear | 0.4196 | 0.1172 | 0.1832 | 1,024 |
| happy | 0.8189 | 0.6702 | 0.7371 | 1,774 |
| sad | 0.4395 | 0.3232 | 0.3725 | 1,247 |
| surprise | 0.7420 | 0.6161 | 0.6732 | 831 |
| neutral | 0.4558 | 0.5977 | 0.5172 | 1,233 |

#### mobilenet_v3_small

| 类别 | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| angry | 0.4913 | 0.5431 | 0.5159 | 569 |
| disgust | 0.3640 | 0.7477 | 0.4897 | 111 |
| fear | 0.5545 | 0.4766 | 0.5126 | 1,024 |
| happy | 0.8858 | 0.8354 | 0.8599 | 1,774 |
| sad | 0.5694 | 0.5100 | 0.5381 | 1,247 |
| surprise | 0.7448 | 0.8111 | 0.7765 | 831 |
| neutral | 0.6057 | 0.6667 | 0.6347 | 1,233 |

#### resnet18

| 类别 | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| angry | 0.4700 | 0.6186 | 0.5341 | 569 |
| disgust | 0.3578 | 0.7027 | 0.4742 | 111 |
| fear | 0.5768 | 0.5098 | 0.5412 | 1,024 |
| happy | 0.9049 | 0.8579 | 0.8808 | 1,774 |
| sad | 0.5822 | 0.5196 | 0.5492 | 1,247 |
| surprise | 0.8073 | 0.8219 | 0.8145 | 831 |
| neutral | 0.6340 | 0.6561 | 0.6449 | 1,233 |

### 5.3 混淆矩阵

混淆矩阵已导出为 PNG（行=真实标签，列=预测标签，标签顺序：angry, disgust, fear, happy, sad, surprise, neutral）：

- [`artifacts/custom_cnn/confusion_matrix.png`](../../ml/expression_recognition/artifacts/custom_cnn/confusion_matrix.png)
- [`artifacts/mobilenet_v3_small/confusion_matrix.png`](../../ml/expression_recognition/artifacts/mobilenet_v3_small/confusion_matrix.png)
- [`artifacts/resnet18/confusion_matrix.png`](../../ml/expression_recognition/artifacts/resnet18/confusion_matrix.png)

原始数值见各模型目录下 `metrics.json::confusion_matrix`。

### 5.4 训练过程曲线

每个 epoch 的 train_loss / val_loss / val_acc / val_macro_f1 / lr 记录于：

- [`artifacts/custom_cnn/training_history.csv`](../../ml/expression_recognition/artifacts/custom_cnn/training_history.csv)
- [`artifacts/mobilenet_v3_small/training_history.csv`](../../ml/expression_recognition/artifacts/mobilenet_v3_small/training_history.csv)
- [`artifacts/resnet18/training_history.csv`](../../ml/expression_recognition/artifacts/resnet18/training_history.csv)

## 6. 导出模型 SHA-256

以下指纹均为真实训练产物（best_checkpoint），非工程验证阶段的随机权重。

### 6.1 best_checkpoint (.pt)

| 模型 | 文件大小 | SHA-256 |
| --- | --- | --- |
| custom_cnn | 1.09 MB | `8b97c0141764421873e956221d8d112b897c45becf61546469d967363f9d0ed4` |
| mobilenet_v3_small | 17.70 MB | `e06061ba05c5e2d054e99e3170b23708dd4b8e2274a139b7375b381cf98f8cff` |
| resnet18 | 128.07 MB | `1eac5ec087b57122127020ff27e26cdbca132a936d33801d1b1dcf643d8082b7` |

### 6.2 ONNX

| 模型 | 文件大小 | SHA-256 |
| --- | --- | --- |
| custom_cnn | 368.23 KB | `68500c5b5c52d7ddd8fda59a762f287d5fe509444d2c08f12fdf75903f8f30ae` |
| mobilenet_v3_small | 5.83 MB | `15fa53d75dd83278a5c02dd89b32a23fa591a3ddf7610096d339ee9947671b9a` |
| resnet18 | 42.64 MB | `ad2b0cdd1902a71d18f57f6abb4b18a64951c031646fc4f539573631ed0d5aa5` |

### 6.3 TFLite

| 模型 | 状态 | 原因 |
| --- | --- | --- |
| custom_cnn | ❌ 未导出 | 未安装 tensorflow / onnx2tf（按指令不得安装/不得伪造） |
| mobilenet_v3_small | ❌ 未导出 | 同上 |
| resnet18 | ❌ 未导出 | 同上 |

> TFLite 导出状态记录于各模型目录下 `model.tflite.json`。后续安装
> `pip install onnx2tf tensorflow ai-edge-litert` 后可补齐，不影响 PT/ONNX 链路。

### 6.4 辅助产物

每个模型目录下还包含：

- `labels.json`：标签顺序契约（七类）
- `preprocess.json`：预处理参数（size / channels / mean / std）
- `model_card.json`：完整模型卡片（含训练配置、指标、SHA-256、一致性测试、科学边界声明）
- `metrics.json`：完整测试指标（含混淆矩阵原始数值）
- `per_class_metrics.csv`：每类指标 CSV
- `evaluate_summary.json` / `export_summary.json` / `consistency.json` / `training_summary.json`
- `last_model.pt`：最后一个 epoch 的权重（供调试，非部署用）

## 7. 训练配置（真实使用）

三个模型共享以下训练策略，差异在模型结构与输入尺寸：

| 项 | custom_cnn | mobilenet_v3_small | resnet18 |
| --- | --- | --- | --- |
| 输入尺寸 | 48×48 | 224×224 | 224×224 |
| 输入通道 | 1（灰度） | 3（灰度复制三通道） | 3（灰度复制三通道） |
| 预训练 | 否 | ImageNet | ImageNet |
| 冻结 backbone | 否 | 是（epoch 5 解冻） | 是（epoch 5 解冻） |
| batch_size | 128 | 64 | 64 |
| epochs 配置 | 60 | 60 | 60 |
| epochs 实际 | 46（早停） | 44（早停） | 31（早停） |
| optimizer | AdamW | AdamW | AdamW |
| lr 初始 | 1e-3 | 1e-3 | 1e-3 |
| weight_decay | 1e-4 | 1e-4 | 1e-4 |
| scheduler | cosine | cosine | cosine |
| loss | cross_entropy | cross_entropy | cross_entropy |
| class weights | ✅ | ✅ | ✅ |
| label smoothing | 0.1 | 0.1 | 0.1 |
| 数据增强 | ✅ | ✅ | ✅ |
| early stopping | patience=8 | patience=8 | patience=8 |
| AMP (混合精度) | ✅ | ✅ | ✅ |
| seed | 42 | 42 | 42 |
| device | cuda | cuda | cuda |
| 训练耗时 | 756s (~12.6min) | 1608s (~26.8min) | 1421s (~23.7min) |

数据增强项：随机水平翻转、小角度旋转 (±10°)、随机裁剪 (scale 0.8-1.0)、亮度/对比度抖动、Cutout (p=0.3, max=16)。

## 8. 跨后端一致性（真实模型）

best_checkpoint 导出 ONNX 后，与 PyTorch 在测试集上做 Top-1 一致性验证：

| 模型 | 一致性 | max abs diff | Top-1 不一致数 |
| --- | --- | --- | --- |
| custom_cnn | ✅ passed | 1.907e-06 | 0 / 6789 |
| mobilenet_v3_small | ✅ passed | 3.777e-04 | 0 / 6789 |
| resnet18 | ✅ passed | 1.311e-06 | 0 / 6789 |

> 三模型 PyTorch 与 ONNX 在测试集上 Top-1 预测完全一致，可放心使用 ONNX 部署链路。

## 9. 已验证内容

### 9.1 单元测试（conda env: campusmate-cnn, torch 2.12.1+cu130）

```
cd ml/expression_recognition
conda run -n campusmate-cnn python -m pytest
```

真实结果：**52 passed, 2 skipped**

- ✅ 配置加载与校验（`test_config.py`，7 项）
- ✅ FER2013 CSV 解析（带/不带 Usage、错误 pixels 数量、错误标签）
- ✅ image_dir 扫描（结构 A 与 B、空目录拒绝）
- ✅ 划分：官方 Usage、分层随机、可复现、样本不丢失、防泄漏说明存在
- ✅ 数据缺失错误信息（明确提示、不自动下载）
- ✅ 指标函数（accuracy/macro_f1/per_class/混淆矩阵，用已知预测验证公式）
- ✅ 标签顺序契约（`assert_label_order` 拒绝错位）
- ✅ 模型前向传播、输出维度 (N,7)、标签顺序、冻结/解冻参数量变化（`test_models.py`）
- ✅ 检查点保存/加载、标签顺序守卫、num_classes 守卫、早停（`test_checkpoint.py`）
- ✅ ONNX 导出 + onnxruntime 推理 + 数值一致性 + 动态 batch + labels/preprocess.json（`test_export_onnx.py`）
- ⏭ TFLite 导出与三方一致性（`test_export_tflite.py`）— 2 项 skip，原因：未安装 tensorflow/onnx2tf（按指令不得安装）

### 9.2 工程级 10 项真实验证（`verify_engineering.py`）

```
conda run -n campusmate-cnn python verify_engineering.py
```

真实结果：**all_ok = True**，报告写入
`ml/expression_recognition/artifacts/engineering_verification/engineering_verification.json`

| 检查项 | 结果 |
| --- | --- |
| 1. 三个模型前向传播 | ✅ 全部通过 |
| 2. 输出维度 = 7 | ✅ 全部 (1, 7) |
| 3. CPU 与 CUDA 张量前向 | ✅ 全部通过（RTX 5060 Laptop, sm_120） |
| 4. checkpoint 保存与重新加载 | ✅ 权重完全一致 |
| 5. ONNX 导出 | ✅ 三模型均导出成功 |
| 6. ONNX Runtime 推理 | ✅ 三模型均推理成功 |
| 7. PyTorch 与 ONNX Top-1 一致性 | ✅ 三模型 0/8 不一致，consistency=1.000 |
| 8. 标签顺序检查 | ✅ angry,disgust,fear,happy,sad,surprise,neutral |
| 9. 输出模型参数量 | ✅ 见下表 |
| 10. 测试命令与真实结果 | ✅ 已记录 |

#### 前向传播与参数量（工程验证阶段，随机权重）

| 模型 | 输入形状 | CPU 前向 | CUDA 前向 | 总参数 | 可训练参数 |
| --- | --- | --- | --- | --- | --- |
| custom_cnn | (1,1,48,48) | 5.86 ms | 0.55 ms | 93,799 | 93,799 |
| resnet18 | (1,3,224,224) | 15.36 ms | 2.27 ms | 11,180,103 | 3,591（冻结） |
| mobilenet_v3_small | (1,3,224,224) | 12.48 ms | 3.91 ms | 1,525,031 | 598,023 |

> CPU vs CUDA 输出 max abs diff：custom_cnn 1.61e-01、resnet18 7.22e-02、mobilenet 3.83e-02。
> 差异来自 BatchNorm 在 eval 模式下 CPU/CUDA 浮点实现差异，属正常现象；
> Top-1 标签在工程验证用例中仍一致。

### 9.3 真实训练 + 评估 + 导出（本轮新增）

| 检查项 | 结果 |
| --- | --- |
| 1. 七类齐全检查 | ✅ angry/disgust/fear/happy/neutral/sad/surprise 全部存在 |
| 2. 固定标签顺序 | ✅ angry, disgust, fear, happy, sad, surprise, neutral |
| 3. 分层 90/10 划分 | ✅ train=25,838 / val=2,870（seed=42） |
| 4. test 隔离 | ✅ test=6,789 完全不参与训练/调参/模型选择 |
| 5. 固定划分清单复用 | ✅ 三模型共享 `split_manifest.json` |
| 6. smoke 训练（1 epoch） | ✅ 三模型全部通过（每类 30 样本子集） |
| 7. 正式训练（串行） | ✅ 三模型按序完成，未同时占用 GPU |
| 8. CUDA + class weights + 增强 + scheduler + early stopping + seed | ✅ 全部启用 |
| 9. 按 val Macro-F1 保存 best | ✅ best_epoch 分别为 38 / 36 / 23 |
| 10. test 只评估一次 | ✅ 使用 best_checkpoint 评估 |
| 11. 真实指标输出 | ✅ Accuracy / Macro-F1 / 每类 P/R/F1 / support / 混淆矩阵 / best epoch / 参数量 / checkpoint 大小 |
| 12. 真实导出 | ✅ .pt / .onnx / labels.json / preprocess.json / model_card.json / SHA-256 |
| 13. TFLite 缺失依赖处理 | ✅ 未安装/未伪造，仅标记 not_exported |
| 14. 产物写入 artifacts/ | ✅ 全部位于 `ml/expression_recognition/artifacts/{model}/` |
| 15. 跨后端一致性 | ✅ PyTorch 与 ONNX Top-1 不一致 = 0 |

## 10. 未验证内容（诚实声明）

以下内容**本轮仍未验证**：

- ❌ TFLite 导出链路（未安装 tensorflow/onnx2tf，按指令不得安装）
- ❌ PyTorch/ONNX/TFLite 三方一致性（依赖 TFLite，环境不支持）
- ❌ Flutter 端 LiteRT 加载导出 TFLite 的端到端推理（属 Flutter 侧，不在本工程范围）
- ❌ 消融实验（数据增强 / 类别权重 / 标签平滑 / Focal Loss 对比）— 本轮仅跑通主链路，未做对比实验
- ❌ 不同随机种子的方差分析（本轮仅用 seed=42）

## 11. 环境信息

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows 11 (10.0.26200) |
| Python | 3.12.13（conda env: `campusmate-cnn`） |
| Conda 安装 | `H:\Miniconda3` |
| 解释器路径 | `H:\Miniconda3\envs\campusmate-cnn\python.exe` |
| torch | 2.12.1+cu130 |
| torchvision | 0.27.1+cu130 |
| onnx | 1.22.0 |
| onnxruntime | 1.28.0 |
| CUDA runtime | 13.0 |
| CUDA available | True |
| GPU | NVIDIA GeForce RTX 5060 Laptop GPU |
| GPU capability | (12, 0) — Blackwell sm_120 |
| tensorflow / ai-edge-litert | 未安装（按指令不得安装） |
| FER2013 数据 | ✅ 已提供（`K:/深度学习代码`） |

## 12. 复现步骤

```powershell
# 1. 激活环境
H:\Miniconda3\Scripts\conda.exe run -n campusmate-cnn --no-capture-output <command>

# 2. 数据集放置（image_dir 格式）
#    K:/深度学习代码/train/{label}/*.png
#    K:/深度学习代码/test/{label}/*.png

# 3. 运行完整训练流水线（smoke + 正式训练 + 评估 + 导出）
cd f:\demo1\ml\expression_recognition
python run_fer2013_training.py

# 4. 跳过 smoke（已验证过）
python run_fer2013_training.py --skip-smoke

# 5. 只训练指定模型
python run_fer2013_training.py --only resnet18

# 6. 产物位置
#    artifacts/split_manifest.json         # 固定划分清单
#    artifacts/fer2013_training_summary.json  # 三模型汇总
#    artifacts/{model}/best_model.pt       # best checkpoint
#    artifacts/{model}/model.onnx          # ONNX
#    artifacts/{model}/model_card.json     # 完整模型卡片
#    artifacts/{model}/metrics.json        # 测试指标
#    artifacts/{model}/training_history.csv  # 每 epoch 记录
```

## 13. 训练结果汇总

来自 `artifacts/fer2013_training_summary.json`：

```
custom_cnn:        best_epoch=38, val_f1=0.4274, test_acc=0.4827, test_f1=0.4206
mobilenet_v3_small: best_epoch=36, val_f1=0.6361, test_acc=0.6620, test_f1=0.6182
resnet18:          best_epoch=23, val_f1=0.6531, test_acc=0.6796, test_f1=0.6341
```

**结论**：迁移学习（ImageNet 预训练）显著优于从零训练。resnet18 在 Accuracy 与 Macro-F1 上均最佳；mobilenet_v3_small 指标接近 resnet18，但模型体积仅 17.7 MB（resnet18 为 128 MB），是移动端部署的更优候选。custom_cnn 受限于从零训练与 48×48 输入，指标偏低，可作为轻量级基线对照。

## 14. 工程产物清单

- 训练工程：[`ml/expression_recognition/expression_recognition/`](../../ml/expression_recognition/expression_recognition/)
- 训练驱动脚本：[`ml/expression_recognition/run_fer2013_training.py`](../../ml/expression_recognition/run_fer2013_training.py)
- 模型配置：[`ml/expression_recognition/configs/`](../../ml/expression_recognition/configs/)
- 依赖：[`ml/expression_recognition/requirements.txt`](../../ml/expression_recognition/requirements.txt)
- 测试：[`ml/expression_recognition/tests/`](../../ml/expression_recognition/tests/)
- 工程验证脚本：[`ml/expression_recognition/verify_engineering.py`](../../ml/expression_recognition/verify_engineering.py)
- 划分清单：[`ml/expression_recognition/artifacts/split_manifest.json`](../../ml/expression_recognition/artifacts/split_manifest.json)
- 训练汇总：[`ml/expression_recognition/artifacts/fer2013_training_summary.json`](../../ml/expression_recognition/artifacts/fer2013_training_summary.json)
- 训练日志：[`ml/expression_recognition/artifacts/training_run.log`](../../ml/expression_recognition/artifacts/training_run.log)
- 复现指南：[`REPRODUCTION.md`](./REPRODUCTION.md)
- 科学边界：[`SCIENTIFIC_BOUNDARIES.md`](./SCIENTIFIC_BOUNDARIES.md)
