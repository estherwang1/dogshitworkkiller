# 环境搭建指南

本文档适用于:**内外网隔离,有大模型 API 可用,但没有标准开发环境**的场景。
记录如何从零搭建 Python 运行环境并管理离线依赖包。

---

## 前提

- Windows 系统
- 内网有可用的大模型 API(OpenAI 兼容接口)
- 无法在内网直接联网安装任何东西

---

## 一、外网准备(在能联网的电脑上做完)

所有需要联网的操作都在外网完成。做完后你会得到两样东西搬到内网:
一个装好 pip 的嵌入式 Python 目录,一个离线包目录。

### 1.1 下载嵌入式 Python

访问 https://www.python.org/downloads/ ,下载对应版本的
**Windows embeddable package (64-bit)**。文件名类似 `python-3.13.x-embed-amd64.zip`。

### 1.2 解压

解压到一个目录,例如 `D:\python3.13`。解压后目录里大概有这些文件:

```
D:\python3.13\
├── python.exe
├── python313.dll
├── python313._pth
├── python313.zip
└── ...
```

### 1.3 修改 ._pth 文件

这一步**必须做**,否则 pip 装不上、第三方包也找不到。

打开 `python313._pth`(文件名里的数字对应 Python 版本,3.12 就是 `python312._pth`),
找到被注释掉的这一行:

```
#import site
```

把 `#` 去掉,改成:

```
import site
```

保存。这行的作用是让 Python 加载 site-packages 目录,pip 和所有第三方包
都依赖这个机制。

### 1.4 安装 pip

嵌入式 Python **默认不带 pip**,需要手动装。

下载 `get-pip.py`:

```
https://bootstrap.pypa.io/get-pip.py
```

运行:

```cmd
D:\python3.13\python.exe get-pip.py
```

安装完成后,pip 会出现在 `D:\python3.13\Scripts\` 目录下。

验证:

```cmd
D:\python3.13\Scripts\pip.exe --version
```

**重要**:这一步必须在外网做——get-pip.py 运行时需要联网下载依赖。
内网没有网络,跑 get-pip.py 会失败。

### 1.5 下载项目依赖包

离线包统一存放在 `D:\offline-whls`,作为独立目录管理。
所有项目共用这一个目录,避免包文件散落在各处。

```cmd
mkdir D:\offline-whls
```

具体装哪些包取决于你的项目。查看项目的 README 或 requirements.txt
确认依赖清单,然后下载:

```cmd
:: 方式一:逐个指定包名
pip download -d D:\offline-whls 包名1 包名2 包名3

:: 方式二:如果项目提供了 requirements.txt
pip download -d D:\offline-whls -r requirements.txt
```

以后需要新包时,往同一个目录里继续 download 即可,已有的不会重复下载。

### 1.6 搬运到内网

把以下两样东西通过 U 盘、共享文件夹等方式搬到内网机器:

- **整个 `D:\python3.13\` 目录**(已经带 pip 和 Scripts)
- **整个 `D:\offline-whls\` 目录**(离线包)

建议内网也放在同样的路径(`D:\python3.13` 和 `D:\offline-whls`),
方便团队统一文档和命令。

---

## 二、内网部署

以下操作在内网机器上完成。不需要联网。

### 2.1 配置系统环境变量(可选但建议)

把以下两个路径加到系统 PATH:

```
D:\python3.13
D:\python3.13\Scripts
```

加完后,命令行里可以直接用 `python` 和 `pip`,不需要每次输完整路径。

设置方法:系统设置 → 搜索"环境变量" → 编辑 Path → 新增上面两行。

如果**不想改环境变量**(比如怕和其他 Python 冲突),每次运行时用完整路径即可:

```cmd
D:\python3.13\python.exe runner.py
D:\python3.13\Scripts\pip.exe install xxx
```

### 2.2 安装依赖包

```cmd
:: 方式一:逐个指定
pip install --no-index --find-links=D:\offline-whls 包名1 包名2 包名3

:: 方式二:从 requirements.txt
pip install --no-index --find-links=D:\offline-whls -r requirements.txt
```

`--no-index` 告诉 pip 不要联网找包,`--find-links` 指定从本地目录找。

验证(以某个包为例):

```cmd
python -c "import 包名; print('OK')"
```

---

## 三、以后加新依赖

同样的流程,外网下载,搬运,内网安装:

```cmd
:: 外网
pip download -d D:\offline-whls 新包名

:: 搬运(增量搬 offline-whls 里新增的 .whl 文件即可)

:: 内网
pip install --no-index --find-links=D:\offline-whls 新包名
```

---

## 四、常用命令

### 运行脚本

```cmd
python 脚本路径.py
```

### 查看已装包

```cmd
pip list
```

### 查看单个包版本

```cmd
pip show 包名
```

### 导出当前环境的包列表(给别人复现用)

```cmd
pip freeze > requirements.txt
```

### 从 requirements.txt 批量下载(外网)

```cmd
pip download -d D:\offline-whls -r requirements.txt
```

### 从 requirements.txt 批量安装(内网)

```cmd
pip install --no-index --find-links=D:\offline-whls -r requirements.txt
```

---

## 五、已知的坑

### 5.1 ._pth 文件没改

症状:装完 pip 后 `import xxx` 报 ModuleNotFoundError。

原因:嵌入式 Python 默认不加载 site-packages。

解决:见第一节 1.3 步,把 `#import site` 的 `#` 去掉。

### 5.2 在内网跑 get-pip.py

症状:get-pip.py 报网络连接错误。

原因:get-pip.py 运行时需要联网下载 pip 的依赖。内网没网。

解决:在外网装好 pip,把整个 Python 目录搬过来。见第一节流程。

### 5.3 YAML 配置文件里 Windows 路径用了双引号

症状:YAML 解析报错 `found unknown escape character`。

原因:YAML 双引号字符串里 `\` 是转义前缀,`\s`、`\i` 等不是合法转义。

解决:路径不加引号,或用单引号:

```yaml
# 正确
input_dir: C:\std_gov\input

# 正确
input_dir: 'C:\std_gov\input'

# 错误,会报转义错误
input_dir: "C:\std_gov\input"
```

---

## 六、项目与 Python 的关系

项目代码和 Python 环境是**互相独立**的:

- 项目放在任意目录(如 `D:\projects\你的项目\`)
- Python 放在另一个目录(如 `D:\python3.13\`)
- 离线包放在第三个目录(如 `D:\offline-whls\`)
- 三者之间没有硬绑定,搬运项目不需要搬 Python,升级 Python 不需要改项目

唯一的连接点是配置文件里的路径和运行时用哪个 python.exe。
不存在虚拟环境(venv),不存在项目内嵌的 Python。
