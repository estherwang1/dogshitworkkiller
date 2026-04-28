# 任务 01:标准规范评估

## 任务目的

扫输入目录的 docx 文件,对每份调用一次 LLM,产出两类信息:

- **概述**:一句话概括 + 文档摘要(让业务人员快速了解文档讲什么)
- **评估**:元信息、硬约束、质量分、问题清单(支持治理改进)

历史上"摘要"和"评估"是两个独立任务,跑两次 LLM。合并后只跑一次,
因为它们读的是同一份文本,目标都是"理解这份文档说了什么+怎么样"。

## 产出

每份输入 docx 对应一份 JSON,放在 `output_items_dir`(由 config.yaml 配置)。

完整字段结构见 `schema.json`。主要字段:

| 字段 | 说明 |
|------|------|
| `标准名称` | 从文档首部提取,提取不到则用文件名 |
| `一句话概括` | 大致 30 字,精准可判断 |
| `文档摘要` | 100-200 字,客观描述 |
| `元信息.标准类型` | 原则性 / 执行性 / 混合性 |
| `元信息.是否监管要求` | 建议(是/疑似/否) + 置信度(高/中/低) |
| `元信息.可检查性主导类型` | 自动 / 半自动 / 人工有标准 / 人工主观 |
| `硬约束.*` | 5 项,每项 命中(bool) + 证据(原文片段) |
| `质量分.*` | 3 项,每项 建议分(1-5) + 证据;原则性文档的可操作性为 null |
| `问题清单` | 最多 5 条,每条 章节/描述/证据 |
| `source_file` | 自动注入,输入文件相对路径 |

失败时 JSON 格式:
```json
{
  "source_file": "xxx.docx",
  "_status": "failed",
  "_error": "错误类型: 描述",
  "_timestamp": "2026-04-25 12:34:56"
}
```

## 运行方式

### 独立运行(命令行)

```bash
cd tasks/01_std_eval
# 先修改 config.yaml(填 input_dir、output_items_dir、llm_base_url 等)
python runner.py
```

### 启动器调用

启动器自动传入任务目录:

```bash
python tasks/01_std_eval/runner.py tasks/01_std_eval
```

## 断点续跑

`output_items_dir` 中已存在且非 `failed` 状态的 JSON 会被跳过,只处理新的或失败的。

强制重跑某份:删除对应的 JSON,再次运行即可。

## 配置说明

详见 `config.schema.yaml` 的 description 字段。关键参数:

- `input_dir`:输入目录,递归扫描 .docx
- `output_items_dir`:输出 JSON 目录
- `excel_output_dir`:Excel 导出目录(仅 excel_export.py 用)
- `llm_base_url` / `llm_model_name`:LLM 服务地址和模型名
- `llm_max_tokens`:默认 4096,合并后输出较长,不要小于此值
- `llm_temperature`:默认 0.1,评估类任务需要稳定输出
- `threshold_long_doc_chars`:文档过长时打印警告(不影响处理),默认 180000

## 文件结构

```
01_std_eval/
├── task.yaml          # 任务元信息(给启动器读)
├── config.yaml        # 运行参数(用户编辑)
├── config.schema.yaml # 字段声明(给启动器生成 UI)
├── prompt.md          # LLM 提示词模板
├── schema.json        # JSON schema 约束
├── runner.py          # 任务入口:调 LLM 生成 items
├── excel_export.py    # 业务交付:items → Excel
└── README.md          # 本文件
```

## Excel 导出

```bash
cd tasks/01_std_eval
# config.yaml 里要先填好 excel_output_dir
python excel_export.py
```

或从启动器调用(传任务目录):

```bash
python tasks/01_std_eval/excel_export.py tasks/01_std_eval
```

产出 `excel_output_dir/result_YYYYMMDD_HHMM.xlsx`,包含三个 sheet:

- **主表**:一份文档一行,含元信息、硬约束、质量分、概述、状态;失败行整行标红;末尾两列(复核结论/复核备注)留作人工填写
- **问题清单**:每条 `问题清单` 一行,含章节/描述/证据 + 复核列
- **失败列表**:抽取失败的文档及错误信息

excel_export.py 不调用 LLM,可反复运行。修改 Excel 格式无需重跑 runner。
items 目录里损坏的 JSON 会被跳过并打印警告,不中断生成。
