# ACC 优化实施报告

日期：2026-10-13（Europe/Berlin）。范围：本地、增量扩展 `output/acc`；未发布远程站点。

## 本次实现

| 改动 | 实现与效果 |
|---|---|
| 可执行契约 | `executable_rule_contracts.json`：9 项 v1.0.0 子检查，绑定条文、PDF 页码/bbox、原文哈希、上下文/例外、数据需求、目标选择、函数、阈值来源、容差及审核。全局仍为 PENDING / execution_ready=false；运行中只接受针对当前契约、源文本、模型及事实的显式 APPROVED 审核。 |
| 数据需求层 | `src/ifc_requirements.py`：区分原生属性、发生实例 Pset、分类关系、空间边界关系、位置及人工测量；保留类型、单位、GlobalId、有效性和缺失原因。原生 OverallWidth 独立保存并明确不能代替净宽。分类及 Accessible 声明不自动证明用途或合规。 |
| 法规驱动 runner | `src/compliance_runner.py`：规则选择 → 适用性/例外审核 → 模型指纹 → 目标清单 → 数据有效性 → 函数注册表 → 结果与证据。数量必须对应审核后的 GlobalId 集合。路线节点绑定 IFC GlobalId，仍只检查审核图的连通性。 |
| 状态与统计 | 保留 PASS、FAIL、UNKNOWN、MANUAL_REVIEW、NOT_APPLICABLE；界面统一前三种可见结论 PASS / FAIL / NOT CHECKABLE，排除项独立。记录 8 类原因码，执行错误单独标记 CHECK_ERROR。覆盖率与已判定通过率使用不同分母；零分母为 null/不可计算。 |
| Why–What–Where | 每个实例绑定源条款/规则版本、函数/要求/实际值/单位/容差/原因、模型哈希/GlobalId 集合/元数据和运行/审核/输入证据。聚合检查绑定整个目标集合；候选目标标记 candidate_unreviewed，不声称为违规对象。 |
| 结构校验 | `schemas/` 下两份 JSON Schema，加载契约、保存结果时实际执行校验，并核对结果身份与统计。JSON Schema、原有 SHACL 与 OWL-RL 各自只验证结构或有限一致性，不能证明法规解释或建筑合规。原 RDF 图保持为法规文档和语义证据来源。 |
| Compliance Panel | `viewer/dist/compliance*.js`：总览、Accessibility/Egress 主题、Why–What–Where 详情；章节、规则、状态、主题、楼层和当前构件筛选；双向定位；按选中结果或已审核结果最高严重状态着色。保留中英切换、候选关联、原文/PDF、几何失败及关联导入导出。 |
| 复查与历史 | `viewer/serve.py` 仅监听本机，浏览器可选择规则、载入审核事实、调用 Python、导出 JSON 报告与查看历史。`runs/<model_id>/<run_id>.json` 保存各次运行和模型版本。旧模型版本可保留和导出，不能与当前几何混合定位。 |
| 旧引擎修复 | 无效连通图的 reason 曾重复传给 outcome 而抛异常，已修复；新 runner 对缺数据、无效数据及函数/提取异常分别给出明确结果。 |

## 首批范围与门净宽

沿用 5 项数量、1 项连通性、2 项项目信息检查；新增 `egress-door-clear-width`。信息检查的 PASS 只证明项目字段存在且类型/枚举有效，Accessible=false 也可以是有效信息；不证明无障碍设计合规。

门宽依据为 IBC 2021 1010.1.1：Chapter 10 摘录第 13 页、原 PDF 第 316 页。一般 32 inch 与 I-2 运床门 41½ inch 起草为两个待审核分支；使用 inch 精确换算为 0.8128 m 和 1.0541 m，保留正文所印的四舍五入 mm 数值。单位解释也属于契约审核范围，不允许按这两个值套用所有门。

审核需明确适用性、例外、用途、门型、双扇门情况下的一扇净宽及量测定义。单项结论仅覆盖净宽，不涵盖容量、净高、开门方式、无障碍专用尺寸或整条款合规。未设 900 mm 展示阈值；无额外法规容差。几何净宽算法尚未实现，使用经审核的项目净宽属性或有独立证据的人工净宽测量。

## 审核事实准备与运行

从项目根目录：

```powershell
python output/acc/src/prepare_compliance_facts.py output/acc/models/ifcopenhouse/IfcOpenHouse_IFC4.ifc --model-id ifcopenhouse --output output/acc/my_facts.json
```

填写 `facts_by_rule` 中的适用性及依据、设施/场地/租户范围、完整目标 GlobalId 清单与事实。数量还需 `accessible_global_ids`、对应整数及独立设计证据；图节点使用 IFC GlobalId；维度检查每个实例只绑定一扇门。一条规则可用事实对象数组表达多个设施或门。

填写后刷新输入哈希（不会审批，会重置为 PENDING）：

```powershell
python output/acc/src/prepare_compliance_facts.py output/acc/models/ifcopenhouse/IfcOpenHouse_IFC4.ifc --model-id ifcopenhouse --facts output/acc/my_facts.json --output output/acc/my_facts.pending.json
```

复核人核验法规上下文、例外、测量及目标完整性后填写 reviewer/rationale 并手动设置 resolution=APPROVED，再另存审核版本。只更改 scope_review 不影响 facts_sha256；更改任何事实、模型或契约都需重新审核。这里沿用项目的显式审核记录机制，未增加电子签名或身份认证。

```powershell
python output/acc/src/compliance_runner.py output/acc/models/ifcopenhouse/IfcOpenHouse_IFC4.ifc --model-id ifcopenhouse --facts output/acc/my_facts.reviewed.json --rules egress-door-clear-width --output output/acc/my_report.json
```

浏览器可载入同一文件再执行。默认重导出读取 `reviewed_facts/<model_id>.json`；该目录没有审核文件时不推断适用性。重建契约或更改 Python 后需重启 Viewer 服务。

IFC 手动修改后：重新预检/提取，更新模型证据与审核，运行检查，重导出 Viewer 几何（`viewer/export_data.py` 保留章节合并并更新报告）。如果 IFC 文件变化但几何数据未重导出，Viewer 会拒绝新模型版本的结果叠加。

## 验证证据

- 35 项 Python unittest 通过：原有 25 项 + 新增 10 项测试方法；每条首批规则均在 fixture 下测试 PASS、FAIL、缺数据和不适用。另覆盖审批过期、模型不匹配、数量与对象清单不一致、门宽边界/单位/零容差、图方向性/不完整拓扑/无效边/不可达、未解析引用、几何及提取错误、重复输入与多实例统计。日志：`optimization_python_tests.log`。
- 18 项 Node 测试通过：原有 12 项 + 6 项新增测试，覆盖源文本/模型/GUID 验证、覆盖率/通过率/排除项/零分母、多种过滤、候选关联与结果区分、严重状态着色及中英文标签。JavaScript 语法检查通过。
- 两个真实 IFC 样例各执行 9 项检查，均为 NOT CHECKABLE；实际缺少适用性及审核事实，没有法规 PASS/FAIL。初始覆盖率 0%，已判定通过率不可计算。报告是真实样例的信息缺口证据，不是建筑合规结论。
- 前端已有数据重新核对：1,499 条结构条目；两个模型 70 个对象、51 个成功几何；IfcOpenHouse 两个墙体几何失败对象继续保留。源 PDF 和 IFC 原文件没有写入修改。
- 浏览器验证：模型切换、门 GlobalId 的反查与结果定位、Why–What–Where 及 PDF 页码、中英界面、规则筛选、Python 重跑/运行历史、候选法规视图、章节过滤和无几何墙体元数据。默认窄屏及 1440×1000 桌面布局检查。浏览器记录见 `optimization_validation.json`（最终实测记录）。

所有测试审批、合成事实及临时 IFC 均明确标为 fixture；不产生真实建筑审批，不计算无独立人工标注依据的 Precision/Recall。可重复性指相同规则、检查器和事实得到相同结论/计算；run ID 和时间每次新建。

## 待审核与后续范围

9 项契约及原映射仍需业务/法规审核；没有将 AI 编写或合成测试等同于审批。现有 97/365 候选/延期分类没有被改写为可执行认证。

BCF 导出按 handoff 的后续阶段保留；本次完成 JSON 证据报告、手动修复与重新检查入口。没有自动 IFC 修改、generative design、未证实的路线阻断点或路线几何；相机视点字段为可选 null。Fire Safety 尚无规则输入，未创建该主题。ICC A117.1 等外部标准仍需按具体检查识别和补齐。历史跨模型版本暂由 JSON 导出审查，不能用当前几何展示旧版本。

基础阶段 `execution_report.md` 中“没有 IFC”“未开发 Viewer”“全部门宽待外部标准”的描述属于旧阶段；后来的样例和 Viewer 已存在，本报告及最新 README 为当前状态。

AI 辅助用于规则契约/IFC 映射建议、代码编写、测试设计及疑难诊断。Python、IFC、Schema 与 Node 本地运行均不调用 LLM。精确按步骤或文件 Token 数不可测，未填写估计百分比。
