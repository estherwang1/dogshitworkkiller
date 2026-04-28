# CHANGELOG

项目演进的历史记录。新条目在上,旧条目在下。

## v0.4 — 阶段四收尾(2026-04-28)

重构的收尾工作:删除旧文件、更新文档、建任务模板,使项目从
"旧代码 + 新代码混杂"进入"重构后的干净状态"。

### 删除

- `shared/generate_excel.py` — 业务代码,已重写为 `tasks/01_std_eval/excel_export.py`
- `shared/template_merge.py` — merged.json 中间产物已废弃
- `shared/check_conversion.py` — 已重写为 `shared/docx_check.py`
- `tasks/01_std_eval/` 下旧脚本(`eval_docx.py` / `eval_prompt.py`)
- `tasks/02_std_annotate/` 下旧脚本(`annotate_docx.py` / `annotation_prompt.py`)
- `tasks/03_std_summary/` 整个目录(已在 v0.2 合并进任务 01)
- `tasks/ARCHITECTURE.md`(旧"标准规范知识库项目"的架构说明,信息已拆解吸收到各任务 README 和 docs/ARCHITECTURE)

### 新增

- `dev_tools/inspect_styles.py` — 从 shared/ 挪出,开发期辅助工具不混 shared
- `templates/task_template/` — 新建任务的脚手架(7 个文件),复制后改名即可用。模板 README 承担原 NEW_TASK_GUIDE.md 的职责
- `CHANGELOG.md` — 项目演进历史(本文件)
- `plan.md` — 下一步计划,和架构文档分离(计划经常变,架构不该跟着变)

### 修改

- `docs/ARCHITECTURE.md` — 目录树反映真实现状(去掉已删任务、加 dev_tools/templates/CHANGELOG/plan);shared 清单换成实际 5 个模块;任务文件清单的可选文件改为 prompt.md/schema.json;删除第七节整段(任务列表/状态/计划不属于架构)
- `docs/CODING_STANDARDS.md` 3.2 节 — 跨任务命名约定统一为 `llm_` 前缀(去掉 `model_` 选项),示例和实际代码对齐;路径示例加注释提醒 Windows 双引号陷阱
- `docs/DECISIONS.md` — 追加决策 06(业务文件命名保持短名)和决策 07(Claude 多文件交付打包 zip)
- `README.md` — 文档地图加 CHANGELOG 和 plan;造房子比喻加"施工日志"和"施工计划";快速上手段指向 templates;项目状态指向 CHANGELOG

### 关键设计

- 架构文档第七节删除的理由:任务列表是架构(第一节目录树已有),但任务状态和下一步计划是项目管理信息,不属于架构,分别进了 CHANGELOG 和 plan.md
- templates 而非 NEW_TASK_GUIDE:模板目录自带 README 作为使用说明,比独立的 guide 文档更贴近使用场景,不会产生"两份文档说同一件事"的困惑
- dev_tools 独立于 shared 和 tasks:开发期辅助工具不被任何组件 import,不是运行时依赖,放 shared 违反 shared 的"零业务通用工具"定位

---

## v0.3 — 任务 02 标注迁移(2026-04-27)

把旧的 `annotate_docx.py` + `annotation_prompt.py` 按新架构重写为
`tasks/02_std_annotate/`。

这个任务比任务 01 复杂:文档可能很长,模型一次调用的 token 撑不下,
需要分块调用 + 重叠区去重;输出不只是 JSON,还要把标记插回 docx
产出新文件。这两块逻辑被拆成任务专属模块,不进 shared。

### 新增

- `tasks/02_std_annotate/runner.py` — 任务入口,串起分块调用和 docx 写入
- `tasks/02_std_annotate/chunker.py` — 任务专属:按字符数切分调用范围,带重叠;合并多次调用结果,按段落编号去重;标记疑似边界(落在重叠区的标记)
- `tasks/02_std_annotate/docx_writer.py` — 任务专属:在 docx 对应段落前插入 `<<<SECTION>>>`,遍历顺序与 word_parser 一致保证编号对应
- `tasks/02_std_annotate/prompt.md` — 从原 `annotation_prompt.py` 搬出
- `tasks/02_std_annotate/schema.json` — 从原 `annotation_prompt.py` 搬出
- `tasks/02_std_annotate/task.yaml`
- `tasks/02_std_annotate/config.yaml` — 新增 `max_chars_per_call`(单次调用字符上限)和 `overlap_blocks`(重叠段落数)两个分块参数
- `tasks/02_std_annotate/config.schema.yaml`
- `tasks/02_std_annotate/README.md`

### 待删除(阶段四执行)

- 旧 `tasks/02_std_annotate/annotate_docx.py`
- 旧 `tasks/02_std_annotate/annotation_prompt.py`

### 关键设计

- 分块 + 合并 + docx 写入是任务专属逻辑,不进 shared,理由:只有标注任务需要,其他任务没有"输出比输入更长"的问题
- `<<<SECTION>>>` 保持硬编码(docx_writer 的默认参数),不做成 config 字段,理由:HiAgent 端按这个固定值分块,改了就要同时改 HiAgent 配置,做成 config 反而诱导乱改
- runner 里 handler 负责 JSON 和 docx 两份输出,batch_runner 只管 JSON 的断点续跑。docx 是 handler 内部的副产物,不扩展 batch_runner 接口,理由:shared 不为单个任务的特殊需求扩接口

---

## v0.2 — 任务 01 评估迁移,合并摘要(2026-04-27)

把旧的 `eval_docx.py` + `eval_prompt.py`(评估)和 `summary_docx.py` +
`summary_prompt.py`(摘要)合并为 `tasks/01_std_eval/`。

合并的理由:评估和摘要读的是同一份文档文本,调用同一个模型,目标
都是"理解这份文档说了什么和怎么样"。原来分成两个任务是因为先做了
评估、后来才想起加摘要,不是业务上有分离的必要。合并后 60 份文档
从跑 120 次模型变成 60 次。

### 新增

- `tasks/01_std_eval/runner.py` — 任务入口,约 85 行(原版各约 200 行)
- `tasks/01_std_eval/prompt.md` — 合并后的 prompt,先概述(标准名称 / 一句话概括 / 文档摘要)再评估(元信息 / 硬约束 / 质量分 / 问题清单)
- `tasks/01_std_eval/schema.json` — 合并后的 JSON schema,字段顺序按"概述 → 评估"
- `tasks/01_std_eval/excel_export.py` — 从原 `shared/generate_excel.py` 重写:直接读 items 目录而非 merged.json;主表的"评估状态/摘要状态"两列合为"任务状态"一列;修复了原版复核列标红的 off-by-one bug
- `tasks/01_std_eval/task.yaml`
- `tasks/01_std_eval/config.yaml` — 字段命名统一 `llm_` 前缀
- `tasks/01_std_eval/config.schema.yaml`
- `tasks/01_std_eval/README.md`

### 废弃(阶段四执行)

- 旧 `tasks/01_std_eval/eval_docx.py` + `eval_prompt.py`
- 旧 `tasks/03_std_summary/` 整个目录(已合并进 01)
- `shared/generate_excel.py`(已重写为任务内的 excel_export.py)
- `shared/template_merge.py`(merged.json 这层中间产物已废弃)

### 关键设计

- prompt 和 schema 从 .py 文件变成 .md + .json,实现数据资产与代码分离(哲学 2.1 维度 E)
- 配置从脚本顶部硬编码常量变成 config.yaml,字段命名遵守编码规范 3.2 节(`llm_` / `threshold_` 前缀)
- items 目录是任务的**结构化输出**(不是中间产物),Excel 是它的一个视图。断点续跑、失败标记都基于 items 目录
- 决策 06:讨论过给业务文件加任务前缀(eval_prompt.md 等),最终不加,理由:真实痛点是聊天交付摊平了目录,解法是打包 zip(决策 07),不改项目命名
- 决策 07:Claude 多文件交付打包成 zip,保留目录结构

---

## v0.1 — shared 层重构(2026-04-27)

从旧代码的三个脚本(eval_docx.py / annotate_docx.py / summary_docx.py)
中提取重复代码,抽成 shared 下的通用模块。同时把不符合 shared 边界
规则(编码规范 2.1)的业务代码清出 shared。

### 新增

- `shared/__init__.py` — 包标识,docstring 里写明 shared 的边界规则
- `shared/llm_client.py` — LLM 调用封装:LLMClient 类(复用 base_url/model/timeout)+ extract_first_json 兜底解析 + 4 个自定义异常类(LLMError / LLMTruncatedError / LLMEmptyResponseError / LLMJSONParseError)
- `shared/batch_runner.py` — 批量处理框架:扫输入目录、断点续跑、失败隔离、进度打印。任务侧只需提供 handler 回调函数
- `shared/config_loader.py` — 读 YAML 配置,返回 dict,空文件返回空 dict,顶层非 dict 抛 ValueError
- `shared/docx_check.py` — 改写自原 `check_conversion.py`:阈值全部参数化,函数签名传入,shared 不预设经验值

### 不动

- `shared/word_parser.py` — 原版符合规范,保留

### 待删除(阶段四执行)

- `shared/generate_excel.py` — 重业务代码(硬约束/质量分等字段),违反 shared 边界规则,已挪到任务 01
- `shared/template_merge.py` — merged.json 不再需要
- `shared/check_conversion.py` — 已重写为 docx_check.py

### 关键设计

- batch_runner 只暴露一个公共函数 `run_batch`,其余全是私有工具函数。任务侧写一个 handler(Path) -> dict 就够,所有样板代码(扫目录、断点续跑、写 success/failure JSON、计时)由框架承担
- llm_client 用类而非函数,理由:同一个任务里 base_url/model/timeout 固定,做成实例属性避免每次调用重复传参
- 自定义异常体系让调用方能按错误类型处理(截断可重试、解析失败重试无用),但当前不强制区分,统一 catch LLMError 也行
- docx_check 阈值参数化后,shared 真正零业务;业务经验值(如"标准规范文档文件大小 < 5KB 视为异常")由调用方通过 config 传入
