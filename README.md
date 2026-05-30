# 写作反馈助手

面向中小学作文教学的 AI 写作反馈 Skill。项目目标是帮助教师更高效地批改学生作文，同时保留教师判断边界：先识别学生原文，再区分客观修改、整体评价、成长画像和年级化写作脚手架。

## 项目内容

- `writing-feedback/`：可安装的 Skill，包含工作流程、年级评价标准、客观批改规则、输出格式、写作脚手架规则和 Gemini OCR 辅助脚本。
- `scripts/`：仓库辅助脚本，目前包含 Skill 打包脚本。

## 目录结构

```text
.
├── README.md
├── .gitignore
├── scripts/
│   └── package-writing-feedback.sh
└── writing-feedback/
    ├── SKILL.md
    ├── agents/
    │   └── openai.yaml
    ├── requirements.txt
    ├── scripts/
    │   └── gemini_ocr.py
    └── references/
        ├── objective-correction.md
        ├── output-format.md
        ├── rubric-g3-g4.md
        ├── rubric-g5-g6.md
        ├── rubric-g7-g9.md
        ├── scaffolding-writing-support.md
        ├── student-writing-profile-template.md
        └── teacher-critic-template.md
```

## 使用方式

### 使用 Skill

将 `writing-feedback/` 作为 Skill 目录安装到支持 Skill 的 Agent 环境中，然后在任务中调用：

```text
使用 $writing-feedback 批改学生作文，并按年级生成写作脚手架和更新画像记忆。
```

Skill 会按以下流程工作：

1. 读取学生作文，并尽量保留原始文本、格式和不确定识别结果。
2. 确认年级、班级、姓名、题目和教师反馈风格等元信息。
3. 读取对应年级评价标准、客观批改规则和输出格式。
4. 输出可定位的客观修改意见、整体评价、成长点和具体修改任务。
5. 在需要时生成年级化写作脚手架。

### 使用 Gemini OCR

图片或扫描版 PDF 可以先用 Skill 内的 OCR 脚本识别为 JSON，再交给批改流程使用。脚本使用 Gemini 的 OpenAI 兼容接口，API Key 只从环境变量读取；多张图片可一次传入，并按输入顺序识别为同一篇作文。

```bash
python3 -m pip install -r writing-feedback/requirements.txt
export GEMINI_API_KEY=你的 Gemini Key
python3 writing-feedback/scripts/gemini_ocr.py --input 第1页.jpg 第2页.jpg --output ocr.json
```

默认模型和接口地址也可以通过环境变量或命令行参数覆盖：`GEMINI_MODEL`、`GEMINI_OPENAI_BASE_URL`、`--model`、`--base-url`。

扫描版 PDF 需要 PyMuPDF，已包含在 `writing-feedback/requirements.txt` 中。输出 JSON 会包含 `raw_text`、`metadata`、`issues` 和 `warnings`。`metadata` 包含班级、年级、姓名、作文题目和作文题目描述；`issues` 会单独标注疑似错别字、疑似 OCR 错误、疑似教师批注和无法确认内容。

### 打包 Skill

```bash
./scripts/package-writing-feedback.sh
```

脚本会在仓库根目录生成 `writing-feedback-时间戳-提交号.zip`，用于分发 Skill。生成的 zip 包不会提交到仓库。

## 数据说明

本仓库不包含学生作文扫描件、音频、教师个人批改记忆、学生画像记忆或内部参考 Prompt。相关数据和参考材料可能包含隐私信息或内部资料，应在本地或受控环境中使用，并在提交前进行脱敏处理。

## 设计边界

- 不代写整篇作文。
- 不把疑似 OCR 错误当成确定的学生错误。
- 不把教师批注当作学生原文批改。
- 不用高年级标准过度评价低年级作文。
- 画像记忆只记录可观察的写作证据，不记录人格判断。
