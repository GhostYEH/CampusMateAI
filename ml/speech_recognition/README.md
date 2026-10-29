# 本地语音识别：小声与噪声鲁棒性实验

本模块保留现有 SenseVoice INT8 / sherpa-onnx 的推理前处理消融，并提供独立的 MPS 预检、公开标注数据准备和冻结编码器的输出层训练试验。不自动修改应用配置或覆盖部署模型。前处理识别、Silero VAD、受限增益、GTCRN、Observation Adding 和 CER 计分复用 `backend/` 现有实现。

## 论文依据与适用范围

| 依据 | 本次实现 | 与论文的区别 |
| --- | --- | --- |
| [Iwamoto 等，Interspeech 2022：How bad are artifacts?](https://www.isca-archive.org/interspeech_2022/iwamoto22_interspeech.html) | `oa`：GTCRN 增强后混合 50% 原音；`oa_gain`：再做受限增响 | 借用 Observation Adding 减少增强伪影的思路；识别器和增强器不同，不宣称复现原论文指标 |
| [Ferreira、Oliveira，SE&R 2022：Domain Specific Wav2vec 2.0 Fine-tuning](https://arxiv.org/abs/2207.14418) | `gain`：语音通过原有门控后，按 RMS 0.02、最大增益 20、峰值上限 0.95 增响；不降低已有音量 | 原文在训练中使用数据集平均增益归一化及噪声增强；这里是冻结 SenseVoice 的推理消融，不能将训练收益直接移用于此处 |
| [Bain 等，Interspeech 2023：WhisperX](https://www.isca-archive.org/interspeech_2023/bain23_interspeech.html) | `padded_trim`：完整收集 VAD 区间，只裁两侧非语音，保留 250ms 边界和内部停顿 | 仅验证 VAD 分段思路的一种保守变体，没有实现完整 Cut & Merge、强制对齐或批推理 |

原始语音始终先经过现有 VAD 和受限复检，识别前处理只在通过后运行。VAD 复检增益（目标 RMS 0.005）与识别输入增益（实验目标 RMS 0.02）是不同步骤。数字增响不提高物理信噪比；降噪听感变好也不意味着错字减少。

## 基线与验证协议

- `engine_arguments()` 显式传入应用全部 ASR 设置，包括默认开启的 VAD 复检。旧的 `backend/scripts/evaluate_asr.py` 没有传递复检参数，不能将其默认输出直接当作当前应用基线。
- 使用仓库声明的 ASR 默认值，不加载 `.env`，也不采用本机 ASR 环境变量覆盖；实际部署若显式覆盖配置，需要另做对应基线。
- 开发集：沿用历史 FLEURS test tar 的前十条唯一文本中索引 0、2、4、6、8，共 5 条原句。比较原音、仅增响、仅 OA、OA + 增响。裁剪仅用于早期探索，因退化淘汰。
- 验证集：固定版本 FLEURS 普通话 dev tar 中最先遇到的 32 条唯一文本；按音频 SHA256 和标准化文本 SHA256 阻止与开发集重合。
- 语音条件：原音、10% 音量、1% 音量、10/0dB 白噪声、5dB 粉红噪声；验证另加 10/0dB 实录环境噪声，以及整体衰减到 1% 的 10dB 环境噪声混合。各变体按 PCM16 量化并饱和截幅。SNR 按整句 RMS 计算；降音量不等同于耳语或远场。
- 实录噪声：ESC-50 fold 2，雨、风、吸尘器、洗衣机、引擎、火焰各一个源，按文件名排序选第一条，不根据预测筛选。混合时循环延长噪声，不能视为新的独立噪声源。
- 负例：13 条合成噪声/静音回归控制在开发、验证中重复使用；验证另加上述 6 条未参与选参的真实环境录音，分别计误报。合成负例直接送入引擎作为浮点门控回归输入；这不是完整的 PCM16 上传或 HTTP 端到端测试。
- CER 使用现有 NFKC、小写、去标点和空白规则，语义不同的数字形式不强行合并。空参考不计入语音 CER，单独计非语音非空输出。
- 配对 bootstrap 以原句为单位同时抽取其全部变体，重复 5000 次；不同噪声源仍只有 6 个，区间不代表对任意环境噪声的保证。
- 推理时间包含门控、前处理和识别，排除 WAV 读取、解码、变体生成、评分及模型冷加载。候选轮换执行顺序以减小顺序偏差。

`validation_protocol.json` 是本轮验证前冻结的选择和验收记录；命令中明确指定候选，CLI 不读取该文件。验证模式只允许一个候选，检查源码指纹，并对照模型指纹和基线配置。代码、模型或配置改变后，应重新运行开发阶段。

验收要求总体和噪声 CER 各相对下降至少 5%，纯净和 1% 音量不退化，每个条件最多退化 0.5 个百分点，非语音误报不增加，原句分组 95% 区间上界小于 0，平均实时率低于 0.15。运行成功返回 0 仅表示完成实验；采用结论必须查看 `acceptance.passed`，不会自动写入应用配置。

## 第一轮结果（2026-10-29）

开发集 5 条原句 × 6 条件：基线 98/954 个字符错误（10.27%），仅增响 97/954（10.17%），仅 OA 和 OA + 增响均为 92/954（9.64%）。按噪声条件错误更少的规则选定 `oa_gain`，验证前冻结，未查看验证预测选参。

独立验证为 32 条新原句 × 9 条件，1113 个原始参考字符重复计分，共 10017 字符；另有 19 个非语音控制。

| 条件 | 应用基线 CER | OA + 增响 CER |
| --- | ---: | ---: |
| 全部语音 | 8.226% | 8.256% |
| 原音 | 5.211% | 5.211% |
| 1% 音量 | 6.739% | 6.469% |
| 10dB 实录环境噪声 | 6.649% | 6.739% |
| 0dB 实录环境噪声 | 11.590% | 12.040% |
| 1% 音量 + 10dB 实录环境噪声 | 6.918% | 7.098% |
| 非语音非空输出 | 0/19 | 0/19 |
| 平均实时率 RTF | 0.0278 | 0.0753 |

总体错误 824 → 827，CER 差值的原句分组 95% 区间为 `[-0.167, +0.204]` 个百分点。平均热推理耗时约 2.70 倍。候选未通过总体、噪声和显著性门槛，不启用降噪，不宣称总体准确率提升。

后续 `gain` 独立实验使用第二批新原句（dev 唯一文本索引 32–63），不得重用这轮验证原句。`validation_gain_protocol.json` 冻结了其专门针对小声的目标：1% 音量 CER 相对下降至少 5%、该条件配对区间上界小于 0，同时总体和合并噪声 CER 不退化。六个环境噪声源只作为回归控制复用，不宣称是未见噪声。该实验不能解释为降噪方法；没有新独立结果前不得采用。

## 第二轮结果（2026-10-29）

第二批 32 条原句的音频和标准化文本指纹与开发集、第一轮验证均不重合。每条产生 9 个条件，共 9603 个计分参考字符；复用 19 个非语音回归控制。参数在验证前冻结，没有根据第二轮预测调参。

| 条件 | 应用基线 CER | 仅受限增响 CER |
| --- | ---: | ---: |
| 全部语音 | 7.331% | 7.352% |
| 原音 | 4.592% | 4.592% |
| 1% 音量 | 5.904% | 5.904% |
| 10dB 实录环境噪声 | 4.873% | 4.967% |
| 0dB 实录环境噪声 | 12.090% | 12.090% |
| 1% 音量 + 10dB 实录环境噪声 | 4.873% | 4.967% |
| 非语音非空输出 | 0/19 | 0/19 |
| 平均实时率 RTF | 0.0237 | 0.0244 |

总体错误 704 → 706；1% 音量仍为 63/1067 个字符错误，配对差值 95% 区间为 `[-0.275, +0.278]` 个百分点；总体差值区间为 `[-0.078, +0.113]` 个百分点。未通过小声改善、总体/噪声不退化和置信区间门槛，不启用识别前增响。两轮都是未通过的候选，不能因为开发集有少量改善就宣称完成准确率优化。

后续训练路线应使用独立训练语料和人工参考；不能把上述已查看验证集继续当未见留出集，也不能以模型预测代替真值。优先在目标设备的真实麦克风、小声、距离和环境噪声上建立有标注的验证集，再评估训练时噪声/混响/增益增强。可参考 [SenseVoice 官方微调入口](https://github.com/QwenAudio/SenseVoice#finetune)，并将 [SpecAugment（Park 等，2019）](https://arxiv.org/abs/1904.08779)作为训练期消融候选，不能把训练期方法直接套在冻结 ONNX 的输入上。现有 INT8 ONNX 在部署链路仍是推理资产；下文试验重建独立的可训练浮点输出层，冻结编码器，不等同于原模型全量训练。

## 复现

使用现有后端 Python 环境，需 `sherpa-onnx`、NumPy、Pydantic Settings 和 pytest。本次环境为 Python 3.12.14、sherpa-onnx 1.13.8、NumPy 2.5.4。先用后端已有脚本准备 SenseVoice、词表、Silero 和 GTCRN：

```sh
backend/.venv/bin/python backend/scripts/download_asr_model.py --with-vad --with-denoiser --check
```

缺文件时去掉 `--check` 下载。数据准备阶段联网，评测阶段完全本地运行。下列命令从仓库根目录执行；目标数据目录已经存在时会拒绝覆盖。

```sh
backend/.venv/bin/python ml/speech_recognition/prepare_fleurs.py --output ml/speech_recognition/data/development --split test --count 5 --stride 2
backend/.venv/bin/python ml/speech_recognition/prepare_fleurs.py --output ml/speech_recognition/data/fleurs_validation --split dev --count 32
backend/.venv/bin/python ml/speech_recognition/prepare_noise.py --output ml/speech_recognition/data/esc50_validation --fold 2

backend/.venv/bin/python ml/speech_recognition/robustness.py --manifest ml/speech_recognition/data/development/manifest.jsonl --candidates baseline gain oa oa_gain --output ml/speech_recognition/runs/development_frozen.json

backend/.venv/bin/python ml/speech_recognition/robustness.py --manifest ml/speech_recognition/data/fleurs_validation/manifest.jsonl --noise-manifest ml/speech_recognition/data/esc50_validation/manifest.jsonl --candidates baseline oa_gain --development-report ml/speech_recognition/runs/development_frozen.json --output ml/speech_recognition/runs/validation.json

backend/.venv/bin/python -m pytest ml/speech_recognition/tests -q
```

第二轮只验证增响，使用完全不同的原句并显式排除第一轮数据：

```sh
backend/.venv/bin/python ml/speech_recognition/prepare_fleurs.py --output ml/speech_recognition/data/fleurs_validation_gain --split dev --count 32 --offset 32
backend/.venv/bin/python ml/speech_recognition/robustness.py --manifest ml/speech_recognition/data/development/manifest.jsonl --candidates baseline gain --output ml/speech_recognition/runs/development_gain.json
backend/.venv/bin/python ml/speech_recognition/robustness.py --manifest ml/speech_recognition/data/fleurs_validation_gain/manifest.jsonl --noise-manifest ml/speech_recognition/data/esc50_validation/manifest.jsonl --candidates baseline gain --development-report ml/speech_recognition/runs/development_gain.json --exclude-report ml/speech_recognition/runs/validation.json --output ml/speech_recognition/runs/validation_gain.json
```

下载器流式读取压缩包并在取得所需样本后停止，默认限制 80MiB；只写选择的文件，不解压任意归档路径。保留原始引用、模型/音频哈希和转换说明。`data/`、`runs/`、日志和模型不提交。完整结果在本地 JSON 中，下面仅保留结论所需的聚合数据。

数据来源：[Google FLEURS](https://huggingface.co/datasets/google/fleurs)，固定版本 `70bb2e84b976b7e960aa89f1c648e09c59f894dd`，CC-BY-4.0；[ESC-50](https://github.com/karolpiczak/ESC-50)，固定版本 `33c8ce9eb2cf0b1c2f8bcf322eb349b6be34dbb6`，原始音频 CC BY-NC 3.0。各下载目录的 `provenance.json` 保留具体来源及许可信息。

## 适用边界

前两轮是冻结模型的前处理研究；后续 MPS 试验只适配输出层，仍不是移动端迁移或全端功能交付。语料主要是朗读语音，开发集很小，未验证真实麦克风、耳语、远场、多人同时讲话或设备间差异。不能证明数据与模型训练集不重合，也未证明开发/验证说话人不相交。接口、客户端和应用默认行为均不因运行本模块而变化。

## Apple Silicon 小内存训练试验

`mps_preflight.py` 动态检查芯片架构、统一内存和 MPS，执行小型 CTC 正向/反向，并确认梯度在 MPS 且非零。若原生 CTC 不支持，会单独验证 CPU 损失到 MPS 参数的梯度路径并明确标记；不会把回退写成原生支持。本次在 M1 / 8GiB、PyTorch 2.15.0 上实测原生 MPS CTC 正反向通过。这个检查不等于完整 SenseVoice 训练或容量验证。

训练环境放在本模块被忽略的 `.venv/`，与后端环境分离：

```sh
backend/.venv/bin/python -m venv ml/speech_recognition/.venv
ml/speech_recognition/.venv/bin/python -m pip install -r ml/speech_recognition/requirements-mps.txt
ml/speech_recognition/.venv/bin/python ml/speech_recognition/mps_preflight.py --output ml/speech_recognition/runs/mps_preflight.json
```

`prepare_training.py` 使用官方 FLEURS **train** 人工参考，不用已查看的 dev/test 数据训练。训练噪声选 ESC-50 fold 3，验证噪声沿用 fold 2，并检查底层 `src_file` 不重合。保留官方原始文本、`<|zh|>` / `<|Speech|>` / ITN 标记；无情绪标注显式用 `<|EMO_UNKNOWN|>`。`source_len` 为 10ms 单位，`target_len` 只是采样估算，实际标签由分词器计算。字段参考 [官方训练说明](https://github.com/modelscope/FunASR/blob/main/docs/training.md)与 [SenseVoiceCTCDataset](https://github.com/modelscope/FunASR/blob/main/funasr/datasets/sense_voice_datasets/datasets.py)。

试验包的训练原句 64 条，生成 576 个增强样本和 **576 个纯净重复对照**；两组 key、长度和样本曝光量相同，比较时还须固定优化步数。32 条开发回归原句生成 288 个验证样本。这批验证已在前两轮查看，不是最终未见测试集。JSONL 的音频路径相对试验包工作目录，可整体搬迁。

```sh
backend/.venv/bin/python ml/speech_recognition/prepare_fleurs.py --output ml/speech_recognition/data/fleurs_train_pilot --split train --count 64
backend/.venv/bin/python ml/speech_recognition/prepare_noise.py --output ml/speech_recognition/data/esc50_train_pilot --fold 3
backend/.venv/bin/python ml/speech_recognition/prepare_training.py --train-manifest ml/speech_recognition/data/fleurs_train_pilot/manifest.jsonl --valid-manifest ml/speech_recognition/data/fleurs_validation_gain/manifest.jsonl --train-noise-manifest ml/speech_recognition/data/esc50_train_pilot/manifest.jsonl --valid-noise-manifest ml/speech_recognition/data/esc50_validation/manifest.jsonl --regression-report ml/speech_recognition/runs/validation.json --regression-report ml/speech_recognition/runs/validation_gain.json --output ml/speech_recognition/data/training_pilot
```

`frozen_head.py` 固定现有 INT8 编码器，在 CPU 缓存其量化末层特征，只在 MPS 更新 512 → 25055 的 CTC 线性输出层。每批一个样本、AdamW 学习率 0.00002、梯度裁剪 5，MPS 分配器占推荐工作集比例限制为 0.35。输入 Fbank/LFR/CMVN 按 [sherpa-onnx v1.13.8](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.8/sherpa-onnx/csrc/offline-recognizer-sense-voice-impl.h) 重建；缓存阶段逐条检查浮点输出层与原 INT8 输出的解码一致性，并用既有原生识别结果检查纯净语音前端一致性。任何不一致均停止。

这是将带噪训练思想用于冻结表征的输出层试验，不是原论文完整微调的复现，也没有实现 LoRA 或训练期 SpecAugment。含分词器未知 ID 0 的训练原句会从两组整句同步排除并记录，因为 0 同时是 CTC blank；不能把这些标签直接送入损失。64 条中本轮发现 2 条此类原句，剩余 62 条 / 每组 558 行。验证原句保留原始参考，不按可训练性筛掉难例。

原生模型输出只用于实现对齐检查，不作为训练标签或识别准确率真值；训练和 CER 始终使用官方人工参考。开发缓存中 286 个原生非空语音输出均对齐，另外 2 个原生判空案例不据此作前端等价断言。

分词模型来自 [SenseVoiceSmall](https://huggingface.co/FunAudioLLM/SenseVoiceSmall/tree/3847d57b6bdf2dd8875cb1508d2af43d80a16bf7)，固定版本 `3847d57b6bdf2dd8875cb1508d2af43d80a16bf7`，文件 `chn_jpn_yue_eng_ko_spectok.bpe.model` 的 SHA256 为 `aa87f86064c3730d799ddf7af3c04659151102cba548bce325cf06ba4da4e6a8`。仅下载该文件到被忽略的 `data/`，不需要下载完整浮点模型。

```sh
curl --fail --location 'https://huggingface.co/FunAudioLLM/SenseVoiceSmall/resolve/3847d57b6bdf2dd8875cb1508d2af43d80a16bf7/chn_jpn_yue_eng_ko_spectok.bpe.model?download=true' --output ml/speech_recognition/data/chn_jpn_yue_eng_ko_spectok.bpe.model
ml/speech_recognition/.venv/bin/python ml/speech_recognition/frozen_head.py cache --model backend/data/asr_models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.int8.onnx --tokenizer ml/speech_recognition/data/chn_jpn_yue_eng_ko_spectok.bpe.model --bundle ml/speech_recognition/data/training_pilot --parity-report ml/speech_recognition/runs/validation_gain.json --output ml/speech_recognition/runs/frozen_head_cache
ml/speech_recognition/.venv/bin/python ml/speech_recognition/frozen_head.py train --cache ml/speech_recognition/runs/frozen_head_cache --split train_clean --steps 64 --output ml/speech_recognition/runs/head_clean.pt
ml/speech_recognition/.venv/bin/python ml/speech_recognition/frozen_head.py train --cache ml/speech_recognition/runs/frozen_head_cache --split train_augmented --steps 64 --output ml/speech_recognition/runs/head_augmented.pt
ml/speech_recognition/.venv/bin/python ml/speech_recognition/frozen_head.py evaluate --cache ml/speech_recognition/runs/frozen_head_cache --tokenizer ml/speech_recognition/data/chn_jpn_yue_eng_ko_spectok.bpe.model --checkpoints ml/speech_recognition/runs/head_clean.pt ml/speech_recognition/runs/head_augmented.pt --output ml/speech_recognition/runs/head_evaluation.json
```

输出 `.pt` 仅为研究用浮点线性层，不能直接替换部署模型。`frozen_head.py evaluate` 的 CER 为不带应用 VAD 的原始声学模型计分，与前两轮端到端 CER 不直接比较；单独环境的归一化/计分规则由测试对照后端契约。输出层试验不训练情绪或事件任务，不能宣称这些能力已通过回归。

### 一遍训练与兼容导出

在同一开发回归集上，原始声学模型为 641/9603 个字符错误（6.675%）。64 步纯净/增强对照分别为 637、636 个错误；一遍训练（每组 558 次更新）分别为 617（6.425%）、612（6.373%）。558 步两组耗时分别为 38.78、39.41 秒，实测 MPS 张量最高约 233MiB、驱动报告最高约 1035MiB；这不是整机内存峰值。

按开发集最低原始 CER 固定选择 `head_augmented_558.pt`，再做最终独立测试；不根据最终预测调训练步数。`frozen_head.py export` 只按原量化尺度重建输出层整数权重并更新偏置，原 ONNX 输入输出、元数据和其余参数保持原样。导出目标已存在时拒绝覆盖。此次改变 920 个量化权重，未发生权重截幅，须单独核对浮点收益是否经重新量化保留。

最终语音取固定版本 FLEURS **test** tar 中跳过前 10 条历史研究原句之后的 32 条唯一文本；环境噪声取 ESC-50 fold 5，来源与本轮训练 fold 3、开发 fold 2 不相交。先前尝试读取 dev 深偏移样本下载缓慢，在任何该批推理前停止，改用官方 test；没有根据预测筛选。最终脚本校验训练/开发和历史验证音频/文本不重合、噪声底层来源不重合、候选文件 SHA256 等于预先固定的选择记录。

```sh
ml/speech_recognition/.venv/bin/python ml/speech_recognition/frozen_head.py train --cache ml/speech_recognition/runs/frozen_head_cache --split train_clean --steps 558 --output ml/speech_recognition/runs/head_clean_558.pt
ml/speech_recognition/.venv/bin/python ml/speech_recognition/frozen_head.py train --cache ml/speech_recognition/runs/frozen_head_cache --split train_augmented --steps 558 --output ml/speech_recognition/runs/head_augmented_558.pt
ml/speech_recognition/.venv/bin/python ml/speech_recognition/frozen_head.py export --model backend/data/asr_models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.int8.onnx --checkpoint ml/speech_recognition/runs/head_augmented_558.pt --output ml/speech_recognition/runs/head_augmented_558.int8.onnx
backend/.venv/bin/python ml/speech_recognition/prepare_fleurs.py --output ml/speech_recognition/data/fleurs_head_test --split test --count 32 --offset 10
backend/.venv/bin/python ml/speech_recognition/prepare_noise.py --output ml/speech_recognition/data/esc50_head_holdout --fold 5
```

将导出文件 SHA256 与开发选择依据写入本地 `runs/head_selection.json` 的 `candidate_sha256` 字段，在第一次最终推理前固定。其余字段保留所选 checkpoint、步数及数据选择；此记录和生成模型均不提交。验收沿用首轮总体/噪声相对 CER 改善至少 5%、分组区间不触零、纯净/小声不退化及非语音误报门槛，不自动替换应用模型。

```sh
backend/.venv/bin/python ml/speech_recognition/evaluate_trained_head.py --manifest ml/speech_recognition/data/fleurs_head_test/manifest.jsonl --noise-manifest ml/speech_recognition/data/esc50_head_holdout/manifest.jsonl --training-cache ml/speech_recognition/runs/frozen_head_cache --candidate ml/speech_recognition/runs/head_augmented_558.int8.onnx --selection ml/speech_recognition/runs/head_selection.json --exclude-report ml/speech_recognition/runs/validation.json --exclude-report ml/speech_recognition/runs/validation_gain.json --exclude-report ml/speech_recognition/runs/development_gain.json --output ml/speech_recognition/runs/head_native_test.json
```

这轮完整原生验证的两组错误数均为 1123/9594，CER 都是 11.705%，19 个非语音类别控制均无非空输出，配对差值区间为 `[0, 0]`。RTF 为 0.0256 / 0.0254。候选未达到改善门槛，不采用。这个结果本身不能区分量化影响和泛化不足，因为开发集与最终测试集不同。

### 同一 checkpoint 的输出层精度对照

保留编码器与其量化激活，只把同一 checkpoint 的输出投影保留 FP32，导出混合精度 ONNX。外部输入输出及元数据、编码器节点和权重均逐项检查未改变；体积为 277.72MB。`--precision float32` 会改写内部 CTC 投影子图，默认 `int8` 仍只改原头的整数权重/偏置。两种实验模型都不覆盖部署文件。

预先固定 FP32 头为主比较对象、同 checkpoint INT8 头为诊断控制，换用 test 唯一文本索引 42–73 的新 32 条原句及 ESC-50 fold 4 六个噪声源。排除上一轮最终测试的指纹，在同一批新输入上同时评估基线、FP32 头与 INT8 头；只以预先固定的 FP32 头对基线进行采用判定，不在测试后选三者中的赢家。六个新噪声源不与训练/开发/上一轮测试的来源复用；未证明逐句人工审听的真实非语音，控制集结果不等于实际麦克风误报保证。

```sh
ml/speech_recognition/.venv/bin/python ml/speech_recognition/frozen_head.py export --model backend/data/asr_models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.int8.onnx --checkpoint ml/speech_recognition/runs/head_augmented_558.pt --precision float32 --output ml/speech_recognition/runs/head_augmented_558.mixed.onnx
backend/.venv/bin/python ml/speech_recognition/prepare_fleurs.py --output ml/speech_recognition/data/fleurs_head_mixed_test --split test --count 32 --offset 42
backend/.venv/bin/python ml/speech_recognition/prepare_noise.py --output ml/speech_recognition/data/esc50_head_mixed_test --fold 4
```

在推理前把混合模型 SHA256 写入本地 `runs/head_mixed_selection.json` 的 `candidate_sha256`，把 INT8 控制的 SHA256 写入 `quantized_control_sha256`，一并保留上述预定主比较和数据选择。控制文件变化也会被拒绝。

```sh
backend/.venv/bin/python ml/speech_recognition/evaluate_trained_head.py --manifest ml/speech_recognition/data/fleurs_head_mixed_test/manifest.jsonl --noise-manifest ml/speech_recognition/data/esc50_head_mixed_test/manifest.jsonl --training-cache ml/speech_recognition/runs/frozen_head_cache --candidate ml/speech_recognition/runs/head_augmented_558.mixed.onnx --quantized-control ml/speech_recognition/runs/head_augmented_558.int8.onnx --selection ml/speech_recognition/runs/head_mixed_selection.json --exclude-report ml/speech_recognition/runs/validation.json --exclude-report ml/speech_recognition/runs/validation_gain.json --exclude-report ml/speech_recognition/runs/development_gain.json --exclude-report ml/speech_recognition/runs/head_native_test.json --output ml/speech_recognition/runs/head_mixed_native_test.json
```

该新测试集有 1268 个原始参考字符，九种条件重复计分共 11412 字符，另有 19 个非语音类别控制。结果如下：

| 原生完整链路 | 错误数 / 参考字符 | CER | 非语音控制非空输出 | RTF |
| --- | ---: | ---: | ---: | ---: |
| 原始模型 | 1140 / 11412 | 9.989% | 0/19 | 0.0337 |
| 同 checkpoint INT8 头诊断控制 | 1139 / 11412 | 9.981% | 0/19 | 0.0343 |
| 预定 FP32 头主候选 | 1171 / 11412 | 10.261% | 0/19 | 0.0371 |

FP32 主候选比原始模型多 31 个错误，差值的原句分组 95% 区间为 `[-0.010, +0.531]` 个百分点；纯净条件 84 → 87 个错误、1% 音量 105 → 106、0dB 实录环境噪声 209 → 217。未通过总体/噪声改善、纯净/小声不退化、单条件退化上限和区间门槛。INT8 控制少 1 个错误不能作为测试后切换采用对象的理由；该版本前一独立批也未改善。

这轮证明本机 MPS 训练和兼容导出路径可运行，不能证明准确率优化成功。开发回归集上的浮点收益没有在新测试原句上复现，也不能把失效简单归因于量化。应用默认模型保留原样。后续需要扩大、改进与目标麦克风场景相符的标注数据，并使用另一批未查看的最终留出集；本轮已查看的两批 test 数据只再作为回归数据使用。
