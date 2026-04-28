# 任务模板使用说明

## 怎么用这个模板

1. 复制整个 `task_template/` 目录到 `tasks/` 下,改目录名为 `NN_task_name`(编号 + 蛇形命名)
2. 按下面的顺序逐个修改文件

## 修改顺序

### 第一步:task.yaml

改 `name` 和 `description`,定义任务在启动器列表里的显示名和一句话说明。

### 第二步:prompt.md + schema.json

先写 prompt(你希望模型做什么),再写 schema(你希望模型输出什么结构)。
这两个是业务的核心,和代码无关,改起来不会影响框架。

prompt 末尾的 `__DOCUMENT_TEXT__` 占位符不要删——runner.py 会把它替换成实际输入内容。

### 第三步:config.yaml + config.schema.yaml

按你的任务需要增删配置字段。两个文件要同步改:config.yaml 加一个字段,
config.schema.yaml 就要加一条声明。

字段命名遵守编码规范 3.2 节的约定:
- 路径字段以 `_dir` / `_path` / `_file` 结尾
- LLM 调用字段以 `llm_` 开头
- 阈值字段以 `threshold_` / `max_` / `min_` 开头
- Windows 路径不要加双引号(YAML 会把反斜杠当转义)

### 第四步:runner.py

修改 `handler` 函数里的业务逻辑。框架代码(config 加载、batch_runner 调用)
一般不用改。

如果你的任务不需要调 LLM,删掉 LLMClient 相关的代码即可。
如果你的输入不是 docx,改 `file_pattern` 和 handler 里的解析逻辑。

### 第五步:README.md

把这份"模板使用说明"替换成你任务的说明。参考 `tasks/01_std_eval/README.md` 的结构:
任务目的 → 产出 → 运行方式 → 断点续跑 → 配置说明 → 文件结构。

## 文件清单

```
NN_task_name/
├── task.yaml          # 任务元信息
├── config.yaml        # 运行参数
├── config.schema.yaml # 字段声明
├── prompt.md          # LLM 提示词模板
├── schema.json        # JSON schema 约束
├── runner.py          # 任务入口
└── README.md          # 任务说明(你正在读的这个,记得替换)
```

如果有任务专属的业务模块(如解析器、后处理脚本),直接放在任务目录下,
runner.py 里 import 即可。不通用的东西不要放 shared/。
