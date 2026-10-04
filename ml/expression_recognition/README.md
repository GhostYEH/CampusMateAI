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

通过 `CAMPUSMATE_EXPRESSION_DATASET_ROOT` 指定的训练目录包含 3 个自动检测到的数据集：

| 数据集 | 图片数 | 尺寸 | 通道 | 标签格式 |
|---|---:|---|---|---|
| 2013 (FER2013) | 35,887 | 48×48 | 1 | 类别文件夹 |
| DATASET (RAF-DB aligned) | 15,339 | 100×100 | 3 | 数值 1-7 |
| archive (3) | 30,626 | 96×96 | 3 | 文件夹名 + CSV |

`unified_manifest.py` 自动识别三种布局（类别文件夹、train/test/val 目录、CSV 标签），统一映射为七类，使用 SHA-256 全局去重，按类别分层划分 train/val/test。合计 81,852 张，去重后 included 76,137。

## 从零复现

原始 FER2013 CSV 需先转换到新的派生目录（不会改写 CSV 或覆盖已有目录）：

```powershell
python -m expression_recognition.prepare_fer2013 --csv $env:FER2013_CSV --output-dir artifacts/prepared/FER2013
python -m expression_recognition.unified_manifest --dataset-root artifacts/prepared --output-dir manifests_new
```

转换保留 `Training → train`、`PublicTest → validation`、`PrivateTest → test`；像素范围、尺寸、标签或 Usage 无效的行写入隔离记录。清单保留来源的显式验证集，仅对没有验证集的来源重新划分训练池。跨划分重复图优先保留 test，其次 validation，避免验证图重新流入训练。不同数据集的数字标签顺序不同，来源不明的数字目录应先隔离核对。

对已逐文件核对作者标注索引的 RAF Basic `0..6` 目录，可在清单命令增加 `--raf-train-root $env:RAFDB_TRAIN_ROOT --raf-test-root $env:RAFDB_TEST_ROOT`。该路径显式采用 RAF 顺序 `surprise, fear, disgust, happy, sad, angry, neutral`；即使测试目录在本地名为 `valid`，仍保留为 test，并只从官方训练池划出 validation。类目录内的图片才参与导入，其他嵌套副本忽略。

要求 Windows、`uv`、可用的 NVIDIA 驱动，以及通过 `CAMPUSMATE_EXPRESSION_DATASET_ROOT` 指定的只读数据源。脚本在本模块内创建 Python 3.12 独立环境，不修改系统 Python 或后端虚拟环境。

```powershell
$repoRoot = (git rev-parse --show-toplevel).Trim()
Set-Location (Join-Path $repoRoot 'ml\expression_recognition')
if (-not $env:CAMPUSMATE_EXPRESSION_DATASET_ROOT) { throw 'Set CAMPUSMATE_EXPRESSION_DATASET_ROOT first.' }
.\scripts\reproduce_training.ps1 -DatasetRoot $env:CAMPUSMATE_EXPRESSION_DATASET_ROOT
```

这会安装官方 CUDA 13.0 PyTorch wheel、运行环境自检与 pytest、构建多数据集统一清单、依次执行四个模型的 smoke test 和完整训练与评估。

## 恢复中断训练

微调已有识别模型时使用 `--initialize-from`，严格恢复模型权重和输入契约，使用新配置中的小学习率、新优化器及调度器；不会重新加载 ImageNet 权重。该选项与完整状态恢复的 `--resume` 互斥。输出必须选择新的运行目录，并在同一固定划分上对比原模型与微调模型；再下载旧数据不等于新增外部测试集。

下面示例从 ResNet18 的 `last.pt` 恢复；恢复时继续沿用 checkpoint 内保存的模型、优化器、调度器、AMP scaler、epoch、早停计数和历史：

```powershell
& .\.venv\Scripts\python.exe -m expression_recognition.train --config configs\resnet18.yaml --manifest manifests_v2\included.csv --run-dir runs_v2\full_resnet18 --resume runs_v2\full_resnet18\last.pt
```

## 评估

均衡类别/领域采样使用 `seed + epoch`，每轮重新抽样；恢复训练及 OOM 重建 loader 时沿用当前 epoch。评估 loss 按样本总数累计，避免最后一个短 batch 改变报告值。Android 保留大于 1 的类别阈值，用于禁用未达到验证精度门槛的类别。

候选模型只在 validation 上比较。架构和阈值锁定后，test 仅用于最终评估及已锁定导出模型的数值回归：

PyTorch 和 LiteRT 评估只在 `validation` 生成 `class_thresholds`；`test` 报告保留准确率、F1 和固定阈值曲线，不拟合类别阈值。生产阈值必须取自验证集校准结果。

```powershell
$env:PYTHONPATH = "src"
& .\.venv\Scripts\python.exe -m expression_recognition.evaluate --checkpoint runs_v2\full_resnet18\best.pt --manifest manifests_v2\included.csv --split validation --output-dir reports\generated_v2\resnet18
```

离线评估可添加 `--horizontal-flip-tta`，将原图和水平翻转图的 softmax 概率取均值；默认仍为单图推理。
两种策略应使用同一 checkpoint 和固定 validation，分别写入新的输出目录，比较准确率、Macro-F1
以及分类别精度和覆盖率。报告的 `inference_strategy` 与推理基准均记录所选策略，loss 是最终概率分布的 NLL。

```powershell
& .\.venv\Scripts\python.exe -m expression_recognition.evaluate --checkpoint runs_v2\full_resnet18\best.pt --manifest manifests_v2\included.csv --split validation --horizontal-flip-tta --output-dir reports\generated_v2\resnet18_flip
```

策略改变后必须在 validation 上重新校准类别门禁，不能沿用单图阈值；总体准确率上升也不代表高精度信号的覆盖率增加。
锁定策略后，可用同一开关和 `--split test` 做数值回归；test 不拟合门禁。该选项仅用于离线 PyTorch 评估，
不会改变 Android/Harmony 推理或部署模型，实机延迟须单独验证。

## LiteRT 导出与验证

```powershell
.\scripts\export_litert_v2.ps1
```

脚本优先尝试官方 AI Edge Torch。当前 Windows 环境缺少官方 `torch_xla` wheel，因此 `auto` 会记录原始失败原因，并使用 TensorFlow 中的同构 ResNet18 权重转移 + 官方 TensorFlow Lite Converter。只有 PyTorch↔TensorFlow 固定样本 logit 对齐通过后才继续生成 LiteRT。没有使用第三方 ONNX 转换链。

当前真实结果和限制见 [训练报告](reports/TRAINING_REPORT.md)。

## 目标域高精度提升流程

### 遮挡训练论文思路的离线对照

在已有 ResNet18 检查点和 `manifests_v2/included.csv` 可用时，可以比较
仅用遮挡图像微调与保留清晰图像监督、冻结教师参考的微调。两组从同一个
检查点启动，使用固定的验证集遮挡掩码，并分别报告正常和遮挡图像的
Macro-F1、准确率及每类 F1。该实验借鉴 [CA-HOFT](https://doi.org/10.3390/s26175500) 的训练思路，不声称
复现论文的 RAF-DB 数值，也不会自动更新手机部署资产。

```powershell
$env:PYTHONPATH = "src"
python -m expression_recognition.occlusion_experiment `
  --checkpoint runs_v2/full_resnet18/best.pt `
  --manifest manifests_v2/included.csv `
  --output-dir runs/paper_occlusion `
  --epochs 5
```

输出在 `runs/paper_occlusion/comparison.json`。若提供的是目标域清单，
应以该清单的 train/validation 两个分组运行；严禁以 test 调参。

### CPM 前摄目标域训练

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

## DAiSEE 三维学习状态扩展（离线实验）

`learning_state_model.py` 在原 ResNet18 上增加三个独立输出：`boredom`（无聊）、
`confusion`（困惑）、`frustration`（挫败）。每个输出保留 DAiSEE 的四档标注：
`0=very_low, 1=low, 2=high, 3=very_high`。它们可以同时出现，不是七类表情 softmax 的新增互斥类别；
本扩展不训练 `Engagement`。

原视觉主干、BatchNorm 统计量和七类分类器全部冻结，新增分支在固定人脸特征上训练。
视频使用均匀采样帧的特征均值，这是片段级研究基线，不是实时心理状态判断。
输入继续使用现有 96×96 灰度复制三通道和 ImageNet 归一化。原七类标签顺序保持不变。

数据源由 `CAMPUSMATE_DAISEE_ROOT` 指定，目录包含 `DataSet/` 和 `Labels/`。
准备工具只读取原始数据，输出到新目录；按官方人物划分保留 train/validation/test，
忽略 `GenderClips` 副本及无标注视频，拒绝跨划分人物/片段、非法标签及路径逃逸。
使用 OpenCV Haar 检测提取带 padding 的最大人脸，未检测到人脸的帧跳过；没有可用帧的片段隔离。
少于采样数的片段重复最后有效帧补齐，并在准备报告中记录，不能把这些帧当成独立样本划分。

从本模块目录执行：

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements-daisee.txt
$env:PYTHONPATH = "src"
python -m expression_recognition.daisee_data --dataset-root $env:CAMPUSMATE_DAISEE_ROOT --output-dir artifacts/daisee_faces_trainval --splits train validation --workers 4
python -m expression_recognition.learning_state_experiment train --checkpoint exports_v2/best_checkpoint.pt --manifest artifacts/daisee_faces_trainval/manifest.csv --output-dir artifacts/daisee_heads --epochs 40
```

训练仅使用训练集计算类别权重和多数类基线，以三个维度四档 Macro-F1 的均值在 validation 选择 checkpoint。
报告同时包含 accuracy、Macro-F1、balanced accuracy、每档指标及混淆矩阵，避免多数类准确率掩盖稀有档失败。
选择完成后，用独立命令准备 test 并评估锁定 checkpoint，不重新训练、不在 test 上选 epoch 或阈值：

```powershell
python -m expression_recognition.daisee_data --dataset-root $env:CAMPUSMATE_DAISEE_ROOT --output-dir artifacts/daisee_faces_test --splits test --workers 4
python -m expression_recognition.learning_state_experiment evaluate --checkpoint artifacts/daisee_heads/best.pt --manifest artifacts/daisee_faces_test/manifest.csv --output-dir artifacts/daisee_test
```

这些新目录必须不存在，工具不会覆盖旧实验。模型、缓存和报告保留在 Git 忽略的 `artifacts/`。
中断或失败时保留已有产物；重试请指定新的输出目录。
扩展 checkpoint 包含七类输出和三个四级分支的独立契约，不能交给旧七类 LiteRT 导出入口。
Android、HarmonyOS、小程序和后端目前仍消费原七类；新增分支未部署，实机采样、时序稳定性和置信度门禁尚需独立验证。

## 一个模型输出十个标签的置信度

`multitask_model.py` 的联合模型复用同一个 ResNet18，人脸特征同时服务原七类表情和
`boredom/confusion/frustration` 三个独立标签。输出固定顺序为
`angry, disgust, fear, happy, neutral, sad, surprise, boredom, confusion, frustration`。
前七项使用 softmax，合计为 1；后三项各自使用 sigmoid，可以与任一种表情同时出现，十项不合计为 1。
置信度表示模型概率，不能解释为测得的准确率。

新增标签不再要求用户选择程度档位。本实验把 DAiSEE 的 `0/1` 合为低程度负类，`2/3` 合为高程度正类，
因此“无聊置信度”具体指高/极高无聊的概率，而非任何程度无聊的概率。这是有记录的实验定义。
表情数据没有学习状态标注，DAiSEE 没有七类表情标注；训练各自的损失只使用已知标注，
不会把缺失标注当成负例。共享网络的 layer4、原七类分类器和新增分支参与训练，早期层及 BatchNorm 统计量冻结，
以原模型教师蒸馏和原七类验证指标保护已有能力。是否提升准确率由验证结果决定。

从模块目录执行，清单路径由环境变量提供：

```powershell
$env:PYTHONPATH = "src"
$env:OMP_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
& .venv/Scripts/python.exe -m expression_recognition.multitask_experiment train --checkpoint exports_v2/best_checkpoint.pt --expression-manifest $env:CAMPUSMATE_EXPRESSION_MANIFEST --daisee-manifest $env:CAMPUSMATE_DAISEE_MANIFEST --output-dir artifacts/joint_expression_states --epochs 3 --workers 2
& .venv/Scripts/python.exe -m expression_recognition.multitask_confidence calibrate --checkpoint artifacts/joint_expression_states/best.pt --validation-predictions artifacts/joint_expression_states/validation_predictions.npz --output-checkpoint artifacts/joint_expression_states/calibrated.pt
& .venv/Scripts/python.exe -m expression_recognition.multitask_confidence predict --checkpoint artifacts/joint_expression_states/calibrated.pt --face-images $env:CAMPUSMATE_FACE_IMAGE
```

校准仅拟合与 checkpoint 哈希对应的 validation 预测，拒绝 test 预测。
七类使用温度缩放，新标签分别使用单调 Platt 校准；validation 缺少正类或负类的标签明确标为未校准。
校准后的参数与网络权重保存在同一个 `.pt` 文件，推理 JSON 提供十项概率及百分比。
输入须是同一人物的人脸裁剪；可传一张或同一片段的多张裁剪，使用帧特征均值。
学习状态训练使用每片段四帧，单帧输出属于尚未单独验证的实验模式。

最终评估须使用已锁定的模型与校准参数，不根据 test 结果重新训练、选模型或修改阈值。
用 `multitask_experiment evaluate` 指定校准后的 checkpoint、原七类清单和独立 DAiSEE test 清单，
写入新的 `--output-dir`；报告中的状态指标使用校准后的概率，并保留原始概率的对照指标。
已经查看过的测试集再次评估只能作为开发对照，不能宣称全新外部验证。
本入口保持离线，不能直接替换旧七类手机模型；部署和客户端展示需要后续适配与实机验证。

### 继续微调十标签模型

`--checkpoint` 仍指定原七类来源，`--initialize-from` 指定通过 validation 七类保护检查的十标签 checkpoint。
默认 `--teacher-source original` 使用原七类模型作教师；`--teacher-source initial` 使用继续训练起点的
七类分支作教师，权重独立复制并冻结，适合保护当前模型已有的七类能力。
继续训练会加载全部已训练权重，并清除旧的置信度校准参数；选择新模型后须重新在 validation 校准。
这与从七类模型重新随机初始化三个状态分支不同。

可调参数包括共享层与状态分支的学习率、状态损失权重、训练正类权重的指数/上限、
状态采样与数据增强、余弦学习率调度及梯度裁剪。
`--trainable-blocks layer3_layer4` 允许以较小学习率微调更多共享特征；默认仍仅微调 layer4，
所有 BatchNorm 运行统计量继续冻结，十标签格式与输出顺序保持不变。

```powershell
& .venv/Scripts/python.exe -m expression_recognition.multitask_experiment train --checkpoint exports_v2/best_checkpoint.pt --initialize-from artifacts/joint_expression_states/best.pt --expression-manifest $env:CAMPUSMATE_EXPRESSION_MANIFEST --daisee-manifest $env:CAMPUSMATE_DAISEE_MANIFEST --output-dir artifacts/joint_expression_states_tuned --epochs 4 --learning-rate 0.00003 --state-learning-rate 0.0003 --state-loss-weight 0.75 --state-pos-weight-power 0.5 --pos-weight-cap 30 --state-augmentation mild --scheduler cosine --gradient-clip 1 --selection-metric average_precision --max-expression-f1-drop 0.005 --max-expression-accuracy-drop 0.005 --workers 2
```

调参比较使用未校准的 validation 预测，以三个状态 AP 的均值选候选，同时检查原七类 Macro-F1
和准确率相对继续训练起点的变化，避免多数负类掩盖稀有状态的识别失败。
正类权重和均衡采样权重只由 train 标签计算；均衡采样与正类加权会叠加，必须显式记录和比较。
训练报告记录各状态正类 precision/recall/F1、AP、混淆矩阵、初始化哈希及实际训练参数。
保持原始模型和各候选，不覆盖旧实验；如果验证结果没有提升，保留原模型。
