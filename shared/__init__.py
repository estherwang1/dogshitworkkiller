"""shared: 多任务共用的零业务工具

边界规则见 docs/CODING_STANDARDS.md 第 2.1 节:
- 不允许业务词汇
- 不允许 import 任务代码
- 函数只接受通用类型,不接受业务对象
- 搬到完全不同的项目能不能直接用?不能 → 不要进 shared
"""
