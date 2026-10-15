# ACC 数据与规则基础

所有本阶段代码及成果位于本目录。原 PDF 和法规结构/RDF 文件仅作为输入读取。

## 当前状态

- 462 条 DSL 规则已完成保守范围筛选，97 条进入可计算候选集合，365 条延期。
- IFC4 Profile、项目属性约定、11 项 IBC—IFC 候选映射已生成。
- IDS 包含 6 项信息要求，已通过 Schema 校验和证据关联校验。
- MVP 目录包含 5 项数量子检查、1 项连通性子检查和 2 项项目信息检查。
- IFC 预检、声明属性清单提取和候选空间—门邻接提取已有命令行入口。
- 已下载 2 个 GitHub IFC4 样例并运行真实文件集成测试，见 `model_tests/report.md`。25 项回归测试仍使用临时合成数据；样例缺少规则所需证据，尚无实际项目合规结论。

## 运行环境

当前验证环境为 Windows / Python 3.12，依赖安装于 `.python_deps`。
其他机器可从项目目录执行：

```powershell
python -m pip install -r output/acc/requirements.lock.txt --target output/acc/.python_deps
```

仅重新构建本阶段成果：

```powershell
python output/acc/src/run_foundation.py
```

或逐项运行：

```powershell
python output/acc/src/build_acc_foundation.py
python output/acc/src/build_rule_context.py
python output/acc/src/build_mvp_catalog.py
python output/acc/src/generate_acc_ids.py
python output/acc/src/validate_acc_foundation.py
```

获得测试模型后：

```powershell
python output/acc/src/precheck_ifc.py "D:/path/to/model.ifc"
python output/acc/src/ifc_inventory.py "D:/path/to/model.ifc"
```

重新执行已下载 GitHub 样例的预检、全量几何生成、属性/关系提取、IFC 属性与逆属性约束检查、规则缺失数据检查及回归测试：

```powershell
python output/acc/src/run_github_model_tests.py
```

样例原文件位于 `models/`，固定源提交、文件大小和 SHA-256 记录于各目录的 `source.json`；输出位于 `model_tests/`。原模型未添加或推断无障碍属性。

## 模型与法规可视化

2026-10-13 新增用户提供的 Duplex 和 `models/villa-patio/AC29_Villa-Patio_GRAPHISOFT-Sample.ifc`（均为 IFC2X3），已加入 Viewer、章节候选关联和本地检查入口。测试结果见 `model_tests/duplex/report.md` 与 `model_tests/villa-patio/report.md`。四个模型由 `models/catalog.json` 统一登记；原两个 IFC4 样例仍保留。

`viewer/` 提供 Three.js 构件—法规双向查询工具，支持模型点选、条文反向高亮、属性及原文证据查询、补充关联的导入导出。使用及覆盖范围见 `viewer/README.md`。本地从 `viewer/` 执行 `npm run serve`。

`precheck_ifc.py --geometry-sample 20` 默认只尝试前 20 个有表示的对象。
未覆盖全部几何对象、目标对象缺少表示、缺单位、缺属性或缺 Space Boundary 时返回 UNKNOWN。
预检报告的 PASS/FAIL 属于模型信息质量，不是法规合规结论。

## 规则执行约束

`acc_scope.json` 的类别用于安排工作；全部 `execution_ready` 均为 false。
映射全部为 `proposed_requires_review`。IFC4.3 读取保留为人工核验兼容性，当前 IDS 目标为 IFC4。
项目 `ACC_Accessibility` 属性集属于本项目约定，IBC 没有规定该属性集名称。

`Accessible=true` 是模型作者声明；执行数量子检查还需要独立的无障碍设计证据。
属性缺失与显式 false 会保留为不同信息。

`acc_engine.py` 接收 `facts_by_rule` 格式的已规范化事实 JSON。每条法规子检查需要：

空白录入模板为 `normalized_facts.template.json`，所有事实与审批均为空；请另存为新文件填写。

- 模型证据、适用性及其证据；
- 明确的设施/场地/租户范围、清单类型和完整性确认；
- 复核人、复核理由、APPROVED 结论及与源文本和当前规则定义匹配的 SHA-256；
- 数量检查所需的完整整数数据及无障碍/单元类型的独立证据。

无模型事实为 UNKNOWN；数据完整但缺复核为 MANUAL_REVIEW；有证据的排除为 NOT_APPLICABLE。
数量或连通性子检查的 PASS 仅覆盖 `result_scope`，不代表整个条款、设计或建筑通过。
原 8 项 MVP 没有门净宽检查。新增 `egress-door-clear-width` 根据 Chapter 10 的 1010.1.1 起草两个分支，并保留适用性/例外及净宽定义审核；无障碍专用尺寸与坡度等外部标准要求仍需逐条补齐。

```powershell
python output/acc/src/acc_engine.py "reviewed_facts.json" --output "output/acc/reviewed_subchecks.json"
```

请先阅读 `execution_report.md`、`foundation_validation_report.json` 和 `mapping_review_queue.json`。

## 2026-10-13 ACC 优化

新增 9 项版本化规则契约、IFC 观测层、法规驱动 runner、Why–What–Where 结果及 Compliance Panel。实施说明、审核流程和验证记录见 `optimization_report.md`。旧目录与旧状态保留；所有规则契约全局仍为 PENDING，只有针对当前源文本、契约、模型和事实的显式审核才能在某次运行中放行。

新增 JSON Schema 校验依赖：

```powershell
python -m pip install -r output/acc/requirements.compliance.txt --target output/acc/.python_deps
```

从项目根目录重建并验证：

```powershell
python output/acc/src/build_compliance_schemas.py
python output/acc/src/compliance_contract.py
python output/acc/viewer/export_compliance.py
python -m unittest discover -s output/acc/tests -v
```

执行明确选择的规则与版本（默认当前契约 v1.0.0，不满足审核门槛时输出 NOT CHECKABLE）：

```powershell
python output/acc/src/compliance_runner.py output/acc/models/ifcopenhouse/IfcOpenHouse_IFC4.ifc --model-id ifcopenhouse --rules egress-door-clear-width --output output/acc/door_check.json
```

`--facts reviewed_facts.json` 可接入审核事实。先另存 `compliance_facts.template.json`；填写后用 `prepare_compliance_facts.py --facts ... --output ...` 刷新哈希并重置为 PENDING，复核人再填写审核信息并手动改为 APPROVED。事实随后更改会使审核失效。模型更新后应重新提取、审核，并重导出 Viewer 几何；旧结果保存在 `runs/<model_id>/<run_id>.json`。
