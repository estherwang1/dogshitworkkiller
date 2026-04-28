# DogshitWorkKiller 架构文档

本文档是项目的"图纸目录"——描述**东西在哪、叫什么、怎么连**。

**本文档适用范围**:DogshitWorkKiller 单个项目内部的架构
(系统内架构,相当于"单栋别墅的图纸目录")。
跨系统集成、多项目协同不在本文档范围内。

**与其他文档的关系**:

- 本文档 = 图纸目录(东西在哪)
- 编码规范 = 施工标准(怎么造)
- 决策日志 = 改造档案(为什么这么造)
- 哲学 = 世界观(什么是好的)

具体"怎么写、怎么做"见编码规范。本文档不讲实现细节。

---

## 一、目录树

```
DogshitWorkKiller/
│
├── launcher/                    # 启动器(Tkinter GUI)(待实现)
│   ├── main.py                  # 入口,双击快捷方式跑这个
│   ├── task_loader.py           # 扫 tasks/ 目录发现任务
│   ├── config_editor.py         # 配置可视化编辑组件
│   └── runner_proxy.py          # 起子进程跑任务、捕获日志
│
├── tasks/                       # 所有任务,一个文件夹一个任务
│   ├── 01_std_eval/             # 任务 1:标准规范评估(含摘要)
│   └── 02_std_annotate/         # 任务 2:标准规范分块标注
│
├── shared/                      # 多任务共用的零业务工具
│   (具体模块见第三节)
│
├── dev_tools/                   # 开发期辅助工具(不进 shared 不进 tasks)
│   └── inspect_styles.py        # 统计 docx 段落样式分布
│
├── templates/                   # 新建任务的模板(待建)
│   └── task_template/           # 复制后改名即可用
│
├── docs/
│   ├── DESIGN_PHILOSOPHY.md     # 设计哲学(世界观)
│   ├── ARCHITECTURE.md          # 本文档(图纸目录)
│   ├── CODING_STANDARDS.md      # 编码规范(施工标准)
│   └── DECISIONS.md             # 决策日志(改造档案)
│
├── CHANGELOG.md                 # 项目演进历史
├── plan.md                      # 下一步计划
└── README.md                    # 项目总入口说明
```

---

## 二、组件依赖关系

```
launcher/  ──进程调用──>  tasks/*/runner.py
                              │
                              │ import
                              ▼
                          shared/
```

**依赖规则**:

- launcher 不 import tasks,只通过子进程和文件通信
- tasks 只依赖 shared,任务之间不相互依赖
- shared 不依赖任何 tasks 或 launcher
- dev_tools 是独立辅助工具,不被任何组件依赖

依赖规则的具体执行方式见编码规范"项目契约"一章。

---

## 三、shared 模块清单

| 模块 | 职责 |
|------|------|
| `word_parser.py` | Word 文档结构化解析,产出通用块级列表。提供 `parse_docx` / `join_for_evaluation` / `format_for_annotation` 三个函数 |
| `llm_client.py` | LLM 调用封装。`LLMClient` 类复用连接参数,`call_json` 方法含 JSON 解析兜底和 response_format 约束。4 个自定义异常类 |
| `batch_runner.py` | 批量处理框架。`run_batch` 一个公共函数,承担目录扫描、断点续跑、失败隔离。任务侧只需提供 handler 回调 |
| `config_loader.py` | 读 YAML 配置文件,返回 dict,做顶层结构校验 |
| `docx_check.py` | docx 文件质量检查。阈值全部参数化,shared 不预设经验值 |

**模块清单会随项目演化**。新增或修改 shared 模块时更新本表。

---

## 四、任务目录文件清单

任务目录(`tasks/NN_task_name/`)包含的文件:

| 文件 | 用途 | 谁读 | 变化频率 |
|------|------|------|----------|
| `task.yaml` | 任务元信息(名字、说明、入口) | 启动器 | 很少 |
| `config.yaml` | 运行参数(路径、模型、阈值) | runner | 经常 |
| `config.schema.yaml` | 配置字段声明(类型、默认值、控件) | 启动器 | 随 config.yaml |
| `runner.py` | 任务主脚本 | 用户/启动器 | 稳定 |
| `README.md` | 任务说明 | 接手者 | 偶尔 |

可选文件(按业务需要):

- `prompt.md`:LLM 提示词模板(数据资产,和代码分离)
- `schema.json`:JSON schema 约束(配合 prompt 使用)
- 任务专属模块(如 `chunker.py`、`docx_writer.py`、`excel_export.py`):不通用的业务逻辑,不进 shared

**各文件的具体写法(字段结构、代码模式)见编码规范。**

---

## 五、启动器职责清单(待实现)

启动器的五项职责:

1. **发现任务**:扫 `tasks/` 目录,读各任务的 `task.yaml`,生成任务列表
2. **生成配置 UI**:读 `config.schema.yaml`,按字段声明生成 Tkinter 编辑界面
3. **保存配置**:用户改完点保存,写回 `config.yaml`
4. **触发任务**:以子进程方式启动 runner.py,传入任务目录作为参数
5. **捕获日志**:实时读子进程的 stdout/stderr,显示到日志区

**具体的代码实现方式见编码规范。**

---

## 六、启动器 UI 布局(待实现)

```
┌─────────────────────────────────────────────────┐
│ DogshitWorkKiller                               │
├─────────────┬───────────────────────────────────┤
│ 任务列表     │ 任务详情 / 配置编辑                │
│             │                                   │
│ ○ 任务 1    │ 名称:标准规范评估                 │
│ ● 任务 2    │ 说明:扫目录跑评估...              │
│             │                                   │
│             │ 配置:                             │
│             │   输入路径: [_________] [浏览]     │
│             │   模型名:   [下拉选单  ▼]          │
│             │   阈值:     [_________]           │
│             │                                   │
│             │ [保存配置] [运行] [打开输出目录]    │
│             ├───────────────────────────────────┤
│             │ 日志:                             │
│             │  [1/50] 评估: xxx.docx            │
│             │  ✓ 完成 (耗时 5s)                 │
│             │  ...                              │
└─────────────┴───────────────────────────────────┘
```

---

## 七、本文档的更新规则

- 改变目录结构、模块清单、文件清单:必须更新本文档
- 不涉及结构的代码变动:不必更新本文档(改代码即可)
