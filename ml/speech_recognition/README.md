# 本地语音识别：小声与噪声鲁棒性实验

本模块在现有 SenseVoice INT8 / sherpa-onnx 上比较推理前处理，不训练、更换或导出模型，不自动修改应用配置。识别、Silero VAD、受限增益、GTCRN、Observation Adding 和 CER 计分均复用 `backend/` 现有实现。

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

后续训练路线应使用独立训练语料、人工参考和原始可训练权重；不能把上述已查看验证集继续当未见留出集，也不能以模型预测代替真值。优先在目标设备的真实麦克风、小声、距离和环境噪声上建立有标注的验证集，再评估训练时噪声/混响/增益增强。可参考 [SenseVoice 官方微调入口](https://github.com/QwenAudio/SenseVoice#finetune)，并将 [SpecAugment（Park 等，2019）](https://arxiv.org/abs/1904.08779)作为训练期消融候选，不能把训练期方法直接套在冻结 ONNX 的输入上。现有 INT8 ONNX 是推理资产，本模块没有执行训练。

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

这是一轮冻结模型的前处理研究，不是移动端迁移或全端功能交付。语料主要是朗读语音，开发集很小，未验证真实麦克风、耳语、远场、多人同时讲话或设备间差异。不能证明数据与模型训练集不重合，也未证明开发/验证说话人不相交。接口、客户端和应用默认行为均不因运行本模块而变化。
