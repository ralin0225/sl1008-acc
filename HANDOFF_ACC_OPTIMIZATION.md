# LLM + IFC 自动合规检查：优化计划交接

更新日期：2026-10-13（Europe/Berlin）  
项目目录：`D:\00_SL1008`

## 本次交接的任务边界

本文件记录用户认可方向下的更改计划，供下一个对话实施。本轮只创建此 Markdown，没有修改检查器、法规数据或 Viewer。下一轮先核对已有实现，再按计划增量修改；不要将本计划中的功能描述当作已完成成果。

用户提出的核心参考是 Kestrel 的检查逻辑与结果反馈：法规驱动、Python 确定性判定、三种可见结果状态、Why–What–Where 追溯及层级式 Compliance Panel。这里是对用户提供分析的项目化落实，不代表对 Kestrel 产品实现的独立验证。

## 项目目标与核心架构

形成能够连接「法规条款—检查逻辑—BIM 对象—检查结果」的学生项目：

```text
Regulation PDF
→ Structured Rules / RDF
→ Rule Selection
→ Applicability + Required IFC Data
→ Target Elements + IFCOpenShell Extraction
→ Python Deterministic Check
→ PASS / FAIL / NOT CHECKABLE
→ Regulation + Reason + Element
→ 3D Highlight / Compliance Report
```

LLM 用于法规理解、结构化规则、IFC 映射建议、疑难项分析和解释草稿；生产检查的 Pass/Fail 由版本化 Python 函数决定。整改建议可展示，IFC 修改保留为用户手动操作后重新检查。

## 已有成果与本轮检查到的实际目录

### 法规输入与结构化成果

- 原始 IBC：`D:\00_SL1008\2021_International_Building_Code.pdf`
- Chapter 11 摘录：`D:\00_SL1008\IBE2021_11Accessibility.pdf`，原 PDF 实际第 356–373 页，共 18 页。
- Chapter 10 摘录：`D:\00_SL1008\IBC2021_10MeansOfEngress.pdf`，原 PDF 实际第 304–355 页，共 52 页。保留现有文件拼写。
- Chapter 11 产物：`D:\00_SL1008\output\ibe_accessibility_structure`
- Chapter 10 产物：`D:\00_SL1008\output\ibc_means_of_egress_structure`
- 处理脚本：根目录的 `extract_ibc_accessibility.py`、`build_semantic_rdf.py`、`process_ibc_chapter.py`。

Chapter 11 现有报告记录：305 个结构节点、289 个语义候选、462 条原子规则、86 个复杂语义对象待复核。现有 SHACL、证据字符串检查和 OWL-RL 检查通过，但这些不证明条款解释、条件作用域或建筑合规判定正确。

### 已有 ACC 基础

目录：`D:\00_SL1008\output\acc`

开始实施前读取：

- `README.md`：当前运行方法及限制。
- `execution_report.md`：基础阶段记录，部分后续状态已变化，应与最新 README 和实际文件核对。
- `acc_scope.json`、`computable_rules.json`、`deferred_rules.json`。
- `mvp_rule_catalog.json`、`rule_review_context.json`。
- `ibc_ifc_mapping.json`、`ifc_profile.json`、`ifc_property_conventions.json`。
- `ibc_accessibility.ids`、`ids_validation_report.json`。
- `src/acc_engine.py`、`src/precheck_ifc.py`、`src/ifc_inventory.py`。
- `tests/`、`model_tests/report.md`。

现有 README 记录：462 条原子规则中 97 条是可计算候选，365 条延期；全部执行就绪标记仍为 false，映射待审核。MVP 包含 5 项数量子检查、1 项连通性子检查和 2 项项目信息检查，现有结果包括 UNKNOWN、MANUAL_REVIEW、NOT_APPLICABLE。

现有样例 IFC 已位于：

- `D:\00_SL1008\output\acc\models\ifcopenhouse\IfcOpenHouse_IFC4.ifc`
- `D:\00_SL1008\output\acc\models\buildingsmart-simple-scene\Building-Architecture_IFC4.ifc`

不能沿用早期 handoff 中“没有 IFC 文件”的说法。样例存在不代表已有用户项目模型，也不代表具备完整无障碍检查数据。

### 已有三维查询 Viewer

目录：`D:\00_SL1008\output\acc\viewer`

先读 `README.md`、`package.json`，检查 `dist/`、`export_data.py`、`export_chapters.py` 和 `tests/`。

现有 Viewer 提供构件—法规双向查询、Chapter 10/11 切换、候选关联、高亮、法规来源查看、关联导入导出及中英文切换。README 记录两章共 1,499 个结构条目、两个模型共 70 个可查询对象和 51 个成功生成几何的对象。这些是已有文档记录，下一轮核对数据后再用于新报告。

现有候选关联和用户补充关联不能当作已确认的法规适用性或 ACC 结果。复用 Viewer，增加检查执行与结果面板；保留现有语言、章节过滤、模型定位、失败几何对象和关联功能。

## 更改计划

### 1. 建立审核后的可执行规则契约

将语义候选与可执行规则分开。为每条首批规则补齐以下字段：

- `rule_id`、`rule_version`、法规章节及 `source_node_id`。
- 原文、源 PDF、摘录页序、原 PDF 页序、bbox 和源文本哈希。
- `applicability` 与例外处理，包括建筑/设施/租户/楼层的检查范围。
- `required_ifc_data`：实体、分类、属性、单位、关系和几何需求。
- `target_selector`：明确目标集合及清单完整性要求。
- `check_function`、参数、比较符、阈值来源、容差依据。
- `result_scope`：子检查范围，避免用一个子检查代表整条款通过。
- `review_status`、审核证据、测试用例及 `execution_ready`。

首批只启用字段完整、依据明确且通过审核的规则。LLM 可以起草，审批和哈希绑定沿用已有机制。未经审核的映射保留候选状态。

### 2. 增加独立的 IFC 数据需求与提取层

每个数据项记录获取方式：原生 IFC 属性、项目 Pset、分类、空间关系、几何派生或人工输入。定义数据类型、单位、来源 GlobalId、有效性和缺失原因。

特别注意：`IfcDoor.OverallWidth` 与法规要求的净通行宽度不能默认等价；包围盒宽度同样不能直接代替净宽。需明确几何算法或经审核的项目属性定义。空间名称及 `Accessible=true` 声明不自动证明空间用途或设计合规。

此前示例中的 900 mm 只是展示阈值。正式检查从适用条款取得要求值。Chapter 10 已有门净宽条款 1010.1.1 候选证据，可核对是否适用于首批规则；依赖 ICC A117.1 的要求按具体条款识别缺口，不能使用无出处阈值，也不能将所有门宽检查笼统判为缺少外部标准。

IDS 用于信息要求检查，几何和路线验证由对应检查函数完成。

### 3. 固定法规驱动的执行顺序

```text
选定规则及版本
→ 确定是否适用并检查例外
→ 提取目标对象及必需数据
→ 检查数据有效性与目标清单完整性
→ 计算实际值
→ Python 函数比较
→ 保存结果、证据和运行记录
```

适用性未知、数据不完整、几何失效、外部依据未解析及执行错误都有明确结果；不可静默忽略，也不可因没有匹配对象而判为 PASS。

### 4. 统一展示状态并保留内部原因

界面三种可见状态：`PASS / FAIL / NOT CHECKABLE`。

兼容现有引擎，不直接删除旧状态：

| 内部状态 | 界面表示 | 统计处理 |
|---|---|---|
| PASS | PASS | 计入已完成判定 |
| FAIL | FAIL | 计入已完成判定 |
| UNKNOWN | NOT CHECKABLE | 附缺数据、无效几何或适用性未知原因 |
| MANUAL_REVIEW | NOT CHECKABLE | 附待审核原因 |
| 执行错误 | NOT CHECKABLE | 明确 CHECK_ERROR，不冒充数据不足 |
| NOT_APPLICABLE | 不适用/排除项 | 单独展示，不计入合规率分母 |

建议原因码：`MISSING_DATA`、`INVALID_DATA`、`INVALID_GEOMETRY`、`UNKNOWN_APPLICABILITY`、`INCOMPLETE_TARGET_SET`、`UNRESOLVED_REFERENCE`、`REQUIRES_MANUAL_REVIEW`、`CHECK_ERROR`。

覆盖率与通过率分开：

- 完成判定率 = `(PASS + FAIL) / (PASS + FAIL + NOT CHECKABLE)`。
- 已判定检查通过率 = `PASS / (PASS + FAIL)`。
- 分母为 0 时显示不可计算，不显示 100%。
- 一条规则作用于多个构件时，规则数与检查实例数分开统计。

### 5. 构建 Why–What–Where 结果契约

每个结果对象保存：

- **Why**：规则与版本、条款原文、页码、哈希、条件和例外依据。
- **What**：检查函数、要求值、实际值、单位、比较符、容差、结论和原因。
- **Where**：模型 ID/哈希、GlobalId 列表、IFC 类型、名称、楼层、位置及可选相机视点。
- **Run**：run ID、时间、检查器版本、规则版本、输入事实证据、审核状态。

GlobalId 与模型身份共同用于定位。STEP 编号仅作辅助，不能作为跨导出版本的唯一关联键。聚合检查绑定对象集合和范围；无法归属单个构件时，展示设施或目标集合而非虚构一个违规构件。

解释根据实际计算结果和源法规生成。AI 改写解释时不能增加新的数值、要求或适用结论。

### 6. 明确 RDF 与 ACC 的职责

文档图保存结构、引用和 PDF 来源；语义图保存规则、条件、例外及 IFC 映射。Python 执行器读取经过确认的规则配置，调用函数注册表。

SHACL 验证规则/结果数据结构，OWL-RL 检查有限本体一致性；这些检查不能代替实际模型 ACC，也不能证明候选 NLP 解析语义正确。现有规则自报置信度不视为经过校准的准确率。

### 7. 在已有 Viewer 中增加 Compliance Panel

三个层级：

1. 总览：规则数、检查实例数、PASS、FAIL、NOT CHECKABLE、不适用项和覆盖率。
2. 主题：Accessibility、Egress；Fire Safety 仅在有相应规则输入时加入。
3. 详情：Rule ID、Why–What–Where、要求/实际值、GlobalId、解释、整改建议和证据链接。

交互要求：点击检查结果定位和高亮对应对象；点击构件查看它的全部结果；支持按章节、规则、状态和楼层过滤。沿用现有候选法规关联视图，同时明确区分候选关联与实际检查结果。

颜色建议：PASS 绿色、FAIL 红色、NOT CHECKABLE 黄色。多个规则涉及同一对象时，可按选中规则着色或显示最高严重状态，并保留明细；缺少几何的对象仍可查元数据和结果。

路线规则可绘制起点、终点、路径和阻断位置。若算法只知道“未找到路径”，而没有阻断定位证据，界面不能虚构具体阻断点。

### 8. 整改与复查闭环

输出建议及后续 BCF issue：法规依据、问题原因、相关构件、测量值、视点。建议值必须有法规出处。用户手动修改 IFC 后重新运行，按模型版本保留结果历史。

不实现自动 IFC 修改或 generative design。导出报告与 BCF 时保留 NOT CHECKABLE 原因，不把它们写成确定违规。

### 9. 用测试与证据控制首批规则范围

首批选择 5–10 条规则，优先复用现有数量及信息检查，再按模型数据增加明确尺寸检查与路线子检查。复用两个 IFC 样例进行提取和显示验证；缺少规范数据的样例应正确返回 NOT CHECKABLE。

每个可执行规则覆盖：PASS、FAIL、缺数据、不适用；数值规则增加边界、单位及容差测试；例外规则测试适用与排除；路线规则测试不完整拓扑、方向性及确定不可达。

合成事实/测试模型要标为 fixture，不能作为真实建筑合规证据。Precision/Recall 仅在存在独立人工标注的参考答案时计算。

## 建议下一轮的执行顺序

1. 读取以上现有 README、代码、规则目录、模型测试和 Viewer 测试；识别已实现部分与实际差距。
2. 定义规则和 Why–What–Where 结果 Schema，增加状态兼容转换与统计口径。
3. 为首批规则绑定 IFC 数据需求、目标筛选和事实提取入口，沿用审核机制。
4. 将现有确定性函数接入法规驱动 runner，保存版本化运行结果。
5. 在现有 Viewer 增加 Compliance Panel、双向定位、过滤、着色和证据详情。
6. 运行 Python 和前端回归测试，完成有证据的样例演示；后续再扩展 BCF。
7. 输出简短报告：每项变更、验证结果、AI 使用环节、待审核项及现有覆盖范围。

## 验收标准

- 从法规规则出发选择并执行检查。
- 每个结果能回溯到源条款、检查逻辑和模型对象/对象集合。
- 数据不足与待审核均明确呈现为 NOT CHECKABLE；不适用独立记录。
- 相同的规则版本和事实输入得到可重复结果。
- 净宽、几何尺寸、分类及声明属性的语义区别可追溯。
- 首批每条执行规则具备状态与边界测试。
- Compliance Panel 统计不把未检查、不适用或未知当作通过。
- 原有语言切换、章节选择、法规查询及几何失败信息继续可用。
- 用户可完成“发现问题→定位→解释→查依据→手动修复→重新检查”的闭环。

## 工作约定

- 现有代码和产物以当前文件为准；早期报告存在过时描述时，明确记录差异。
- 尽量在 `D:\00_SL1008\output\acc` 现有实现上增量扩展。
- 保留原法规数据与证据；需要修复解析时，生成可追溯修订并记录差异。
- 未收到部署请求时，交付本地可审查版本；不自动发布或修改远程站点。
- 记录 AI 辅助的位置：规则语义、映射建议、代码编写、疑难诊断或解释改写。
- Python/IFC/RDF 的本地计算不调用模型；AI 编写代码和读取工具输出仍消耗对话额度。精确逐步 Token 数无法取得时注明不可测，不填写估计百分比冒充实测。
