# 任务 02:标准规范分块标注

## 任务目的

读 docx 文档,识别哪些段落应作为 RAG 切块的边界,在对应段落前插入分块
标识符 `<<<SECTION>>>`,产出新 docx 供 HiAgent 知识库按标识符切块。

## 产出

每份输入 docx 产出两份文件:

1. **标注后的 docx**,放在 `output_docx_dir`,保持输入的子目录结构
2. **识别结果 JSON**,放在 `output_items_dir`,扁平化命名

JSON 字段(详见 `schema.json` 加 `output_docx` 字段):

| 字段 | 说明 |
|------|------|
| `标准名称` | 从文档首部提取,提取不到则用文件名 |
| `节标记列表` | 每项含段落编号、节标题预览、识别依据、置信度 |
| `统计` | 总段落数、标记段落数、低置信度数 |
| `疑似边界` | 落在分块重叠区的标记,供人工复核 |
| `分块信息` | 每段调用范围 + 识别出的标记数 |
| `output_docx` | 输出 docx 的相对路径 |
| `source_file` | 自动注入,输入文件相对路径 |

失败时 JSON 格式同其他任务(`_status: failed` + `_error` + `_timestamp`)。

## 关于分块调用

文档过长时,模型一次调用 token 不够,会按 `max_chars_per_call` 切成多段
调用,相邻段保留 `overlap_blocks` 个段落作为重叠区。重叠区内的标记会被
合并去重,并在结果 JSON 的 `疑似边界` 字段里列出供人工核查。

如果某次调用因 max_tokens 不够被截断,会抛 `LLMTruncatedError`,该份文
档被标 failed,其他文档不受影响。可调大 `llm_max_tokens` 后删除 failed
JSON 重跑。

## 运行方式

### 独立运行(命令行)

```bash
cd tasks/02_std_annotate
# 先修改 config.yaml(填 input_dir、output_items_dir、output_docx_dir、llm_base_url 等)
python runner.py
```

### 启动器调用

```bash
python tasks/02_std_annotate/runner.py tasks/02_std_annotate
```

## 断点续跑

`output_items_dir` 中已存在且非 `failed` 状态的 JSON 会被跳过。

注意:**output_docx_dir 中可能残留上次失败前生成的中间文件**。理论上失败
应该不会写出 docx(handler 抛异常前 docx 未生成),但如果网络中断等情况
下出现残留,新一轮处理会覆盖同名文件,不会报错。

## 配置说明

详见 `config.schema.yaml` 的 description 字段。关键参数:

- `input_dir` / `output_items_dir` / `output_docx_dir`:三个路径
- `llm_max_tokens`:默认 8192,长文档识别结果多,不要小于此值
- `max_chars_per_call`:默认 80000,约对应 80K token,超过分块调用
- `overlap_blocks`:默认 20,过小漏识别,过大浪费 token

## 文件结构

```
02_std_annotate/
├── task.yaml          # 任务元信息(给启动器读)
├── config.yaml        # 运行参数(用户编辑)
├── config.schema.yaml # 字段声明(给启动器生成 UI)
├── prompt.md          # LLM 提示词模板
├── schema.json        # JSON schema 约束
├── runner.py          # 任务入口
├── chunker.py         # 任务专属:切分 + 合并去重
├── docx_writer.py     # 任务专属:把标记插回 docx
└── README.md          # 本文件
```

## 与下游 HiAgent 的接口

`<<<SECTION>>>` 这个值是 HiAgent 知识库按其切块的固定字符串,由用户在
HiAgent 端手动配置。**不要修改 docx_writer.py 里的默认 marker_text**,
除非同时修改 HiAgent 配置。

智能体侧用 prompt 过滤 `<<<SECTION>>>` 不展示给最终用户。
