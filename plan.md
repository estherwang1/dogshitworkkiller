# 下一步计划

已完成的从这里删除,进 CHANGELOG.md 留底。

---

## 近期

### 阶段四收尾(剩余部分)

1. 更新 `docs/ARCHITECTURE.md`
   - 第一节目录树:反映 dev_tools/ 和变化后的 tasks/(01 合并了摘要、03 已删、新增 templates/)
   - 第三节 shared 模块清单:加 llm_client / batch_runner / config_loader / docx_check;删 io_utils / excel_writer(未实现的占位)
   - 第四节任务目录文件清单:可选文件从 `prompt.py` / `parser.py` 改为 `prompt.md` / `schema.json` / 任务专属模块
   - 删除第七节整段(任务列表在第一节已有,计划在 plan.md,状态/来源在 CHANGELOG)

2. 建 `templates/task_template/`
   - 从任务 01 抽一份最小骨架(task.yaml / config.yaml / config.schema.yaml / runner.py / prompt.md / schema.json / README.md)
   - 模板的 README.md 说明"复制本目录到 tasks/ 下,改名,按注释填写"

3. 更新根目录 `README.md`
   - "快速上手"段:指向 templates/task_template/
   - "项目状态"段:不再指向 ARCHITECTURE 第七节,改为指向 CHANGELOG
   - 文档地图:加上 CHANGELOG.md 和 plan.md

---

## 远期

- 搭建启动器基础框架(Tkinter GUI,读 task.yaml / config.schema.yaml 生成界面)
- 设计并实现任务 04:新规范入库(查重 + 上传平台 + 更新目录)
- 在内网完整跑通 60 份文档的评估 + 标注
- HiAgent 端配置按 `<<<SECTION>>>` 分块,用业务问题测 RAG 召回效果
- 智能体 prompt 迭代

---

## 想法池

- 扩展到第二个微应用(邮箱整理)
- excel_export.py 是否值得做成独立任务(从启动器里触发)而非手动跑脚本
