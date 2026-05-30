---
name: writing-feedback
description: 为教师批改中文学生作文。适用于教师提供图片、PDF、DOCX 或文本格式的学生作文，需要识别或提取正文、确认班级姓名题目等元信息、按 3-4 年级/5-6 年级/7-9 年级评价标准批改、输出客观修改意见和整体评价，并读取或更新 .writing-feedback-memory 中的教师批改标准与学生写作画像。
---

# 写作反馈助手

## 核心原则

服务教师。先保留学生原文，再做判断；先分清客观错误和整体评价，再给修改建议；长期记忆统一放在 `.writing-feedback-memory/`。除非特别说明，本文件中的 `scripts/` 和 `references/` 路径都相对本 Skill 目录。

## 工作流程

1. 读取学生作文。
   - 图片或扫描版 PDF：优先使用 `scripts/gemini_ocr.py` 做 OCR，识别文字时尽量保留原始换行、段首空格、错别字、标点、涂改痕迹和无法确认的字。
   - 如果教师提供 PDF 并指定页码或页码范围，先用 `scripts/pdf_pages_to_images.py` 将指定页转换为图片文件，再把生成的图片路径传给 `scripts/gemini_ocr.py` 做 OCR；页码按 PDF 阅读器显示的 1-based 页码理解。
   - 读取 `scripts/gemini_ocr.py` 输出的 JSON：用 `raw_text` 作为学生原文，用 `metadata` 辅助确认班级、年级、姓名和题目，用 `issues` 和 `warnings` 标注疑似 OCR 问题、疑似教师批注和无法确认内容。
   - 可选中文字的 PDF、DOCX 或纯文本：直接提取文字，并保留一份规范化后的正文。
   - 对无法确认的识别结果，标成 `【疑似：...】`，不要悄悄改成通顺文本。

2. 批改前确认元信息。
   - 从文件名和正文中识别班级、年级、学生姓名、作文题目/主题、题目详情、教师希望的评价风格。
   - 如果关键信息缺失或不确定，只向教师询问最少必要信息。
   - 根据年级选择评价标准：3-4 年级、5-6 年级、7-9 年级。

3. 读取写作记忆。
   - 读取 `.writing-feedback-memory/teacher-critic.md`。如果不存在，按 `references/teacher-critic-template.md` 创建。
   - 读取 `.writing-feedback-memory/student-writing-profile/{班级}/{姓名}.md`。如果不存在，在教师确认保存后按 `references/student-writing-profile-template.md` 创建。
   - 不要编造历史表现。没有画像时，要说明本次判断只基于当前作文。

4. 读取对应年级评价标准。
   - 3-4 年级：读取 `references/rubric-g3-g4.md`。
   - 5-6 年级：读取 `references/rubric-g5-g6.md`。
   - 7-9 年级：读取 `references/rubric-g7-g9.md`。
   - 如果年级未知，先请教师确认，再应用标准。

5. 按 `references/output-format.md` 输出批改结果。
   - 先写机械、客观、可定位的修改意见。
   - 再写作文整体评价。
   - 再结合学生画像判断本次问题和成长点。
   - 最后给 1-3 条适合该年级的具体修改任务。

6. 只在教师接受反馈或明确要求保存后更新记忆。
   - 将教师明确提出的偏好、或从教师多次修改中体现出的稳定标准，更新到 `.writing-feedback-memory/teacher-critic.md`。
   - 将可观察的写作表现、反复问题、新优点和下次关注点，更新到 `.writing-feedback-memory/student-writing-profile/{班级}/{姓名}.md`。
   - 避免给学生贴人格标签。只记录写作证据，不记录性格判断。

## 记忆目录

使用仓库内的这个结构：

```text
.writing-feedback-memory/
  teacher-critic.md
  student-writing-profile/
    {班级}/
      {学生姓名}.md
```

新建班级或学生路径时，中文班级名和学生姓名尽量保持可读。路径里不能出现的 `/` 等分隔符改成 `-`。

## Gemini OCR 识别图片和扫描版 PDF

当用户提供图片、扫描版 PDF，或需要从手写作文图片中提取文字时，使用 `scripts/gemini_ocr.py`。脚本会输出 JSON，包含 `raw_text`、`metadata`、`issues` 和 `warnings`，后续批改必须基于这些字段继续处理。

首次使用或依赖缺失时，在本 Skill 目录内安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

默认配置文件为 `~/.writing-feedback/gemini_ocr.json`，也可以通过环境变量 `GEMINI_API_KEY`、`GEMINI_MODEL`、`GEMINI_OPENAI_BASE_URL` 或命令行参数覆盖。如果缺少 API Key，不要伪造 OCR 结果，应提示教师补充配置或改用可提取文字的输入。

多张图片属于同一篇作文时，按作文页序传入：

```bash
python3 scripts/gemini_ocr.py --input 第1页.jpg 第2页.jpg --output /tmp/writing-feedback-ocr.json
```

扫描版 PDF 未指定页码时，可以直接传入 PDF；默认最多处理前 20 页，可用 `--page-limit` 调整：

```bash
python3 scripts/gemini_ocr.py --input 作文.pdf --page-limit 6 --output /tmp/writing-feedback-ocr.json
```

当用户给出 PDF 文件并指定只处理某一页或某几页时，先运行：

```bash
python3 scripts/pdf_pages_to_images.py 作文.pdf --pages 2,4-5 --out-dir /tmp/writing-feedback-pages --json
```

脚本会把指定页渲染为图片，输出生成图片的绝对路径。随后将这些图片路径按页序传给 Gemini OCR：

```bash
python3 scripts/gemini_ocr.py --input /tmp/writing-feedback-pages/作文_page_0002.png /tmp/writing-feedback-pages/作文_page_0004.png /tmp/writing-feedback-pages/作文_page_0005.png --output /tmp/writing-feedback-ocr.json
```

`pdf_pages_to_images.py` 默认使用 300 DPI；如果图片过大，可用 `--dpi 220` 降低分辨率。脚本依赖 PyMuPDF（Python 包名 `fitz`），缺失时按脚本提示安装后再运行。

## 输出边界

- 除非教师明确要求，不要整篇重写学生作文。
- 不要把客观错误写成道德评价。
- 不要用高年级文学标准过度批评低年级作文。
- 不要把内部评价标准逐条原样暴露给学生；需要时转成教师可用的判断。
- 不要只根据 OCR 原文更新画像；画像应基于已确认的元信息和教师认可的批改结果更新。

## 资源说明

- `references/rubric-g3-g4.md`：中低年级评价标准，重点看格式、正确性、句子通顺和是否切题。
- `references/rubric-g5-g6.md`：高年级小学评价标准，重点看结构、细节、选材和中心。
- `references/rubric-g7-g9.md`：初中评价标准，重点看立意、组织、论证/叙事推进和语言控制。
- `references/output-format.md`：批改输出结构和措辞约束。
- `references/teacher-critic-template.md`：教师批改记忆初始模板。
- `references/student-writing-profile-template.md`：学生写作画像初始模板。
- `requirements.txt`：Gemini OCR 和扫描版 PDF 处理所需 Python 依赖。
- `scripts/gemini_ocr.py`：用 Gemini 的 OpenAI 兼容接口识别图片或扫描版 PDF，输出可用于批改的 JSON。
- `scripts/pdf_pages_to_images.py`：将 PDF 的指定页码渲染为 PNG/JPEG 图片，供后续 OCR 使用。
