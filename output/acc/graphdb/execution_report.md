# GraphDB Free 安装及 RDF 导入记录

执行日期：2026-10-10。

## 已完成

- 从 Ontotext 官方公开 Maven 仓库下载并安装 GraphDB 10.6.4；未注册账号，未申请许可证。
- 配套安装 Eclipse Temurin 17 JRE，仅供本项目使用；没有更改系统 Java 或 PATH。
- GraphDB 实际版本接口返回 `productType: free`，首页显示 Free Edition、Freeware、Perpetual。
- 本地工作台已打开：http://localhost:7200/ 。HTTP 服务绑定 127.0.0.1:7200。
- 创建数据库 `ibc2021-accessibility`，导入原有 `11_combined_graph.trig`，保留两个命名图。
- 文档图 2,664 条；实体图 6,984 条；显式关系合计 9,648 条。
- 导出后逐条比对原始 RDF 四元组：遗漏 0，新增 0，全部一致。原始 PDF 和 RDF 未修改。
- 推理规则设为 `empty`，当前推理新增关系为 0；这些内容仍为待专家审核的候选知识图谱。

## 路径

- 程序：`C:\Users\dyp\AppData\Local\Programs\GraphDB-10.6.4`
- 数据、配置、日志：`D:\00_SL1008\output\acc\graphdb\home`
- 导入源：`D:\00_SL1008\output\ibe_accessibility_structure\semantic_rdf\11_combined_graph.trig`
- 下载校验记录：`installation_manifest.json`
- 导入校验记录：`import_verification.json`
- 完成截图：`graphdb_workbench.jpg`
- 启动脚本：`Start-GraphDB.ps1`；启动并打开浏览器：`Open-GraphDB.ps1`。

## 使用

双击桌面 `GraphDB IBC Accessibility` 快捷方式。首次打开后如未自动选择数据库，在右上角选择 `ibc2021-accessibility`。

查看关系：左侧 **Explore**；查看法规原文属性：在首页 **View resource** 输入资源完整地址，再点 **Table** 或 **Visual**。例如 `https://example.org/ibc/2021/ibc2021-1106.6`。

数据库在电脑重启后保留；重新打开快捷方式会启动服务。浏览器关闭不会关闭后台服务。

## 工具、AI 与失败记录

- 工具：PowerShell、Python 标准库、RDFLib、GraphDB REST/RDF4J 接口、浏览器自动化及官方文档查询。
- AI Token：使用 AI 辅助选择版本、安装编排和报告；本次精确 Token 数不可取得。
- 备用下载路线：Adoptium API 返回 403，改用该项目官方 GitHub 发布包；Java SHA256 和 GraphDB 官方 SHA1 均校验通过，压缩包 CRC 校验通过。
- JRE 缺少可选 `jdk.management.agent` 模块，首次启动出现警告；服务正常且完成导入。后续启动脚本去除该可选参数。
- 没有新生成或更改法规解释、ACC 检查结果或人工审核结论；现有 86 项复杂条款仍待专家复核。

版本选择依据：https://graphdb.ontotext.com/documentation/10.6/set-up-your-license.html 。10.6 Free 默认模式不需许可证文件；选择此版本满足本次无注册、无许可证申请要求。
