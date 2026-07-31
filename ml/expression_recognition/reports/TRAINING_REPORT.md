# CNN 表情识别训练与部署报告

报告中的数量、指标和耗时均来自本机实际命令输出。训练环境为 Windows、Python 3.12.13、PyTorch 2.12.1+cu130、torchvision 0.27.1+cu130、NVIDIA GeForce RTX 5060 Laptop GPU（8,546,484,224 bytes，compute capability 12.0）。CUDA tensor 与 AMP 运算均已通过。原始数据目录未被修改。

## 数据审计

清洗前：

| Split | angry | disgust | fear | happy | neutral | sad | surprise | 合计 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 3,995 | 436 | 4,097 | 7,215 | 4,965 | 4,830 | 3,171 | 28,709 |
| test | 958 | 111 | 1,024 | 1,774 | 1,233 | 1,247 | 831 | 7,178 |

审计确认全部 35,887 张均可解码、为 JPEG、48×48、单通道。实际发现 1,516 个 SHA-256 精确重复组、506 个跨 train/test 重复组、57 个跨标签冲突组。处理结果：

- 隔离跨标签冲突图片 160 张；
- 排除跨 split 的训练侧重复 682 张，保留 test 规范样本；
- 排除同 split 同标签重复 1,068 张；
- included 33,977、excluded 1,750、quarantined 160。

清洗后按种子 `20260731` 对训练候选做 15% 分层 validation：

| Split | angry | disgust | fear | happy | neutral | sad | surprise | 合计 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 3,210 | 298 | 3,227 | 5,975 | 4,099 | 3,975 | 2,091 | 22,875 |
| validation | 566 | 52 | 570 | 1,055 | 723 | 702 | 369 | 4,037 |
| test | 941 | 108 | 1,005 | 1,764 | 1,224 | 1,235 | 788 | 7,065 |

## 候选模型

三个模型都先完成 4 batches/1 epoch smoke training，验证了数据、loss、checkpoint、resume 与评估链路。完整训练均使用 AMP、AdamW、余弦学习率、梯度裁剪、class-weighted cross entropy、早停，并以 validation macro-F1 保存 best checkpoint。

| 模型 | 输入 | epochs / 训练耗时 | Val accuracy | Val macro-F1 | Val weighted-F1 | Val balanced acc. | ECE / Brier | 参数量 | Checkpoint | CUDA batch-1 / 吞吐 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline CNN | 48×48×1 | 30 / 168.71 s | 0.61779 | 0.57611 | 0.61657 | 0.61889 | 0.05569 / 0.51619 | 841,959 | 10,148,077 B | 0.775 ms / 1,290.8 sps |
| ResNet18 | 96×96×3 | 28 / 251.34 s | 0.66782 | **0.64834** | 0.66516 | **0.64275** | 0.04332 / 0.49221 | 11,180,103 | 134,282,281 B | 1.858 ms / 538.3 sps |
| MobileNetV3-Small | 96×96×3 | 25 / 218.58 s | 0.60837 | 0.57868 | 0.60899 | 0.59069 | **0.03100** / 0.54072 | 1,525,031 | 18,529,943 B | 2.397 ms / 417.1 sps |

上述延迟是本机桌面 CUDA，不是手机实测。完整的 per-class、混淆矩阵、概率分布、Brier、batch-32 基准、阈值覆盖表和训练曲线位于 `reports/generated/<model>/`。

选择 ResNet18，因为其 validation macro-F1 和类别平衡显著领先，且能够可靠转换到 LiteRT。虽然参数更多，动态量化后仍为可接受的 11.3 MB。阈值 0.70 在 validation 上覆盖 60.69%，覆盖样本准确率 80.41%，用于偏保守地生成 `UNKNOWN`。

## 锁定后的最终测试

在选择架构与阈值后仅对锁定的 ResNet18 进行最终 PyTorch test 评估：accuracy 0.67162、macro-F1 0.64613、weighted-F1 0.66924、balanced accuracy 0.64214、ECE 0.05281、Brier 0.49155。详细 per-class 指标见模型卡和 `reports/generated/resnet18/test_metrics.json`。

## LiteRT

官方 AI Edge Torch 在当前 Windows 环境真实失败：`ModuleNotFoundError: No module named 'torch_xla'`；官方 `torch_xla` wheel 没有该 Windows 组合。Docker Desktop 又因移动安装后缺失 `SOFTWARE\Docker Inc.\Docker Desktop` 注册表路径而无法启动 Linux 后端。未修改系统注册表，也未使用第三方 ONNX 链。

替代方案是在 TensorFlow 中重建同构、推理态 ResNet18，逐层转移 torchvision 权重，通过固定样本 logit 验收后使用官方 TensorFlow Lite Converter。验证结果：

| 版本 | Val accuracy | Val macro-F1 | 大小 | 桌面 LiteRT CPU batch-1 | 吞吐 |
|---|---:|---:|---:|---:|---:|
| float32 | 0.66782 | 0.64834 | 44,716,576 B | 1.63 ms | 614.2 samples/s |
| dynamic int8 | 0.67030 | **0.64877** | **11,263,264 B** | **0.80 ms** | 1,247.8 samples/s |

动态 int8 按预先设定的 validation macro-F1 退化不超过 0.01 规则入选。选择完成后，两份导出物仅作 test 回归：float32 accuracy 0.67162、macro-F1 0.64614；动态 int8 accuracy 0.67275、macro-F1 0.64563，量化前后 macro-F1 变化 -0.00051。模型已复制到 Android assets，SHA-256 为 `c4f6852bbe45d302f26bbb40ead8d3b4c9ce78cdf6e15b62738b65afac8357d7`。

## Android 接入

实现包括 CameraX `ImageAnalysis`、`KEEP_ONLY_LATEST`、前置摄像头 rotation/镜像、YUV→RGB、ML Kit 本地人脸检测与最大脸裁剪、与训练一致的 resize/normalization、LiteRT 后台推理、200 ms 分析节流、多帧 EMA、0.70 阈值、稳定帧/持续时间、`NO_FACE`、`UNKNOWN`、建议冷却和完整生命周期。

StudyScreen 只有在用户主动开启、相机授权且专注计时运行时才分析；页面离开会解绑相机并释放解释器。图片不保存、不上传、不写日志。Mock/Real 仍通过 repository 工厂可替换；AI 导员后端忽略 `expression_signal` 的安全降级保持不变，真实 AI 融合默认未开启。

## 验证状态

- Python pytest：6 passed
- 数据审计：通过
- 三模型 smoke/完整训练：通过
- 最终 test 与 LiteRT 数值回归：通过
- Android expression 单测与现有单测：9 tests，0 failures，0 errors
- Android `assembleDebug`：通过
- Android `lintDebug`：通过（最终 `assembleDebug + lintDebug` 为 `BUILD SUCCESSFUL`）
- 真机：未连接，因此未进行真实设备延迟、功耗和相机端到端测试
