"""记忆记录模块 — 使用LLM提取关键信息转向量和三元组"""

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from src.memory.warm_memory import WarmMemory, Triple
from src.memory.cold_memory import ColdMemory, RawRecord
from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ExtractedInfo:
    content: str
    facts: list[str] = field(default_factory=list)
    triples: list[Triple] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    entry_type: str = "knowledge"
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryRecorder:
    """使用LLM从对话中提取关键信息并存储"""

    def __init__(self):
        self.config = get_config()
        self.warm = WarmMemory()
        self.cold = ColdMemory()

    async def record_from_conversation(
        self, messages: list[dict], session_id: str = "default"
    ) -> list[ExtractedInfo]:
        """从对话历史中提取并记录关键信息"""
        logger.info("从对话中提取关键信息，消息数: %d", len(messages))

        if not messages:
            return []

        conversation_text = "\n".join(
            f"[{m.get('role', 'unknown')}]: {m.get('content', '')}" for m in messages
        )

        extracted = await self._extract_info(conversation_text)

        for info in extracted:
            await self._store_info(info, session_id)

        logger.info("提取并存储了 %d 条信息", len(extracted))
        return extracted

    async def record_from_text(
        self, text: str, entry_type: str = "knowledge", session_id: str = "default"
    ) -> ExtractedInfo:
        """从单条文本中提取并记录"""
        logger.info("从文本提取信息: %s", text[:50])

        extracted = await self._extract_info(text)
        if extracted:
            info = extracted[0]
            if entry_type != "knowledge":
                info.entry_type = entry_type
            await self._store_info(info, session_id)
            return info

        return ExtractedInfo(content=text)

    async def record_direct(
        self,
        content: str,
        facts: Optional[list[str]] = None,
        triples: Optional[list[Triple]] = None,
        entry_type: str = "knowledge",
        session_id: str = "default",
    ) -> ExtractedInfo:
        """直接记录已知信息（不经过LLM提取）"""
        info = ExtractedInfo(
            content=content,
            facts=facts or [],
            triples=triples or [],
            entry_type=entry_type,
        )
        await self._store_info(info, session_id)
        return info

    async def _extract_info(self, text: str) -> list[ExtractedInfo]:
        """使用LLM提取关键信息"""
        llm = self._build_llm()
        prompt = self._build_extract_prompt(text)
        response = await llm.ainvoke(prompt)
        return self._parse_extraction(response)

    def _build_llm(self):
        from langchain_openai import ChatOpenAI
        cfg = self.config.llm
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            temperature=0.3,
            max_tokens=1500,
        )

    def _build_extract_prompt(self, text: str) -> str:
        return f"""你是一个信息提取助手。从以下文本中提取关键信息，包括事实、知识三元组和关键词。

文本:
{text}

请返回JSON格式:
{{
    "facts": ["事实1", "事实2"],
    "triples": [
        {{"subject": "主语", "predicate": "谓语", "object": "宾语", "confidence": 0.9}},
        ...
    ],
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "entry_type": "fact|preference|event|knowledge",
    "summary": "一句话总结"
}}

规则:
1. facts: 提取明确的事实陈述
2. triples: 提取实体关系三元组（主语-谓语-宾语）
3. keywords: 提取3-5个核心关键词
4. entry_type: 判断信息类型
5. 只返回JSON，不要其他内容"""

    def _parse_extraction(self, response) -> list[ExtractedInfo]:
        try:
            text = response.content if hasattr(response, "content") else str(response)
            text = text.strip().removeprefix("```json").removesuffix("```").strip()
            data = json.loads(text)

            triples = []
            for t in data.get("triples", []):
                triples.append(Triple(
                    subject=t["subject"],
                    predicate=t["predicate"],
                    obj=t["object"],
                    confidence=t.get("confidence", 0.9),
                ))

            info = ExtractedInfo(
                content=data.get("summary", ""),
                facts=data.get("facts", []),
                triples=triples,
                keywords=data.get("keywords", []),
                entry_type=data.get("entry_type", "knowledge"),
            )
            return [info]
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("信息提取JSON解析失败: %s", e)
            return []

    async def _store_info(self, info: ExtractedInfo, session_id: str):
        """存储提取的信息"""
        for fact in info.facts:
            await self.warm.store(fact, info.entry_type, info.triples)

        if info.triples:
            for triple in info.triples:
                self.warm.add_triple(triple)

        record = RawRecord(
            record_type="extracted_info",
            content={
                "facts": info.facts,
                "triples": [{"s": t.subject, "p": t.predicate, "o": t.obj} for t in info.triples],
                "keywords": info.keywords,
            },
            metadata={"entry_type": info.entry_type, **info.metadata},
            session_id=session_id,
        )
        self.cold.store(record)
