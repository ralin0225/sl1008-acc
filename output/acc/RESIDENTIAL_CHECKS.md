# 二层单户住宅：六项 ACC 子检查

本分支在原有 9 项契约之外增加 6 项，契约总数为 15。新增契约均保持 `PENDING`，模型名称、形状或属性声明不会产生审批。Class 指本实现所需的数据处理方式，依据 Solihin & Eastman (2015)，不是法规文本永久不变的等级。

| rule_id | 检查 | Class | 核心要求 / 结果范围 |
|---|---|---:|---|
| `residential-riser-height` | 住宅楼梯踢面最大高度 | 1 | 已核验的梯段踢面高度 ≤ 7¾ in = **0.19685 m**；不包含逐级一致性、所有楼梯要求或最小踢面高度判定 |
| `residential-tread-depth` | 住宅矩形踏步最小深度 | 1 | 已核验的梯段踏步深度 ≥ 10 in = **0.254 m**；不覆盖扇形踏步 |
| `residential-stair-uniformity` | 梯段尺寸一致性 | 2 | 每个梯段的踢面高度、矩形踏步深度分别计算 max − min，均 ≤ ⅜ in = **0.009525 m** |
| `residential-escape-opening` | 应急逃生开口尺寸 | 2 | 矩形**净**开口：宽 ≥ 20 in、高 ≥ 24 in、底部离地 ≤ 44 in；一般净面积 ≥ 5.7 ft²，符合 grade-floor 定义的分支 ≥ 5 ft² |
| `residential-stair-headroom` | 楼梯连续净空 | 3 | 对完整、已核验的分片平面净空曲面求全域最小值，要求 ≥ 80 in = **2.032 m** |
| `residential-egress-continuity` | 疏散路径连续性 | 3 | 在完整、方向及通行性已核验的模型关系图中，每个范围内房间至少存在一条到已核验室外出口的路径 |

Class 1 使用显式尺寸；Class 2 派生差值或面积；Class 3 使用扩展曲面或有向拓扑图。六项中没有 Class 4。

## 适用条件与来源

首版只接收经审核的 `IBC2021`、`R-3`、二层、单户实验场景。IBC/IRC、司法辖区、建筑用途、条款例外和目标范围必须有明确审核依据；这不是一份普通独立住宅必然采用 IBC 的声明。IRC 规则尚未加入本项目。

楼梯尺寸使用项目内 1011.5.2 住宅例外 `ibc2021-ch10-list_item-0526`，不是一般楼梯 7 in / 11 in 限值。其他来源为 1011.5.4、1031.3.1–1031.3.3 及 grade-floor 例外、1011.3、1003.6。契约中的 `dsl_sources` 保存原子规则 ID、原文及哈希，`supporting_sources` 保存支持条款、页码和上下文。重建时读取当前来源，修改来源或原子记录会使原审核失效。

原英制数值精确换算，`Decimal` 运算，不把印刷毫米舍入值当作放宽。例如 197 mm 大于 7¾ in 的精确值；一般逃生开口最低面积是 0.529547328 m²。开口的最小宽和最小高同时达标，仍可能面积不足。

## 运行

在项目根目录执行（需要已有的本地 IfcOpenShell/jsonschema 依赖和输入 IFC）：

```powershell
python output/acc/src/build_compliance_schemas.py
python output/acc/src/compliance_contract.py
python output/acc/src/prepare_compliance_facts.py "D:/path/to/house.ifc" --model-id house --residential-only --output "D:/path/to/house.residential.facts.json"
```

生成器读取实际 IFC，绑定模型哈希，生成六项空白事实和 `PENDING` 审核，不补造模型事实。每项填写：

目录中的 `residential_facts.template.json` 是以现有 IfcOpenHouse IFC4 为身份来源生成的空白例子，所有适用性和审核字段仍为空或 PENDING。换模型时应运行上述命令重新生成，不能沿用旧模型哈希。

- `applicable` / `applicability_evidence`、`scope_id`、完整且真实的 `target_global_ids`、`inventory_complete`。
- `residential_profile`：`code_basis="IBC2021"`、`occupancy="R-3"`、`stories_above_grade=2`、`single_dwelling=true`、`evidence`；`exceptions_reviewed=true` 仅在有实际审核依据时填写。
- 本节以下列出的测量或拓扑证据。
- 由实际审核者检查规则、适用性、例外、目标、测量定义与数据，然后在当前源文本、契约、模型和事实哈希下记录审核；程序不提供“一键批准”。修改事实后旧审核失效。再次运行 prepare 可刷新哈希，但会将所有审核重新置为 `PENDING`。

审核完成后运行所需规则，可一次传入以下六个 ID：

```powershell
python output/acc/src/compliance_runner.py "D:/path/to/house.ifc" --model-id house --facts "D:/path/to/house.residential.facts.json" --rules residential-riser-height residential-tread-depth residential-stair-uniformity residential-escape-opening residential-stair-headroom residential-egress-continuity --output "D:/path/to/house.residential.report.json"
```

需要在 Viewer 中选择该模型时，仍需先按现有模型注册流程加入 `models/catalog.json` 并导出模型数据。现有已注册模型可执行 `python output/acc/viewer/export_compliance.py` 更新快照。Viewer 的规则下拉框、结果卡片和详情显示新增规则的 Class；报告也保存 `rule_class` 和 `class_basis`。运行中的 Python Viewer 服务需重启以加载新检查函数，然后刷新页面。

## 输入格式与实现范围

一条人工审核长度观测使用：

```json
{
  "value": 190,
  "unit": "mm",
  "source_global_id": "当前模型中该目标的实际 GlobalId",
  "method": "reviewed_manual_input",
  "valid": true,
  "semantics_verified": true,
  "evidence": "测量图、模型属性或测量记录的可核验出处"
}
```

长度支持 `m`、`mm`、`inch`、`ft`；只接收有限数值。零值只在允许的场合（如开口底部离地高度）有效。

### 1–2. 显式踢面高度 / 踏步深度

目标为 `IfcStairFlight`。提取器读取原生 `RiserHeight`、`TreadLength` 及项目单位，但测量含义仍需要 `measurement_semantics_verified` 和 `measurement_definition_evidence`。也可通过 `measurements` 对象按 GlobalId 提供以上人工观测；人工输入必须有目标绑定、测量定义和证据。原生观测不能声称与当前 IFC 不同的数值。踏步深度另需 `rectangular_treads_verified=true`。

### 3. 梯段尺寸一致性

每个检查实例只选择一个梯段。在 `flight_dimensions` 中提供 `riser_heights`、`tread_depths` 两个完整观测数组，以及 `riser_count`、`tread_count`、`inventory_complete`、`rectangular_treads_verified` 和 `evidence`。每个系列至少两个观测；数量必须和数组一致，也必须与 IFC 中有效的 `NumberOfRisers` / `NumberOfTreads` 一致。扇形踏步、特殊斜坡平台分支没有实现。声明的单一 RiserHeight 不能替代逐级测量数组。

### 4. 应急逃生开口尺寸

一个实例只选择一个 `IfcWindow` 或 `IfcDoor`。`opening_dimensions` 提供 `shape="rectangular"`、`normal_operation_verified`、`evidence`、`branch`（`general` / `grade_floor`）及 `branch_evidence`，另有 `net_width`、`net_height`、`sill_height` 三个观测。宽高是正常开启后的实际净开口，不能拿窗框外包尺寸代替。一般/grade-floor 分支需有定义及适用性依据，不能只按楼层名称选择。面积、宽、高、窗台逐项报告；不覆盖开口设置数量、位置和开启操作的完整合规性。

### 5. 楼梯连续净空

目标为一个 `IfcStairFlight`，`clearance_surface` 是**审核后的完整几何表示**：

- `representation="piecewise_planar_full_clearance"`；`unit` 明确。
- `x`、`y` 为从 0 开始严格递增的全域网格轴；末值与两个长度观测 `domain_length`、`domain_width` 精确一致。
- `nosing_z`、`overhead_z` 均为 `[len(x)][len(y)]` 的有限标高矩阵，允许相对基准下的负标高。
- 每个网格单元采用同一条从左下到右上的对角线三角化，两张曲面采用相同分区；在每个三角形上两者的差为线性函数，因此全域最小净空位于某个顶点。
- `source_global_id` 绑定梯段；`geometry_source_global_ids` 列出当前模型中的实际几何来源（梯段、梁、板等）。
- `full_surface_verified`、`scope_covers_required_headroom` 和 `evidence` 必须证明表示覆盖规定的全宽、踏步前缘参考及下部平台延伸等完整范围，并已处理例外。

此实现计算完整曲面的最小值，**尚不从任意 IFC 三角网格自动生成这两张曲面**。离散采样、包围盒、缺失网格单元或未经核验的覆盖范围返回 NOT CHECKABLE。曲面表示的真实性及完整性由证据审核建立，不能把几组采样点改一个名称当作全域曲面。

### 6. 疏散路径连续性

`route_graph` 包含 `nodes`、`edges`、`starts`、`exits`、`inventory_complete`、`evidence`、`exit_discharge_verified`、`exit_evidence`。

- 节点格式为 `{global_id, role}`；role 为 `room`、`circulation`、`stair`、`exit`。房间/交通节点必须是有实际 IFC 楼层归属的 `IfcSpace`，出口节点必须是经审核的 `IfcDoor`。
- 每条边包含 `from`、`to`、实际门/楼梯/坡道的 `via_global_ids`、布尔值 `traversable` 和 `bidirectional`，以及 `evidence`。显式不可通行的边不会加入可通行网络；不明确的状态返回 NOT CHECKABLE。
- 跨层边必须有实际楼梯/坡道及 `vertical_verified=true`。所有选中目标都必须出现在节点或边的来源中，所有房间节点都必须纳入 starts。
- 程序查找每个房间通向任一已审核出口的有向路径，返回路径证据或不可达房间。未找到路径不虚构障碍位置。

本实现不从几何自动判定门锁、火灾状态、路线宽度、无障碍性、行走距离或门—空间通行性。这些与完整住宅疏散合规分开处理。

## 验证

```powershell
python -m unittest discover -s output/acc/tests -v
cd output/acc/viewer
npm test
```

`test_residential.py` 只生成临时的合成 IFC，覆盖 Class、来源哈希、精确边界、通过/失败、缺数据、住宅例外、grade-floor 分支、净空内部低点、不完整曲面、跨层路径及审核失效。测试中的批准字段均显式标注 SYNTHETIC FIXTURE ONLY，不会写入实际模型的审核文件。

## 本地分支

项目根目录原来没有 Git，已建立 `main` 基线和 `feature/residential-six-checks` 分支。为了把整个项目发布到同一个 GitHub 仓库，两个分支都将 Viewer 源代码和展示快照作为普通目录纳入根仓库，不再依赖没有来源地址的 gitlink。`main` 保留九项检查及对应界面，功能分支包含十五项检查及 Class 展示。本地 `output/acc/viewer/.git` 与原有工作仍保留在磁盘，但其 Git/托管元数据不上传；推送和分支比较统一从项目根目录进行。依赖、IFC/PDF 原件和运行历史仍保留在本地。
