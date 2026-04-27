# 阶段一+阶段二交付清单

## zip 内的文件结构

```
refactor_delivery/
├── shared/                      # 复制到项目 shared/ 下
│   ├── __init__.py              # 新增
│   ├── batch_runner.py          # 新增
│   ├── config_loader.py         # 新增
│   ├── docx_check.py            # 新增(替代旧的 check_conversion.py)
│   └── llm_client.py            # 新增
├── tasks/
│   └── 01_std_eval/             # 整个目录新增到项目 tasks/ 下
│       ├── README.md
│       ├── config.schema.yaml
│       ├── config.yaml
│       ├── excel_export.py
│       ├── prompt.md
│       ├── runner.py
│       ├── schema.json
│       └── task.yaml
├── docs/
│   └── DECISIONS_appendix.md    # 内容追加到 docs/DECISIONS.md 末尾
└── README_DELIVERY.md           # 本文件
```

## 你需要手动做的事

### 一、复制新文件

1. 把 zip 里的 `shared/__init__.py`、`shared/llm_client.py`、`shared/batch_runner.py`、`shared/config_loader.py`、`shared/docx_check.py` 复制到项目 `shared/` 目录下
2. 把 zip 里的整个 `tasks/01_std_eval/` 目录复制到项目 `tasks/` 下

### 二、删除旧文件

- `shared/generate_excel.py` —— 已重写为 `tasks/01_std_eval/excel_export.py`
- `shared/template_merge.py` —— merged.json 这层中间产物已废弃
- `shared/check_conversion.py` —— 已重写为 `shared/docx_check.py`

### 三、追加决策日志

打开 `docs/DECISIONS_appendix.md`,把里面的内容(从 `## 06.` 开始,含分隔线)复制粘贴到项目 `docs/DECISIONS.md` 末尾。

### 四、保留不动

- `shared/word_parser.py`(原版即可,符合规范)
- `shared/inspect_styles.py`(开发期辅助工具,等阶段四统一处理)
- `tasks/01_std_eval/`、`tasks/02_std_annotate/`、`tasks/03_std_summary/` 旧目录暂时保留(等阶段三全部完成后再删,避免现在删了找不到旧逻辑做对照)
- `tasks/04_std_import/`(还在设计)
- `tasks/ARCHITECTURE.md`(等阶段四拆解吸收)

### 五、依赖清单

内网部署需要这四个 Python 包:

- openai
- python-docx
- pyyaml
- openpyxl

## 验证

如果想立刻试跑(可选,你说重跑成本高,可以等阶段三全部完成后一起跑):

1. 编辑 `tasks/01_std_eval/config.yaml`:
   - 填 `input_dir`(放几份 docx 测试)
   - 填 `output_items_dir`(任意空目录)
   - 填 `excel_output_dir`(任意空目录)
   - 改 `llm_base_url` 成你内网的实际地址
2. 跑 `cd tasks/01_std_eval && python runner.py`
3. 等 runner 跑完,再跑 `python excel_export.py`,看生成的 Excel
