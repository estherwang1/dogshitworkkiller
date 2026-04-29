# DogshitWorkKiller 编码规范

本文档是项目的"施工标准"——描述**代码具体怎么写、组件之间的边界在哪**。

**本文档适用范围**:DogshitWorkKiller 项目内的所有 Python 代码和配置文件。

**与其他文档的关系**:

- 哲学 = 世界观(为什么这样)
- 架构文档 = 图纸目录(东西在哪)
- 本文档 = 施工标准(怎么写)
- 决策日志 = 改造档案(当初为什么选这个方案)

本文档可以引用哲学(说明"为什么"),不引用决策日志。

---

## 第一部分:通用 Python 规范

任何 Python 项目都该遵守的基础规范。

### 1.1 代码风格:遵循 PEP 8

- **缩进**:4 个空格,禁用 Tab
- **行宽**:不超过 120 字符
- **空行**:顶层函数和类之间空 2 行,类内方法之间空 1 行
- **运算符两侧空格**:`a = 1 + 2`,不是 `a=1+2`
- **逗号后空格**:`foo(a, b, c)`,不是 `foo(a,b,c)`

推荐使用 `ruff` / `black` 等格式化工具自动处理。

### 1.2 命名规范

- **变量、函数、模块名**:`snake_case`
- **类名**:`PascalCase`
- **常量**:`UPPER_CASE_WITH_UNDERSCORES`
- **私有成员**:前缀单下划线 `_private_helper`
- **语言**:注释、字符串、文档可以用中文;变量名、函数名、文件名必须用英文

命名要描述"是什么"或"做什么",不要用 `data1`、`tmp`、`process()` 这类无信息量的名字。

### 1.3 注释与文档

**Docstring 风格:Google 风格**

所有对外接口必须有 docstring。内部辅助函数可省,但若逻辑复杂仍建议写。

格式示例:

```python
def parse_document(path: str) -> list[dict]:
    """解析文档,返回块级元素列表。

    按 body 顺序遍历段落和表格,按真实交错顺序编号。

    Args:
        path: 文档文件的绝对路径。

    Returns:
        块级元素列表,每个元素含 id / type / text 等字段。

    Raises:
        FileNotFoundError: path 指向的文件不存在。
    """
```

**注释原则**:

- 注释写"为什么",不写"是什么"
- 反例:`i += 1  # i 加 1`
- 正例:`i += 1  # 跳过表头行`

### 1.4 Pythonic 惯用法

- **路径处理**:用 `pathlib.Path`,不用 `os.path` 拼字符串
- **资源管理**:用 `with` 语句,不手动 close
- **推导式**:简单变换用列表/字典推导,复杂逻辑用显式循环
- **早返回**:减少嵌套,处理边界条件后尽快返回
- **类型标注**:对外接口(函数签名、类属性)必须有类型标注

---

## 第二部分:项目契约

本项目各组件之间的边界规则。违反这些规则会破坏项目的解耦结构。

### 2.1 shared 边界

**规则**:shared 存放零业务的通用工具。

**红线**:

1. 不允许包含业务词汇(函数名、常量、注释、文档皆是)
2. 不允许 import 任何任务代码(单向依赖:任务→shared,反之不行)
3. 函数只接受通用类型,不接受业务对象
4. 新增模块自问:搬到完全不同的项目能不能直接用?不能→不要进 shared

### 2.2 任务隔离

**规则**:每个任务是独立单元,彼此不相关。

**红线**:

1. 任务之间禁止相互 import
2. 任务只能依赖 shared,不允许依赖其他任务
3. 任务的入口脚本必须能独立运行(不依赖启动器)
4. 任务对外交互只有三种:读自己的配置、写输出文件、调 shared

### 2.3 配置与代码分离

**规则**:所有运行参数外置到配置文件,代码不含硬编码常量。

**红线**:

1. 路径、模型名、阈值、API Key 不允许出现在代码里
2. 配置按"读者和变化频率"拆分到不同文件,不能一个大 config 装所有
3. 配置字段必须有类型和用途声明(让启动器能生成可视化编辑 UI)
4. 配置字段必须遵守跨任务统一的命名约定(见 3.3 节)

### 2.4 启动器与任务的通信

**规则**:启动器与任务之间只通过文件和子进程通信,不通过 import。

**启动器侧红线**:

1. 禁止 import 任务代码
2. 禁止修改任务的业务逻辑(启动器不碰任务入口脚本)
3. 禁止绕过配置文件直接给任务传参

**任务侧约束**:

1. 任务必须保证启动器能实时看到输出(不能带缓冲)
2. 任务必须支持被启动器调用(接收任务目录参数)和独立运行两种方式

具体实现方式见 3.4 节和 3.5 节。

---

## 第三部分:施工规范

本项目特有的文件格式、代码模式等具体实现规范。

### 3.1 task.yaml 字段结构

```yaml
name: 标准规范评估
description: 扫输入目录或单份文件,跑 LLM 评估,输出 JSON 和 Excel
entry: runner.py
actions:
  - name: 导出 Excel
    script: excel_export.py
version: "1.0"
```

字段说明:

- `name`: 启动器列表显示的名字
- `description`: 一句话说明任务做什么
- `entry`: 主入口脚本相对任务目录的路径,启动器的"运行"按钮执行这个脚本
- `actions`: 附加操作列表(可选),每项含 `name`(按钮显示名)和 `script`(脚本相对路径)。启动器为每个 action 生成一个额外按钮。无附加操作时省略此字段
- `version`: 任务版本

### 3.2 config.yaml 字段结构

字段随任务不同,但必须遵守跨任务统一的命名约定。

**跨任务命名约定**:

- 路径字段以 `_dir` / `_path` / `_file` 结尾
- 模型和 LLM 调用相关字段统一以 `llm_` 开头
- 阈值字段以 `threshold_` / `max_` / `min_` 开头

示例:

```yaml
# 路径类字段
input_dir: "C:/std_gov/input"
output_items_dir: "C:/std_gov/eval_items"

# LLM 调用类字段
llm_model_name: Qwen3.5-35B-A3B
llm_base_url: http://a.b.c.d:e/v1
llm_timeout: 600
llm_max_tokens: 4096

# 阈值类字段
threshold_long_doc_chars: 180000
```

---

## 3.3 config.schema.yaml 字段结构

每个 config.yaml 字段对应一条声明:

```yaml
input_path:
  type: path
  widget: file_or_dir
  required: true
  default: ""
  description: 输入源,可以是单个 docx 文件或包含多份 docx 的目录

model_name:
  type: string
  widget: dropdown
  options: ["Qwen3.5-35B-A3B", "Qwen2.5-72B"]
  required: true
  default: Qwen3.5-35B-A3B
  description: 使用的 LLM 模型名

threshold_long_doc_chars:
  type: integer
  widget: number
  required: false
  default: 180000
  description: 超长文档字符数阈值,超过此值会提示人工核查
```

**字段属性说明**:

- `type`: 数据类型——path / string / integer / float / boolean / enum
- `widget`: 编辑控件——file / dir / file_or_dir / text / number / checkbox / dropdown
- `required`: 是否必填
- `default`: 默认值
- `options`: (仅 dropdown)下拉选项
- `description`: 字段说明,启动器 UI 上显示为提示

### 3.4 runner.py 的标准启动模式

runner 必须支持两种调用方式。

**启动器调用**(传任务目录):

```bash
python tasks/01_std_eval/runner.py tasks/01_std_eval
```

**独立运行**(读自己目录下的 config):

```bash
cd tasks/01_std_eval
python runner.py
```

**标准启动代码**:

```python
import sys
from pathlib import Path
from shared.config_loader import load_config

# 设置 stdout 行缓冲,让启动器实时捕获日志
sys.stdout.reconfigure(line_buffering=True)

# 解析任务目录:启动器传入优先,否则用脚本所在目录
if len(sys.argv) > 1:
    task_dir = Path(sys.argv[1])
else:
    task_dir = Path(__file__).parent

config = load_config(task_dir / "config.yaml")

# 之后就是任务业务逻辑
...
```

### 3.5 日志输出规则

- 用 `print` 输出进度,不用 `logging`(理由:见决策日志)
- 需要时间戳自己加:`print(f"[{datetime.now()}] xxx")`
- 任务开头必须设置 `sys.stdout.reconfigure(line_buffering=True)`

### 3.6 启动器调用子进程的代码模式

**用 `subprocess.Popen`,不用 `subprocess.run`**(需要流式读日志)

```python
process = subprocess.Popen(
    [sys.executable, str(runner_path), str(task_dir)],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    bufsize=1,
    text=True,
    encoding="utf-8",
)
for line in process.stdout:
    log_widget.insert("end", line)
    log_widget.see("end")
    root.update_idletasks()
```

---

## 第四部分:错误处理规范

### 4.1 异常处理原则

- runner 主循环必须 try/except 包住单次调用
- 捕获后写入结果 JSON 的 `_status: failed` 字段
- 不允许裸抛 Traceback 导致整体流程退出

这对应项目工程哲学 2.1 维度 C(单个失败与整体流程分离)。

### 4.2 断点续跑

批量任务必须支持断点续跑:

- 每份输入对应一份输出 JSON
- 存在且非 failed 状态时跳过,不重复处理
- 想强制重跑:删对应输出 JSON 后重启

---

## 第五部分:本文档的维护

- 改变代码规范:更新第一部分
- 改变组件边界:更新第二部分
- 改变文件格式或代码模式:更新第三部分
- 新增错误处理约定:更新第四部分
