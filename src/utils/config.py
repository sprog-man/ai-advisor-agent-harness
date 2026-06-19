"""配置管理模块"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    provider: str = "openai"
    model: str = "gpt-4"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.getenv("OPENAI_API_KEY")


@dataclass
class VectorDBConfig:
    provider: str = "chroma"
    host: str = "localhost"
    port: int = 8000
    collection_name: str = "advisor_knowledge"


@dataclass
class KnowledgeGraphConfig:
    provider: str = "neo4j"
    host: str = "localhost"
    port: int = 7687
    username: str = "neo4j"
    password: Optional[str] = None

    def __post_init__(self):
        if self.password is None:
            self.password = os.getenv("NEO4J_PASSWORD", "password")


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    vector_db: VectorDBConfig = field(default_factory=VectorDBConfig)
    knowledge_graph: KnowledgeGraphConfig = field(default_factory=KnowledgeGraphConfig)
    max_retries: int = 3
    log_level: str = "INFO"
    debug: bool = False


_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def load_config(config_path: Optional[str] = None) -> AppConfig:
    global _config
    if config_path and os.path.exists(config_path):
        import json
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _config = AppConfig(
            llm=LLMConfig(**data.get("llm", {})),
            vector_db=VectorDBConfig(**data.get("vector_db", {})),
            knowledge_graph=KnowledgeGraphConfig(**data.get("knowledge_graph", {})),
            max_retries=data.get("max_retries", 3),
            log_level=data.get("log_level", "INFO"),
            debug=data.get("debug", False),
        )
    else:
        _config = AppConfig()
    return _config
