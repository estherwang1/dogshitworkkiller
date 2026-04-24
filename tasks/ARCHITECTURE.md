# 标准规范知识库项目 - 架构说明

## 项目概述

60 份标准规范文档(word 和 pdf)入 HiAgent 知识库做 RAG。核心方案:word 全程保留(保图) + 分段标识符 `<<<SECTION>>>` + HiAgent 按标识分块 + 智能体提示词过滤标识符。

项目包含三条独立链路,外加前置处理、HiAgent 配置、交付层脚本。

## 三条独立链路

每条链路输入都是 word 文档,共用底层 parser,产出不同。

### 链路一:质量评估

目的:对每份标准做治理质量评估,输出评估报告供业务改进参考。

```
word 文档
    ↓
word_parser.parse_docx()          ← 提取块列表
    ↓
word_parser.join_for_evaluation() ← 拼成纯文本,不带编号
    ↓
eval_prompt.PROMPT_TEMPLATE       ← 评估提示词(含占位符说明)
    ↓
模型调用 (response_format + JSON_SCHEMA)
    ↓
eval_items/xxx.json               ← 每份一个评估结果
```

**产出**:每份文档的 JSON,含元信息、硬约束、质量分、问题清单。

### 链路二:分块标注

目的:在 word 里合适位置插入分块标识符,让 HiAgent 按此切 chunk。

```
word 文档
    ↓
word_parser.parse_docx()                ← 提取块列表(带编号)
    ↓
word_parser.format_for_annotation()     ← 带 [P0001] 编号的文本,含格式信号
    ↓
annotation_prompt.PROMPT_TEMPLATE        ← 节标题识别提示词
    ↓
模型调用 (response_format + JSON_SCHEMA)
    ↓
python-docx 在对应段落前插入 <<<SECTION>>>
    ↓
output_docx/xxx.docx                    ← 标注后的 word
annotation_items/xxx.json                ← 识别结果(含疑似边界)
```

**产出**:带 `<<<SECTION>>>` 标识的 word,以及识别结果 JSON。

### 链路三:文档摘要

目的:为每份文档生成"一句话概括 + 文档摘要",让业务人员快速了解文档内容。

```
word 文档
    ↓
word_parser.parse_docx()          ← 提取块列表
    ↓
word_parser.join_for_evaluation() ← 拼成纯文本(和链路一共用)
    ↓
summary_prompt.PROMPT_TEMPLATE    ← 摘要提示词
    ↓
模型调用 (response_format + JSON_SCHEMA)
    ↓
summary_items/xxx.json            ← 每份一份摘要
```

**产出**:每份文档的 JSON,含一句话概括和文档摘要。

### 下游:HiAgent + 智能体

```
output_docx 的 word 文件 → 传 HiAgent 知识库 → 按 <<<SECTION>>> 分块 → RAG 检索
                                                                    ↓
                                                 智能体(agent_prompt.md)处理查询,
                                                 过滤 <<<SECTION>>> 不展示给用户
```

## 文件一览

### 基础层(共用)

| 文件 | 职责 |
|------|------|
| `word_parser.py` | word 遍历器。提取段落/表格/图片/图形对象,按 body 顺序编号。三条链路共用。 |

### 链路一(评估)

| 文件 | 职责 |
|------|------|
| `eval_prompt.py` | 评估提示词和 JSON schema。纯常量模块,不含逻辑。 |
| `eval_docx.py` | 批量评估脚本。读 word → 调模型 → 写 JSON,断点续跑。 |

### 链路二(标注)

| 文件 | 职责 |
|------|------|
| `annotation_prompt.py` | 节标题识别提示词和 JSON schema。 |
| `annotate_docx.py` | 批量标注脚本。读 word → 调模型 → 在 word 插 `<<<SECTION>>>` → 写 JSON。支持超长文档分块调用+重叠去重。 |

### 链路三(摘要)

| 文件 | 职责 |
|------|------|
| `summary_prompt.py` | 摘要提示词和 JSON schema。 |
| `summary_docx.py` | 批量摘要脚本。读 word → 调模型 → 写 JSON。 |

### 交付层

| 文件 | 职责 |
|------|------|
| `generate_excel.py` | 把评估 merged.json + 摘要 merged.json 合并成业务易读的 Excel(主表 sheet + 问题清单 sheet + 失败列表 sheet)。含颜色映射、命中高亮、失败标红、人工复核列。 |

### 前置处理

| 文件 | 职责 |
|------|------|
| `pdf_to_docx.py` | pdf 批量转 docx(备用,目前机器不支持,手工转) |
| `check_conversion.py` | 转换质量抽查。统计 docx 文件大小、块数、空段比例等,列出可疑文件。 |

### HiAgent 配置

| 文件 | 职责 |
|------|------|
| `agent_prompt.md` | 智能体系统提示词。含 A/B 类问题区分、三段式回答模板、占位符过滤等。 |

### 辅助工具

| 文件 | 职责 |
|------|------|
| `inspect_styles.py` | 统计单份 docx 的段落样式分布,用于调 parser 参数。 |
| `template_batch.py` | 通用批量调用模板。三个链路脚本都基于它改。 |
| `template_merge.py` | 合并 items JSON 成 merged.json。 |
| `template_excel.py` | 通用版 JSON 转 Excel。未针对业务优化,当前用 `generate_excel.py` 作为定制版。 |

## 依赖关系

```
word_parser.py
    ↑ ↑ ↑
    │ │ └──── annotate_docx.py  ← annotation_prompt.py
    │ └────── eval_docx.py      ← eval_prompt.py
    └──────── summary_docx.py   ← summary_prompt.py

check_conversion.py ← word_parser.py

generate_excel.py(独立,只读 merged.json 不依赖 parser)
```

- **word_parser.py** 是共用底层,改动会同时影响三条链路
- **三个 prompt 模块** 是纯常量模块,改它们不用动脚本
- **三个 docx 脚本** 相互独立,不依赖对方
- **generate_excel.py** 只在业务交付前跑一次,独立于所有链路

## 目录约定

```
raw_docs/           原始 pdf + docx 混放
converted_docx/     所有统一后的 docx(pdf 转的 + 原生的)
                    → 作为 eval_docx.py / annotate_docx.py / summary_docx.py 的 INPUT_DIR
output_docx/        annotate_docx.py 输出的带 <<<SECTION>>> 的 docx
                    → 最终上传 HiAgent 的文件
eval_items/         eval_docx.py 的每份 JSON 结果
annotation_items/   annotate_docx.py 的每份 JSON 结果
summary_items/      summary_docx.py 的每份 JSON 结果
eval_merged.json    eval_items/ 合并后的整体 JSON
summary_merged.json summary_items/ 合并后的整体 JSON
std_gov_report_*.xlsx  generate_excel.py 生成的业务 Excel
```

## 关键设计决策

### 为什么 word_parser 输出两种格式

- `join_for_evaluation()` 给评估和摘要用:不带编号,段落自然衔接,接近人类阅读
- `format_for_annotation()` 给标注用:带 `[P0001]` 编号,带格式信号,便于模型定位

两种格式都基于同一个 `parse_docx()` 的结果,只是后处理不同。

### 为什么 prompt 独立成模块

- 改 prompt 不用动脚本,降低耦合
- 方便做 A/B 测试(需要时换一个 prompt 常量即可)
- schema 和 prompt 放一起,不会出现"改了 prompt 忘改 schema"

### 为什么评估、标注、摘要是独立链路

- 三者关注点不同:评估看质量、标注找节边界、摘要讲内容
- 评估和摘要都可以随时重跑,标注只需跑一次交付 HiAgent
- 拆开后每条链路的 prompt 更专注,输出更稳
- 单条失败不会连累其他

### 占位符的双重作用

`word_parser.py` 遇到非文字元素会加占位符标记(`<图片>` / `<表格: ...>` / `<含图形对象>` 等)。这些占位符:

- 让模型知道"这里有东西,不要误判为缺失"
- 评估 / 标注 / 摘要三个 prompt 都有专门说明(占位符不是"占位符残留"类问题、不影响节标题识别、摘要时忽略)

## 典型工作流

### 初次跑 60 份文档

```
1. pdf 手工转 docx → 统一放 converted_docx/
2. check_conversion.py 抽查转换质量,人工核对异常文件
3. 并行跑三条链路:
   - annotate_docx.py → 生成 output_docx/(带 <<<SECTION>>>)
   - eval_docx.py     → 生成 eval_items/
   - summary_docx.py  → 生成 summary_items/
4. output_docx/ 上传 HiAgent,配置按 <<<SECTION>>> 分块
5. template_merge.py 合并评估和摘要的 items → eval_merged.json + summary_merged.json
6. generate_excel.py 生成业务 Excel 给相关同事
7. HiAgent 智能体配置 agent_prompt.md,开始问答测试
```

### 某份文档需要重跑

```
1. 删除对应的 xxx_items/xxx.json
2. 重跑对应的链路脚本(只处理缺失的)
3. 重新 generate_excel.py(如果需要更新 Excel)
```

### 某条 prompt 规则要调整

```
1. 改对应的 *_prompt.py
2. 清空对应的 xxx_items/ 目录
3. 重跑脚本(断点续跑机制此时变为全量重跑)
```

## 后续待完成

- [ ] pdf 转 docx(手工,因 numpy 对 CPU 的要求测试机不满足)
- [ ] 60 份文档完整跑通三条链路
- [ ] 完整的手工实验后半段(带 `<<<SECTION>>>` 的 word 传 HiAgent,用业务问题测召回)
- [ ] 智能体实测与 prompt 迭代
- [ ] generate_excel.py 首次生成后人工核对格式是否符合业务阅读习惯

## 环境备忘

- 测试机 CPU(Intel Core 2 Duo T7700)不支持 x86-64-v2 指令集,numpy 2.x 在该机器上无法启动
- **不要在测试机安装 numpy**。目前项目代码本身不依赖 numpy
- 如果装了某个间接依赖 numpy 的包(如 pdf2docx 的 PyMuPDF),可能导致所有 Python 脚本启动时崩溃。解决方法:`python -m pip uninstall numpy`
