# IBC 无障碍法规 RDF：SPARQL 演示案例

整理日期：2026-10-10。

SPARQL 可以理解为“向知识图谱提问的语言”。以下六个案例已在项目的 GraphDB 数据库中实际测试。

## 使用方法

1. 打开 GraphDB 工作台：http://localhost:7200/ 。
2. 在右上角选择数据库 `ibc2021-accessibility`。
3. 在左侧打开 **SPARQL**。
4. 每次复制下面一个完整查询，粘贴到查询编辑区，点击 **Run**。

数据来源：`D:\00_SL1008\output\ibe_accessibility_structure\semantic_rdf\11_combined_graph.trig`。

## 1. 我们的图谱有多少条关系？

```sparql
SELECT ?graph (COUNT(*) AS ?relations)
WHERE {
  GRAPH ?graph { ?subject ?predicate ?object }
}
GROUP BY ?graph
```

预期结果：

| 分区 | 关系数量 |
|---|---:|
| Document Graph：法规文档结构 | 2,664 |
| Entity Graph：法规语义关系 | 6,984 |
| 合计 | 9,648 |

**演示时说：**“我们把法规的章节结构和法规中的要求分别保存，但可以一起查询。”

## 2. 法规被拆成了哪些内容？

```sparql
PREFIX ibc: <https://example.org/ibc/2021/>
PREFIX ibco: <https://example.org/ibc/ontology/>

SELECT ?type (COUNT(DISTINCT ?item) AS ?count)
WHERE {
  GRAPH ibc:entityGraph {
    VALUES ?type {
      ibco:Requirement
      ibco:AtomicRule
      ibco:Condition
      ibco:Measurement
    }
    ?item a ?type .
  }
}
GROUP BY ?type
ORDER BY DESC(?count)
```

预期结果：

| 类型 | 含义 | 数量 |
|---|---|---:|
| AtomicRule | 候选原子规则 | 462 |
| Requirement | 条款级语义对象 | 289 |
| Condition | 条件节点 | 174 |
| Measurement | 测量节点 | 110 |

**演示时说：**“系统不仅保存文字，还把要求、条件和数值分别组织起来。”

## 3. 展示原子规则，并追溯原始 PDF

```sparql
PREFIX ibc: <https://example.org/ibc/2021/>
PREFIX ibco: <https://example.org/ibc/ontology/>

SELECT ?rule ?text ?source ?pdfPage
WHERE {
  GRAPH ibc:entityGraph {
    ?requirement ibco:hasAtomicRule ?rule ;
                 ibco:sourceNode ?source .

    ?rule a ibco:AtomicRule ;
          ibco:text ?text .
  }

  GRAPH ibc:documentGraph {
    ?source ibco:sourcePage ?pdfPage .
  }
}
ORDER BY ?source ?rule
LIMIT 10
```

结果字段：

- `rule`：原子规则的资源地址。
- `text`：规则文字。
- `source`：原始条款节点。
- `pdfPage`：原始完整 PDF 的实际页序，并非截取 PDF 的页序或书内印刷页码。

此查询展示前 10 行结果。一个条款如跨多页，同一规则可能出现多行来源页记录。

**演示时说：**“每条候选规则都有出处，专家能回到原文核对。”

## 4. 一个建筑案例：无障碍厢式车停车位

查询 **1106.6**，同时展示条款、原子规则、关联例外和来源页。

```sparql
PREFIX ibc: <https://example.org/ibc/2021/>
PREFIX ibco: <https://example.org/ibc/ontology/>

SELECT ?clauseText ?atomicText ?exceptionText ?pdfPage
WHERE {
  GRAPH ibc:entityGraph {
    VALUES ?requirement { ibc:sem-ibc2021-1106.6 }

    ?requirement ibco:text ?clauseText ;
                 ibco:sourceNode ?source ;
                 ibco:hasAtomicRule ?rule .

    ?rule ibco:text ?atomicText .
  }

  GRAPH ibc:documentGraph {
    ?source ibco:sourcePage ?pdfPage .
  }

  OPTIONAL {
    GRAPH ibc:entityGraph {
      ?requirement ibco:hasException ?exception .
    }
    GRAPH ibc:documentGraph {
      ?exception ibco:text ?exceptionText .
    }
  }
}
```

实际结果包含“每六个或不足六个无障碍停车位，至少一个为厢式车无障碍停车位”的候选规则、相关例外，来源为原始 PDF 第 **359** 页。

`OPTIONAL` 表示：如果存在关联例外，就一同显示；没有例外时，仍保留主要查询结果。此查询展示当前图谱中记录的关系，并不自动证明已覆盖所有上级条件或适用性要求。

**演示时说：**“我们能一起查看要求和例外，避免只提取一个数字就直接检查。”

## 5. 哪些条款还需要专家审核？

```sparql
PREFIX ibc: <https://example.org/ibc/2021/>
PREFIX ibco: <https://example.org/ibc/ontology/>

SELECT ?source ?text
       (GROUP_CONCAT(DISTINCT STR(?pdfPage); separator=", ")
        AS ?pdfPages)
WHERE {
  GRAPH ibc:entityGraph {
    ?requirement a ibco:Requirement ;
                 ibco:reviewStatus "unreviewed" ;
                 ibco:sourceNode ?source ;
                 ibco:text ?text .
  }

  GRAPH ibc:documentGraph {
    ?source ibco:sourcePage ?pdfPage .
  }
}
GROUP BY ?source ?text
ORDER BY ?source
```

返回 **86 个待复核条款级对象**。跨页条款的页码会合并显示，合并后的页码顺序不保证为数值升序。

**演示时说：**“系统明确保留尚未审核的内容，而不是把所有提取结果都当作正确解释。”

## 6. 展示一个条款周围的关系网络

前面的查询返回表格；`CONSTRUCT` 返回一组 RDF 关系，适合展示“节点怎样连接”。结果的具体显示形式取决于 GraphDB 的结果视图选择。

```sparql
PREFIX ibc: <https://example.org/ibc/2021/>
PREFIX ibco: <https://example.org/ibc/ontology/>

CONSTRUCT {
  ?requirement ?p ?o .
  ?source ?sourceProperty ?sourceValue .
  ?rule ?ruleProperty ?ruleValue .
  ?exception ?exceptionProperty ?exceptionValue .
}
WHERE {
  GRAPH ibc:entityGraph {
    VALUES ?requirement { ibc:sem-ibc2021-1106.6 }

    ?requirement ?p ?o ;
                 ibco:sourceNode ?source .

    OPTIONAL {
      ?requirement ibco:hasAtomicRule ?rule .
      ?rule ?ruleProperty ?ruleValue .
    }
  }

  GRAPH ibc:documentGraph {
    ?source ?sourceProperty ?sourceValue .
  }

  OPTIONAL {
    GRAPH ibc:entityGraph {
      ?requirement ibco:hasException ?exception .
    }
    GRAPH ibc:documentGraph {
      ?exception ?exceptionProperty ?exceptionValue .
    }
  }
}
```

**演示时说：**“一个法规要求连接着原始条款、候选规则、例外和证据。这些连接就是知识图谱的核心。”

## 三分钟演示建议

依次使用 **第 2、4、5 个案例**：

1. 项目规模：法规被组织成了哪些内容。
2. 具体建筑案例：停车位要求如何关联原文、规则和例外。
3. 专家审核环节：复杂条款如何明确列为待复核。

## 解释边界

- 当前图谱是可审计的候选知识图谱，不是经过法律专家认证的最终法规解释。
- 462 条候选原子规则不等于 462 条可直接执行的合规检查。
- `rule_validated` 表示项目中的规则验证状态，不代表通过法律专家认证或建筑模型合规。
- 上述查询只读取 RDF，不修改数据库，也不执行 IFC 模型检查。
