# 多 Agent 协作（Multi-Agent Collaboration）

本文档描述 Trend Scout Enterprise 的多 Agent 协作层（务实第一版，不引入
CrewAI 等外部框架，编排仍由现有 LangGraph 工作流 `workflows/scan_graph.py`
与服务层承担）。代码位于 `backend/src/trend_scout_enterprise/agents/`。

## 角色映射（AgentRole）

`agents/base.py` 中的 `AgentRole` 常量把流水线中的角色显式命名，并文档化
每个角色对应的现有代码位置（仅记录映射，不重构这些模块）：

| 角色 | 常量 | 对应代码 |
|---|---|---|
| 数据采集 | `DATA_COLLECTOR` | `scanners/`（由 scan_graph 调用，产出 `RawItem`） |
| 评分 | `SCORER` | `services/scoring_service.py`（维度评分、审核路由），批量编排见 `services/analysis_service.py` |
| 人工审核 | `REVIEWER` | `api/signals_router.py` 审核端点（`POST /signals/{id}/review`）+ `models/signal_review.py` |
| 趋势分析 | `TREND_ANALYST` | `agents/trend_analyst.py`（本次新增） |
| 报告 | `REPORTER` | `services/report_service.py` / `card_report_service.py` / `ppt_report_service.py` |

## BaseAgent

`agents/base.py` 的 `BaseAgent` 是所有 Agent 的抽象基类：

- 属性：`name`、`role`。
- 抽象方法：`async run(context: dict) -> dict`。
- 调用协议：`await agent(context)` 会包裹 `run`，输出 structlog 结构化日志
  `agent_started` / `agent_completed`，事件含 `agent`、`role`、`duration_ms`。

## TrendAnalystAgent

`agents/trend_analyst.py`，`role = TREND_ANALYST`。对一组高分信号（趋势桶的
top evidence items，通常为 approved/auto 且 `overall_score` 高的条目）做深度
分析：

- 复用 `LlmService.chat_completion`，prompt 要求返回 JSON：
  `{"themes": [...], "connections": [...], "recommended_actions": [...], "summary": "2-3句执行摘要"}`。
- 解析容错与 `LlmService._parse_score_response` 同款：剥离 ``` 代码围栏后
  `json.loads`；失败时回退为 `{"summary": 原始文本截断（500 字符）}`。
- 结果写入每个 item 的 `metadata_json["analyst_insight"]`（不新增 DB 列），
  由调用方负责 commit。
- 执行后发布事件 `TREND_ANALYZED`（`trend.analyzed`），payload 含
  `point_id`、`themes_count`。

### 用法

```python
from trend_scout_enterprise.agents import TrendAnalystAgent
from trend_scout_enterprise.services.llm_service import get_default_llm_service_or_none

llm = get_default_llm_service_or_none(db)
agent = TrendAnalystAgent(llm)
insight = await agent({"items": top_items, "point_id": point.id})
```

## 开关配置

`core/config.py` 新增 `trend_analyst_enabled: bool = False`（环境变量
`TREND_ANALYST_ENABLED`）。默认关闭，聚合行为与之前完全一致。

开启后，`services/trends_service.aggregate_trends_for_workspace` 在为每个
bucket 生成 `TopicTrendPoint` 与 evidence 之后：

1. 通过 `get_default_llm_service_or_none(db)` 构建 LLM 服务；不可用时跳过。
2. 对该 bucket 的 top evidence items 运行 `TrendAnalystAgent`（best-effort，
   失败仅记日志 `trend_analyst_failed`，不阻塞聚合）。
3. 把 insight 的 `summary` 写入 `point.summary`（模型已有该字段；
   `TopicTrendPoint` 无 metadata 列，themes 等完整结果只落在各 item 的
   `metadata_json["analyst_insight"]` 中）。

注意：聚合是同步函数，内部通过 `asyncio.run` 调用 Agent；若检测到已在运行的
事件循环则跳过分析并记录 `trend_analyst_skipped`（当前所有调用方——同步
API 端点与 Celery worker——均不在事件循环内）。

## 事件

| 事件 | 发布方 | Payload |
|---|---|---|
| `SIGNALS_SCORED`（`signals.scored`） | `services/analysis_service.analyze_signals_batch` | `item_ids`、`analyzed`、`failed` |
| `TREND_ANALYZED`（`trend.analyzed`） | `agents/trend_analyst.TrendAnalystAgent` | `point_id`、`themes_count` |

`SIGNALS_SCORED` 此前只有常量没有发布方，本次由评分批量流程补全。

## 演进路径（CrewAI 迁移）

当前实现刻意保持框架无关，后续引入 CrewAI（或类似框架）时的建议路径：

1. **接口稳定先行**：`BaseAgent.run(context) -> dict` 的契约保持不变，
   CrewAI 的 `Agent`/`Task` 作为适配层包装现有 Agent，而不是替换业务逻辑。
2. **编排上移**：先把 `TrendAnalystAgent` 以外的角色（collector/scorer/
   reporter）包装为 CrewAI Task，再评估是否把 `scan_graph` 的 LangGraph
   编排迁移为 Crew Flow；两者可长期共存。
3. **事件总线不变**：`events/bus.py` 的 `subscribe`/`publish` 是对外契约，
   跨进程化（Redis pub/sub / MQ）与框架迁移相互独立。
4. **观测对齐**：CrewAI 自带的 tracing 与现有 `agent_started`/
   `agent_completed` structlog 事件做字段映射，保留 `role`、`duration_ms`。
