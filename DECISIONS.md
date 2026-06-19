# Architecture Decision Log

Record of important design decisions and their rationale.

---

## 2026-06-19: 选择Standard tier harness

- **Decision**: 为AI Advisor Agent项目搭建Standard tier harness工程
- **Reason**: 项目是多会话复杂AI Agent项目，需要完整的harness结构来确保跨会话可靠性
- **Constraints**: 需要维护多个文件（AGENTS.md, feature_list.json, progress.md, DECISIONS.md, session-handoff.md, Makefile等）
- **Alternatives considered**: Minimal tier（仅基础文件）和Full tier（包含CI/CI和gotchas.md），但Standard tier提供了最佳平衡
- **When to revisit**: 当项目进入生产环境或需要团队协作时，考虑升级到Full tier

---

## 2026-06-19: 项目结构设计

- **Decision**: 采用模块化目录结构，按功能领域划分
- **Reason**: 项目包含多个复杂子系统（记忆、反思、Bad Case、灰度测试等），需要清晰的模块边界以降低复杂度
- **Constraints**: 需要维护多个模块的依赖关系，初期可能增加开发复杂度
- **Alternatives considered**: 
  - 单体结构：所有代码放在一个目录，简单但难以维护
  - 按技术层划分：controller/service/dao，但不符合AI Agent的业务逻辑
- **项目结构**:
  ```
  ai-advisor-agent/
  ├── src/
  │   ├── core/                    # 核心功能链路
  │   │   ├── intent_parser.py     # 用户意图解析
  │   │   ├── task_decomposer.py   # 任务拆解
  │   │   ├── knowledge_retriever.py # 知识检索
  │   │   ├── tool_executor.py     # 工具执行
  │   │   └── summarizer.py        # 总结生成
  │   ├── memory/                  # 记忆系统
  │   │   ├── hot_memory.py        # 热记忆（对话上下文）
  │   │   ├── warm_memory.py       # 温记忆（向量库+知识图谱）
  │   │   ├── cold_memory.py       # 冷记忆（原始数据）
  │   │   ├── memory_recorder.py   # 记忆记录
  │   │   └── memory_retriever.py  # 记忆检索
  │   ├── reflection/              # 反思机制
  │   │   ├── conflict_detector.py # 冲突检测
  │   │   ├── self_correction.py   # 局部重试
  │   │   ├── agent_debate.py      # Agent协商辩论
  │   │   └── fallback_handler.py  # 全局回退与人工介入
  │   ├── learning/                # 学习系统
  │   │   ├── bad_case_catcher.py  # Bad Case捕获
  │   │   ├── case_classifier.py   # Bad Case分类
  │   │   ├── feedback_loop.py     # 反馈循环
  │   │   └── rule_extractor.py    # 规则提炼
  │   ├── production/              # 生产保障
  │   │   ├── gray_test.py         # 灰度测试
  │   │   ├── circuit_breaker.py   # 熔断机制
  │   │   ├── permission_control.py # 权限控制
  │   │   └── concurrency_optimizer.py # 并发优化
  │   └── utils/                   # 工具类
  │       ├── config.py            # 配置管理
  │       ├── logger.py            # 日志记录
  │       └── validators.py        # 数据验证
  ├── tests/                       # 测试目录
  ├── data/                        # 数据目录
  ├── docs/                        # 文档目录
  └── scripts/                     # 脚本目录
  ```
- **When to revisit**: 当项目规模显著增长或需要微服务拆分时

---

## 2026-06-19: 系统架构设计

- **Decision**: 采用分层架构，结合事件驱动和微服务思想
- **Reason**: 项目需要处理复杂的AI Agent交互、记忆管理、反思机制等，分层架构提供清晰的职责分离，事件驱动支持异步处理和解耦
- **Constraints**: 需要维护事件总线和消息队列，增加系统复杂度
- **Alternatives considered**:
  - 简单MVC架构：无法处理复杂的异步流程和状态管理
  - 纯微服务架构：对于初期项目过于复杂
- **系统架构**:
  ```
  ┌─────────────────────────────────────────────────────────┐
  │                     用户接口层                          │
  │  (Web API / CLI / Chat Interface)                      │
  └───────────────────────┬─────────────────────────────────┘
                          │
  ┌───────────────────────▼─────────────────────────────────┐
  │                     调度层 (Orchestrator)                │
  │  • 意图解析器 (Intent Parser)                           │
  │  • 任务拆解器 (Task Decomposer)                         │
  │  • 流程控制器 (Flow Controller)                         │
  └───────────────────────┬─────────────────────────────────┘
                          │
  ┌───────────────────────▼─────────────────────────────────┐
  │                     核心功能层                          │
  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
  │  │  记忆系统   │ │  反思系统   │ │  学习系统   │       │
  │  │  (Memory)   │ │ (Reflection)│ │ (Learning)  │       │
  │  └─────────────┘ └─────────────┘ └─────────────┘       │
  └───────────────────────┬─────────────────────────────────┘
                          │
  ┌───────────────────────▼─────────────────────────────────┐
  │                     工具与服务层                         │
  │  • 向量数据库 (Vector DB)                               │
  │  • 知识图谱 (Knowledge Graph)                           │
  │  • LLM服务 (OpenAI/本地模型)                            │
  │  • 外部工具API                                          │
  └───────────────────────┬─────────────────────────────────┘
                          │
  ┌───────────────────────▼─────────────────────────────────┐
  │                     基础设施层                          │
  │  • 事件总线 (Event Bus)                                 │
  │  • 消息队列 (Message Queue)                             │
  │  • 配置中心 (Config Center)                             │
  │  • 监控告警 (Monitoring)                                │
  └─────────────────────────────────────────────────────────┘
  ```
- **核心流程**:
  1. 用户输入 → 意图解析 → 任务拆解
  2. 任务拆解 → 记忆检索（向量+知识图谱）→ 上下文增强
  3. 增强上下文 → Agent执行 → 工具调用
  4. 执行结果 → 反思检测 → 冲突处理
  5. 结果输出 → 记忆记录 → 反馈收集
  6. 反馈 → Bad Case捕获 → 规则提炼 → 系统进化
- **关键技术选型**:
  - 向量数据库: Milvus/Weaviate/Chroma
  - 知识图谱: Neo4j/JanusGraph
  - 事件总线: Kafka/RabbitMQ
  - LLM服务: OpenAI API/本地部署
- **When to revisit**: 当系统性能瓶颈出现或需要支持更大规模用户时