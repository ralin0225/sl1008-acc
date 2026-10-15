# Chapter 10 处理及 visualization 更新报告

执行日期：2026-10-10。

## 第 1–12 步

- 输入：`IBC2021_10MeansOfEngress.pdf`，52 页；逐页文本匹配原始 IBC PDF 实际第 304–355 页。
- 最后一页为正文空白页，保留在来源与页面渲染中。
- 6,167 条正文来源行全部唯一归属，无遗漏、重复或未知引用。
- 1194 个结构节点、31 个 section、423 个 provision、161 个 exception、577 个 list_item、12 个表格候选。
- 1161 个条款级语义候选；1299 条候选原子规则；496 个测量节点；423 个条件节点。
- 文档图 9926 条，实体图 23592 条；共 33518 条显式三元组。
- JSON Schema、来源文本对齐、SHACL、OWL-RL sanity check 通过；owl:Nothing 实例为 0。
- 人工语义复核队列 855 项；编号列表范围、表格结构和复杂数值仍需专家复核。
- 52 张页面渲染、6 张联系表及每一步输入/输出/工具/AI 使用/失败处理记录均已保留。

## 页面更新

- 同一 IFC／法规网站现同时收录 Chapter 10 和 Chapter 11，共 1,499 个证据条目。
- 新增章节复选框：单独勾选任何一章、同时勾选两章，或取消全部选择。
- 选择保存在浏览器，并同步影响法规列表、搜索、构件相关条目、反向关联与高亮。
- 每条法规打开所属章节的真实源 PDF；Chapter 10 的 1010.1.1 门净宽条款打开摘录第 13 页／原始 PDF 第 316 页。
- 门、楼梯、坡道、空间的 Chapter 10 类型关联为候选，需审核；不作法律适用性审批。没有重新生成 IFC 几何或更改模型检查状态。
- 中英界面保留；用户补充关联保留。
- 12 个 Node 数据和功能测试通过。原生浏览器验证因无法可靠识别当前浏览器 URL 被停止；不声称本轮完整浏览器交互已验证。

## 工具与 AI

Python、PyMuPDF、Pillow、JSON Schema、RDFLib、pySHACL、OWL-RL、Node、Sites；AI 用于实现和联系表审查，精确 Token 数不可取得。语义提取为确定性本地流程，没有逐条外部 LLM API 调用。

## 保留与边界

原始 PDF、Chapter 11 结构化和语义输出保留。修正前的 Chapter 10 首轮及列表轮结果、原 viewer 文件保留于 `output/chapter_processing_history/`。

所有候选规则均通过 source_node_id、PDF 页序及来源 bbox/line_ids 回溯。规则验证通过不等于专家认证；没有把数据缺失或待审核内容当作 PASS。

## GraphDB

Chapter 10 的两个命名图已加入原数据库 `ibc2021-accessibility`，逐条 RDF 四元组比对一致。Chapter 11 两个命名图仍为 2,664 和 6,984 条；四个命名图合计 43,166 条显式关系。导入核验见 `semantic_rdf/15_graphdb_import_verification.json`。

关键文件：`03_structured_document.json`、`semantic_rdf/10_dsl_rules.json`、`semantic_rdf/10_manual_review_queue.json`、`semantic_rdf/11_combined_graph.trig`、`semantic_rdf/12_validation_report.json`。

## 发布

- 已更新原网站：https://ifc-regulation-workbench.airyjoy32.chatgpt.site ，版本 4，部署状态 succeeded；原有仅所有者访问权限保留。
- 源码提交：`39c352769e663c32ec5c122d3624f6b503b9ca45`，已由官方 Sites 工作流提交并推送。
- 官方 Node 包装器的 Windows 路径导致打包失败；改用同一官方 package-site.sh，经本地 sh.exe 调用成功，未修改插件。发布包：`output/acc/viewer-chapters-deploy.tar.gz`。
- 部署、版本与归档校验值记录在 `output/acc/viewer_deployment_chapters.json`。本轮未取得新页面浏览器截图。
