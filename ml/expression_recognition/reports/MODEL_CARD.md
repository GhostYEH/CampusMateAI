# Expression ResNet18 Clean v1 — 模型卡

## 用途

本模型用于 Android 学习陪伴页面中，对用户主动授权后的前置摄像头画面进行本地、低频率的面部表情分类。它只描述可观察到的表情类别，不诊断心理状态、疾病或疲劳，不用于危机识别、医疗判断、纪律处分或校园事实推断。

低置信度、概率过于分散或多帧不稳定时输出 `UNKNOWN`，不得触发安慰；画面无人脸时由 ML Kit 阶段输出 `NO_FACE`。原始帧只在内存处理，不保存、不上传、不写日志。

## 模型

- 架构：torchvision ResNet18，ImageNet `IMAGENET1K_V1` 预训练后微调
- 参数量：11,180,103
- 输入：NHWC RGB，96×96，float32
- 归一化：ImageNet mean/std
- 训练损失：class-weighted cross entropy + 0.05 label smoothing
- 数据增强：轻微旋转、平移、尺度、亮度/对比度和水平翻转
- 最佳 checkpoint：validation macro-F1 选择
- 部署版本：动态 int8 权重、float32 激活
- 部署阈值：0.70；validation 覆盖率 60.69%，覆盖样本准确率 80.41%

## 数据

只读源包含 35,887 张 48×48 单通道 JPEG。审计发现 1,516 个精确重复组、506 个实际跨 split 重复组、57 个跨标签冲突组。跨标签冲突的 160 张图全部隔离；同标签重复仅保留规范样本；跨 train/test 重复优先保留 test 并从训练候选排除。

清洗后共 33,977 张：train 22,875、validation 4,037、test 7,065。`disgust` 仍明显少样本（train/validation/test 为 298/52/108）。

## 最终真实性能

锁定的 PyTorch ResNet18 在清洗 test 上：

| 指标 | 值 |
|---|---:|
| Accuracy | 0.67162 |
| Macro-F1 | 0.64613 |
| Weighted-F1 | 0.66924 |
| Balanced accuracy | 0.64214 |
| ECE（15 bins） | 0.05281 |
| Multiclass Brier | 0.49155 |

float32 LiteRT 在同一清洗 test 上 accuracy 0.67162、macro-F1 0.64614；动态 int8 为 accuracy 0.67275、macro-F1 0.64563。量化前后 macro-F1 变化为 -0.00051。该差异属于导出/量化数值回归，不用于重新选择架构或阈值。

| 类别 | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| angry | 0.5913 | 0.6227 | 0.6066 | 941 |
| disgust | 0.6344 | 0.5463 | 0.5871 | 108 |
| fear | 0.5657 | 0.4627 | 0.5090 | 1,005 |
| happy | 0.8621 | 0.8651 | 0.8636 | 1,764 |
| neutral | 0.5808 | 0.6961 | 0.6332 | 1,224 |
| sad | 0.5641 | 0.5166 | 0.5393 | 1,235 |
| surprise | 0.7826 | 0.7855 | 0.7840 | 788 |

`fear` 和 `sad` 仍是最弱类别；`disgust` 支持量小，指标方差会很大；`neutral` 的召回较高但 precision 较低。不能只根据总体 accuracy 解释个体结果。

## 导出验收

- PyTorch→TensorFlow：64 样本 top-1 100%，最大/平均 logit 误差 `5.72e-6 / 1.31e-6`
- PyTorch→float32 LiteRT：top-1 100%，最大/平均误差 `1.61e-5 / 2.00e-6`
- PyTorch→动态 int8 LiteRT：top-1 100%，最大/平均误差 `0.31375 / 0.06171`
- validation macro-F1：float32 0.64834，动态 int8 0.64877
- 文件大小：float32 44,716,576 bytes；动态 int8 11,263,264 bytes
- 桌面 LiteRT CPU batch-1：float32 1.63 ms；动态 int8 0.80 ms
- 最佳模型 SHA-256：`c4f6852bbe45d302f26bbb40ead8d3b4c9ce78cdf6e15b62738b65afac8357d7`

桌面延迟只是本机 XNNPACK 基准。没有连接真实 Android 设备，因此没有声称手机端延迟、功耗或帧率。

## 已知限制

- FER2013 风格标签本身有噪声、主观性和类别不均衡。
- 训练图为低分辨率灰度人脸，校园真实场景的光照、角度、遮挡、肤色、眼镜、口罩和相机质量会产生明显领域偏移。
- 人脸检测裁剪误差会传递到分类器。
- 输出不是用户真实感受的可靠替代，更不能写入 `self_report`。
- 上线前需要在获得知情同意、覆盖不同设备与人群的校内代表性数据上做公平性、鲁棒性和真机性能评估。
