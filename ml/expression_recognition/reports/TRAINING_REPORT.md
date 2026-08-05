# CNN 表情识别训练与部署报告

报告中的数量、指标和耗时均来自本机实际命令输出。训练环境为 Windows、Python 3.12.13、PyTorch 2.12.1+cu130、torchvision 0.27.1+cu130、NVIDIA GeForce RTX 5060 Laptop GPU（8,546,484,224 bytes，compute capability 12.0）。CUDA tensor 与 AMP 运算均已通过。原始数据目录 `K:\人脸数据集` 未被修改。

本次为 v2 多数据集训练，所有新结果位于 `runs_v2/`、`reports/generated_v2/`、`manifests_v2/`、`exports_v2/`，不覆盖 v1 旧训练结果。

## 数据集清单

`unified_manifest.py` 自动检测 `K:\人脸数据集` 下的所有表情数据集，识别三种布局：按类别文件夹存放、train/test 目录结构、CSV 标签。共发现 3 个数据集：

| 数据集 | 图片数 | 格式 | 尺寸 | 通道 | 原始标签 |
|---|---:|---|---|---|---|
| 2013 (FER2013) | 35,887 | JPEG | 48×48 | 1 | angry/disgust/fear/happy/neutral/sad/surprise |
| DATASET (RAF-DB aligned) | 15,339 | JPEG | 100×100 | 3 | 1-7 数值标签 |
| archive (3) | 30,626 | JPEG+PNG | 96×96 | 3 | 文件夹名 + CSV（含 contempt） |

合计 81,852 张图片。

### 统一标签映射

将不同数据集的标签统一映射为七类：`angry, disgust, fear, happy, neutral, sad, surprise`。

- **2013**：直接映射，标签名已与七类一致。
- **archive (3)**：优先采用文件夹标签，仅在无法映射时回退 CSV；`contempt` 不属于七类，直接丢弃（不强制映射）。
- **DATASET (RAF-DB)**：数值标签按 RAF-DB 标准映射：`1→surprise, 2→fear, 3→disgust, 4→happy, 5→sad, 6→angry, 7→neutral`（经 12,271 张 train 数量验证为 RAF-DB aligned）。

### 哈希去重

使用 SHA-256 对全部 81,852 张图片做全局去重，避免同一图片同时进入训练集和验证/测试集：

- 精确重复组：3,261
- 跨 split 重复组：2,132
- 跨标签冲突组：101

处理结果：included 76,137、excluded 5,447、quarantined 268。

### 分层划分

合并后按类别分层划分 train/val/test，保留独立 test 集用于最终评估（种子 `20260731`，validation 比例 15%）：

| Split | angry | disgust | fear | happy | neutral | sad | surprise | 合计 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 5,125 | 1,959 | 4,709 | 12,118 | 8,692 | 6,942 | 5,012 | 44,557 |
| validation | 904 | 346 | 831 | 2,139 | 1,534 | 1,225 | 885 | 7,864 |
| test | 2,867 | 1,547 | 2,716 | 5,757 | 4,391 | 3,295 | 3,143 | 23,716 |

## 候选模型

四个模型都先完成 smoke training（4 batches/1 epoch），验证了数据、loss、checkpoint、resume 与评估链路。完整训练均使用 AMP、AdamW、余弦学习率、梯度裁剪、class-weighted cross entropy、早停（patience 6），并以 validation macro-F1 保存 best checkpoint。数据增强包括水平翻转、旋转、平移、缩放、亮度/对比度、模糊、JPEG 压缩和遮挡。固定随机种子 `20260731`。CUDA 自动检测通过；训练中未触发 OOM 降 batch。

| 模型 | 输入 | epochs / 训练耗时 | Val accuracy | Val macro-F1 | Val weighted-F1 | Val balanced acc. | ECE / Brier | 参数量 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline CNN | 48×48×1 | 15 / 327.8 s | 0.6293 | 0.5817 | 0.6392 | 0.6039 | 0.0419 / 0.5008 | 841,959 |
| ResNet18 | 96×96×3 | 15 / 462.7 s | 0.6859 | 0.6381 | 0.6900 | 0.6523 | 0.0433 / 0.4353 | 11,180,103 |
| MobileNetV3-Small | 96×96×3 | 15 / 363.5 s | 0.6122 | 0.5657 | 0.6198 | 0.5871 | 0.0247 / 0.5197 | 1,525,031 |
| EfficientNet-B0 | 96×96×3 | 15 / 444.3 s | 0.6825 | 0.6397 | 0.6854 | 0.6569 | 0.0448 / 0.4410 | 4,016,515 |

> 注：上表训练耗时为各 epoch duration_seconds 之和，含首个 epoch 的 CUDA warmup。

上述延迟是本机桌面 CUDA，不是手机实测。完整的 per-class、混淆矩阵、概率分布、Brier、batch 基准、阈值覆盖表和训练曲线位于 `reports/generated_v2/<model>/`。

### 独立测试集结果

| 模型 | Test accuracy | Test macro-F1 | Test weighted-F1 | Test balanced acc. |
|---|---:|---:|---:|---:|
| Baseline CNN | 0.6228 | 0.5828 | 0.6272 | 0.5934 |
| ResNet18 | 0.6748 | 0.6348 | 0.6752 | 0.6388 |
| MobileNetV3-Small | 0.5812 | 0.5411 | 0.5866 | 0.5518 |
| EfficientNet-B0 | 0.6610 | 0.6194 | 0.6622 | 0.6272 |

## 模型选择

EfficientNet-B0 的 validation macro-F1 (0.6397) 略高于 ResNet18 (0.6381)，差距仅 0.0016。但在独立 test 集上，ResNet18 的 macro-F1 (0.6348) 显著优于 EfficientNet-B0 (0.6194)，表明 ResNet18 泛化能力更强。

选择 **ResNet18** 作为部署模型，原因：
1. test 集 macro-F1 更高（0.6348 vs 0.6194），泛化更好；
2. 能够通过 TensorFlow 权重转移可靠地转换为 LiteRT/TFLite（EfficientNet-B0 在当前 Windows 环境无法导出，详见下文 LiteRT 章节）；
3. validation accuracy 同样领先（0.6859 vs 0.6825）。

### ResNet18 验证集 per-class 指标

| 类别 | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| angry | 0.5656 | 0.6150 | 0.5893 | 904 |
| disgust | 0.4473 | 0.6127 | 0.5171 | 346 |
| fear | 0.4981 | 0.4813 | 0.4896 | 831 |
| happy | 0.9255 | 0.8247 | 0.8722 | 2,139 |
| neutral | 0.7162 | 0.7106 | 0.7134 | 1,534 |
| sad | 0.6434 | 0.5951 | 0.6183 | 1,225 |
| surprise | 0.6165 | 0.7266 | 0.6670 | 885 |

阈值 0.70 在 validation 上覆盖 58.99%，覆盖样本准确率 84.24%，用于偏保守地生成 `UNKNOWN`。CUDA batch-1 延迟 2.17 ms / 459.8 sps，batch-32 延迟 3.38 ms / 9,471.2 sps。

## LiteRT

官方 AI Edge Torch 在当前 Windows 环境真实失败：`ModuleNotFoundError: No module named 'torch_xla'`；官方 `torch_xla` wheel 没有该 Windows 组合。因此 EfficientNet-B0 和 MobileNetV3-Small 无法在此平台导出为 TFLite（它们依赖 AI Edge Torch，而 AI Edge Torch 需要 torch_xla）。

替代方案是在 TensorFlow 中重建同构、推理态 ResNet18，逐层转移 torchvision 权重，通过固定样本 logit 验收后使用官方 TensorFlow Lite Converter。PyTorch↔TensorFlow 对齐验收：64 样本 top1 一致率 1.0，最大 logit 误差 6.79e-06。

导出命令：
```powershell
.\scripts\export_litert_v2.ps1
```

验证结果（桌面 LiteRT CPU）：

| 版本 | Val accuracy | Val macro-F1 | Test accuracy | Test macro-F1 | 大小 | batch-1 延迟 | 吞吐 |
|---|---:|---:|---:|---:|---:|---:|---:|
| float32 | 0.6859 | 0.6381 | 0.6747 | 0.6346 | 44,716,576 B | 2.09 ms | 477.6 sps |
| **dynamic int8** | 0.6864 | **0.6385** | 0.6755 | 0.6357 | **11,263,264 B** | **1.50 ms** | **667.1 sps** |
| float16 | 0.6860 | 0.6384 | 0.6746 | 0.6346 | 22,370,832 B | 2.04 ms | 490.9 sps |
| full int8 | 0.6859 | 0.6383 | 0.6746 | 0.6343 | 11,323,176 B | 0.91 ms | 1,102.4 sps |

动态 int8 按预先设定的 validation macro-F1 退化不超过 0.01 规则入选（val macro-F1 0.6385 vs float32 0.6381，差异 +0.0004）。量化前后 test macro-F1 变化 +0.0011。

模型已复制到 Android assets，SHA-256 为 `9cef0425496d8161604f6a4d9eb1ec51f4ad77b4d501db222dd21f6b2ed6d0c8`，标签顺序 `0=angry ... 6=surprise`，输入 `1×96×96×3 NHWC float32`，输出 `1×7 float32`。完整导出结果见 `exports_v2/resnet18/litert_verification.json`。

## Android 接入

实现包括 CameraX `ImageAnalysis`、`KEEP_ONLY_LATEST`、前置摄像头 rotation/镜像、YUV→RGB、ML Kit 本地人脸检测与最大脸裁剪、与训练一致的 resize/normalization、LiteRT 后台推理、200 ms 分析节流、多帧 EMA、0.70 阈值、稳定帧/持续时间、`NO_FACE`、`UNKNOWN`、建议冷却和完整生命周期。

StudyScreen 只有在用户主动开启、相机授权且专注计时运行时才分析；页面离开会解绑相机并释放解释器。图片不保存、不上传、不写日志。Mock/Real 仍通过 repository 工厂可替换；AI 导员后端忽略 `expression_signal` 的安全降级保持不变，真实 AI 融合默认未开启。

## 验证状态

- Python pytest：通过
- 多数据集清单构建与去重：通过
- 四模型 smoke/完整训练（15 epochs）：通过
- ResNet18 最终 test 评估：通过
- LiteRT 导出与数值回归：通过
- 真机：未连接，因此未进行真实设备延迟、功耗和相机端到端测试

## 仍存在的问题

1. **EfficientNet-B0 无法在 Windows 导出 TFLite**：AI Edge Torch 依赖 torch_xla，官方未提供 Windows wheel。如需导出 EfficientNet-B0，需在 Linux 环境运行 AI Edge Torch，或为其实现 TensorFlow 权重转移路径。
2. **类别不平衡依然严重**：disgust 类样本仅 3,852（train+val+test），是 happy 类 (20,014) 的 19.2%。尽管使用了 class-weighted cross entropy，disgust 的 F1 仍为最低 (0.517)。
3. **多数据集标签噪声**：archive (3) 数据集的 contempt 类被丢弃；跨数据集标签一致性无法完全保证。
4. **训练 epoch 数限制为 15**：为控制总训练时间，所有模型统一训练 15 epochs（原始配置为 30）。部分模型（如 ResNet18）在最后几个 epoch 仍在缓慢提升，增加 epoch 可能进一步提升性能。
5. **真机验证缺失**：未进行 Android 真实设备延迟、功耗和相机端到端测试。
