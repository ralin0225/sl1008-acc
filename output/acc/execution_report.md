# ACC 基础阶段执行报告

> 2026-10-13 状态说明：本文保留为基础阶段历史记录；“没有 IFC / 未开发 Viewer / 门宽全部待外部标准”等描述已被后续工作更新。当前实现、范围与验证见 `README.md` 和 `optimization_report.md`。

本阶段沿用已完成的法规结构及 RDF 成果，没有重新执行第 1–12 步。
原始 PDF、截取 PDF 和既有结构化成果均未作为写入目标。

## 完成内容

| 阶段 | 输入 | 输出 | 工具与验证 | AI Token |
|---|---|---|---|---|
| 范围筛选 | semantic_validated、dsl_rules、manual_review_queue | acc_scope、computable_rules、deferred_rules | Python 确定性筛选；462 条唯一分配；证据文本 SHA-256 校验 | 代码与判断由 AI 辅助；运行脚本不调用 LLM |
| IFC Profile | 法规证据与项目技术方向 | ifc_profile、ifc_property_conventions | Python；缺失信息为 UNKNOWN；IFC4 主目标 | AI 辅助拟定，项目约定待模型作者确认 |
| IFC 映射 | 11 个概念及条款证据 | mapping JSON/TTL、mapping_review_queue | RDFLib 解析；IfcOpenShell 核对 IFC4 实体；93 条三元组 | AI 辅助拟定，11 项均待复核 |
| IDS | Profile 与映射 | ibc_accessibility.ids、ids_traceability、ids_validation_report | IfcTester 0.9.0；6 项；Schema、回读和 source_node_id 校验 | AI 辅助编写；生成/校验不调用 LLM |
| 预检与 MVP | 数据约定与条款原文 | src 下的预检器、清单提取器、8 项规则目录及子检查引擎 | IfcOpenShell、IfcTester、Python unittest；25 项合成测试通过 | AI 辅助实现；测试不调用 LLM |
| 条款上下文 | 结构导航及语义引用 | rule_review_context.json | 确定性补充数字层级、同前缀引用范围和例外；289 个条款上下文 | AI 辅助编写；运行不调用 LLM |

精确 AI Token 数量在此运行环境中无法按文件或阶段取得，故没有填写推测值。

## 范围筛选统计

| 类别 | 条数 |
|---|---:|
| directly_computable | 45 |
| computable_with_ifc_geometry | 7 |
| computable_with_topology | 45 |
| requires_external_standard | 43 |
| manual_review | 234 |
| non_computable | 88 |
| 合计 | 462 |

这是关键词与原有复核标记驱动的保守分类，并非法规解释认证。
类别与可执行状态分开保存，全部原子规则仍为候选状态。
现有 86 个复杂语义对象的复核要求继续保留；它们与 234 条 manual_review 原子规则不是同一计数单位。

## MVP 范围

5 项数量子检查：单个停车设施的无障碍车位数量、厢式无障碍车位数量、公共入口比例、单个租户无障碍入口数量、经过复核的场地 Type A 单元数量。
另有场地连通性子检查、Required Property Set 和空间用途信息检查。
停车表直接读取结构化 Table 1106.2，并保留表格原页、bbox、来源行和哈希。
入口、单元数量、例外与适用范围均需要来源绑定的显式复核记录。

## 修复与限制

- IfcTester 0.9.0 的 `Specification.parse` 会遗漏 XML 的 identifier。新增 `ids_support.py` 从 XML 对照恢复标识，回归测试确认法规关联不丢失。
- IfcOpenShell 缺少长度单位时可能返回默认比例 1。预检器先检查显式 LENGTHUNIT，避免默认成米。
- IDS 无匹配对象不会自动变成 ACC PASS；缺失数据与未知适用范围均返回 UNKNOWN。
- 声明属性不会自动成为设计验证结论；空间名称不用于推断停车用途。
- 门净宽、坡度的规范阈值延期，需 ICC A117.1；几何采样无法证明未检查对象有效。
- IFC4.3、IfcZone 单元/停车聚合、墙—开口—门关联及垂直路线仍待后续模型驱动验证。
- 预检结果和子检查结果均不代表全条款合规。未开发完整 Web Viewer。

## 当前阻碍与下一步

项目目录中没有用户测试 IFC。实际 IDS、模型检查、BCF Issue、IFC→GLB 和三维验证尚未执行。
需要测试 IFC 及模型作者对属性/分类约定的确认后，才能验证模型映射、几何与拓扑。
当前运行与复现命令见 README.md；验证及输入/输出哈希见 foundation_validation_report.json 与 manifest.json。
