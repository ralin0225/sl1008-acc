# IFC / IBC 法规双向查询工具

Three.js 0.186.1 可视化四个本地测试模型：两个原有 IFC4 样例、Duplex 和 Villa Patio（后两者为 IFC2X3）。几何通过 IfcOpenShell 从原 IFC 导出，以 GlobalId/GUID 保持构件身份。无需 CDN，Three.js 和 OrbitControls 随应用提供。

2026-10-13 加入 `Villa Patio · GRAPHISOFT 样例`：2,210 个可查询对象、2,153 个成功几何。所有 2,153 个有 Representation 的对象均已尝试且成功，另 57 个对象仅保留元数据。包含 24 扇门、3 个楼层；没有 IfcSpace 或 IfcRelSpaceBoundary。IFC2X3 格式、适用性/分类及审核事实缺口继续保留，9 项 ACC 均为 NOT CHECKABLE。原文件未修改，来源指纹及测试报告位于 `../models/villa-patio/` 和 `../model_tests/villa-patio/`。四个模型共 2,576 个可查询对象、2,423 个成功几何。

2026-10-13 加入 `Duplex · 双拼住宅`：296 个可查询对象、219 个成功几何；67 个几何生成失败对象保留原错误与元数据。全量尝试 286 个有 Representation 的对象。模型含 14 扇门、21 个空间、4 个楼层及 265 个空间边界关系；边界关系存在不代表路线通行已验证。IFC2X3 与当前 IFC4 审核目标不符，预检 schema 项显示 FAIL（模型信息/格式检查，不是法规违规），9 项 ACC 结果均为 NOT CHECKABLE。加入 Villa Patio 前的三个模型共 366 个对象和 270 个成功几何。

统一模型目录为 `../models/catalog.json`，几何导出、两个法规章节关联和 API 检查入口共用此目录。Duplex 的原文件副本及 SHA-256 位于 `../models/duplex/`，预检/提取报告位于 `../model_tests/duplex/`；未转换或补写 IFC 属性。测试说明见该目录的 `report.md`。

2026-10-13 新增 Compliance Panel。右侧“合规检查 / 候选法规关联”分别展示实际运行结果与待审核候选关联；共享章节选择。检查结果支持规则、状态、主题、楼层和当前构件过滤，显示规则数与实例数、覆盖率和已判定通过率；不适用独立统计，零分母显示不可计算。点击结果打开 Why–What–Where 并定位对象；点击构件查看其全部结果。多结果对象按 FAIL、NOT CHECKABLE、PASS 排序着色；选中结果时按该结果着色。候选目标默认不按已审核合规结果着色。

“执行所选规则”通过本地 `serve.py` 调用 Python runner，可载入审核事实 JSON，并核验模型/规则/事实哈希。“运行历史”保留各模型版本结果；不匹配当前几何版本的报告会拒绝叠加。“导出检查报告”包含全部当前报告实例和未能检查原因。两个真实样例的初始 9 项结果均为 NOT CHECKABLE。项目属性信息检查仅说明信息完整性，不证明 IBC 合规。

## 使用

右上角“中文 / English”可切换全部界面语言；法规详情窗口也提供切换按钮。选择保存在当前浏览器，下次打开或刷新会恢复。切换保留当前模型、构件/法规选择、搜索和高亮；法规原文、表格证据、IFC 名称、GUID 及属性原值不作翻译。

1. 从顶部选择 buildingSMART 建筑样例、IfcOpenHouse 住宅样例、Duplex 双拼住宅或 Villa Patio GRAPHISOFT 样例。
   右侧“选择 IBC 章节”可分别勾选 Chapter 10 Means of Egress 和 Chapter 11 Accessibility；支持单章、两章同时查看及取消全部选择。选择保存在当前浏览器。章节筛选同时影响搜索、构件相关条目、反向高亮及关联数量；不会删除用户补充关联。
2. 单击三维构件或左侧列表，右侧显示相关候选法规、例外和引用上下文。可搜索 GUID、类型、条款编号或原文。
3. 点击法规卡片，高亮所有候选关联构件；支持定位、隔离关联和透视。无几何对象仍显示在构件列表并可查属性。
4. 点击“原文 / 关联”查看完整条文、来源页码、SHA-256、数量表格、相关对象及关联依据；PDF 链接定位第 11 章摘录页，并显示原书页码。
5. 选择一个构件后，可在任何法规详情中“关联到当前构件”。补充关联保存在当前浏览器；导出 JSON 用于备份，导入时核对模型 SHA-256、构件 GUID 和法规编号。补充关联不会修改 IFC 或审批法律适用性。

## 本地启动

从本目录执行：

```powershell
npm run serve
```

打开 http://127.0.0.1:8765/。浏览器必须支持 WebGL，不能直接双击 index.html 使用 file:// 协议。

`npm run serve` 现在启动仅监听 127.0.0.1 的 Python API 与静态页面；修改 Python 实现后需重启服务。纯静态 HTTP 服务仍能查询已导出的报告，但不能重新执行。自定义端口：`python serve.py --port 8766`。

## 数据与适用范围

- 完整纳入现有结构化 IBC 2021 第 11 章的 305 个证据条目，包括 226 个 provision、41 个 exception、22 个 list_item，以及章节和说明；462 条 DSL 是规则表达数量，并非 462 个独立法规条款。
- 已新增 IBC 2021 第 10 章 Means of Egress 的 1,194 个结构化条目，与第 11 章共 1,499 条。每条包含章节身份、源 PDF 文件和摘录/原始 PDF 页序；1010.1.1 门净宽的来源为 Chapter 10 摘录第 13 页、原始 PDF 第 316 页。
- 两章之间能够确定目标的引用仅用于导航；其他章节和 ICC A117.1 等外部标准仍不在当前结构化范围内。本工具没有声称覆盖所有实际适用条文。
- Chapter 10 的门、楼梯、坡道、空间等 IFC 类型关联为 `proposed_requires_review`，不决定用途、占用类型、例外适用性或合规结果；原模型几何与检查状态保留。
- 直接关联使用现有 11 项 proposed_requires_review 映射，并保留子条款、上位条款、例外、引用及建筑范围上下文。空间用途未核验，不凭房间名称决定停车、卫生间或住宅类型。
- 所有自动关联与用户补充关联仍需审核；UNKNOWN 模型测试和候选关系不表示法规合规。
- 四个模型共 2,576 个可查询对象、2,423 个成功几何。IfcOpenHouse 两面墙及 Duplex 的 67 个对象几何生成失败，元数据和错误仍可查询，没有生成替代形状；Villa Patio 没有几何生成失败。
- 默认视角对准建筑，避免场地及定位辅助物件使建筑过小。“全景”显示整个模型。

来源、模型指纹、原始预检结果和几何失败信息随 data/*.json 提供。buildingSMART 来源为 CC BY 4.0；IfcOpenHouse 源快照无独立许可证声明。Three.js 许可证位于 dist/vendor/LICENSE。

## 更新与验证

```powershell
python export_data.py
python export_compliance.py
npm test
node --check dist/app.js
```

export_data.py 读取现有 models/、model_tests/、ibc_ifc_mapping.json、rule_review_context.json 及结构化法规，重新生成 dist/data/。运行环境使用上一阶段已安装的 output/acc/.python_deps。前端库安装记录在 package-lock.json；更新 Three.js 后需复制 three.module.js、three.core.js、OrbitControls.js 与 LICENSE 到 dist/vendor/。

仅更新章节及候选关联而保留已导出的模型几何，可运行 `python export_chapters.py`。Chapter 10 输入为 `output/ibc_means_of_egress_structure/`；章节专用候选映射及导出检查记录保存在 `chapter10_mapping.json`、`chapter_export_report.json`。

2026-10-10 章节更新验证：12 个 Node 测试全部通过，覆盖章节交集/空选择、双向关联、跨章节人工关联保留、各章 PDF 及门净宽出处、中英界面和旧有几何/关联数据。当前轮次原生浏览器验证因无法可靠识别当前浏览器 URL 被停止；本轮未宣称完成浏览器交互验证。前文浏览器验证记录属于 Chapter 11 原有版本。

自动测试覆盖所有实际数据关联的双向一致性、门条款的 GUID、真实几何与失败对象保留、全部法规检索、表格证据及导入哈希校验。

ACC 扩展验证与审核事实准备步骤见 `../optimization_report.md`。`export_data.py` 会保留 Chapter 10 合并步骤，并在存在规则契约时更新检查快照；`export_compliance.py` 仅重跑检查，不重新生成几何。默认读取 `../reviewed_facts/<model_id>.json`，文件不存在时保留适用性未知。原章结构、模型文件和几何失败对象不被替代。

浏览器验证完成：模型切换；真实三维点击门 GUID `0Tif_$wI1FwAwq$OJt24I8`；直接候选筛选；1105.1 反向高亮 1 个门；1102.1 反向关联 48 个对象（37 个有几何）；法规原文和 PDF 页码；补充关联的增加与移除。
