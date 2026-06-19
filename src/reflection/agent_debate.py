"""Agent协商辩论模块 — 多Agent观点协商"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class AgentRole(Enum):
    PROPOSER = "proposer"      # 提出观点
    CRITIC = "critic"          # 质疑观点
    MEDIATOR = "mediator"      # 协调仲裁
    VALIDATOR = "validator"    # 验证结论


@dataclass
class AgentOpinion:
    agent_id: str
    role: AgentRole
    content: str
    confidence: float = 0.8
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DebateResult:
    topic: str
    opinions: list[AgentOpinion]
    consensus: str = ""
    unresolved: list[str] = field(default_factory=list)
    rounds: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentDebate:
    """多Agent协商辩论机制"""

    def __init__(self, max_rounds: int = 3):
        self.config = get_config()
        self.max_rounds = max_rounds

    async def debate(self, topic: str, initial_opinion: str = "") -> DebateResult:
        """发起辩论"""
        logger.info("开始辩论: %s", topic[:50])

        opinions = []
        if initial_opinion:
            opinions.append(AgentOpinion(
                agent_id="agent_0",
                role=AgentRole.PROPOSER,
                content=initial_opinion,
            ))

        for round_num in range(1, self.max_rounds + 1):
            logger.info("辩论轮次 %d/%d", round_num, self.max_rounds)

            critic_opinion = await self._generate_critic_opinion(topic, opinions)
            opinions.append(critic_opinion)

            if critic_opinion.confidence < 0.3:
                logger.info("质疑置信度低，辩论结束")
                break

            if round_num < self.max_rounds:
                proposer_response = await self._generate_response(topic, opinions)
                opinions.append(proposer_response)

        consensus = await self._mediate(topic, opinions)

        return DebateResult(
            topic=topic,
            opinions=opinions,
            consensus=consensus,
            rounds=min(round_num, self.max_rounds),
        )

    async def consult(self, topic: str, perspective: str) -> AgentOpinion:
        """咨询特定视角"""
        llm = self._build_llm()
        prompt = f"""你是一个顾问，从以下视角分析问题。

视角: {perspective}
问题: {topic}

请提供你的分析和建议，简明扼要。"""
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        return AgentOpinion(
            agent_id="consultant",
            role=AgentRole.VALIDATOR,
            content=content.strip(),
        )

    async def _generate_critic_opinion(self, topic: str, opinions: list[AgentOpinion]) -> AgentOpinion:
        """生成批评意见"""
        opinions_text = "\n".join(f"[{o.role.value}] {o.content}" for o in opinions[-2:])

        llm = self._build_llm()
        prompt = f"""你是一个批判性思考者。分析以下观点，找出问题和漏洞。

问题: {topic}

现有观点:
{opinions_text}

请指出这些观点的问题，质疑其合理性。如果观点合理，说明理由。"""
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        return AgentOpinion(
            agent_id="critic",
            role=AgentRole.CRITIC,
            content=content.strip(),
            confidence=0.8,
        )

    async def _generate_response(self, topic: str, opinions: list[AgentOpinion]) -> AgentOpinion:
        """生成回应"""
        opinions_text = "\n".join(f"[{o.role.value}] {o.content}" for o in opinions[-2:])

        llm = self._build_llm()
        prompt = f"""你是原观点提出者。回应批判性意见，维护或修正你的观点。

问题: {topic}

讨论记录:
{opinions_text}

请回应质疑，可以坚持原观点或做出修正。"""
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        return AgentOpinion(
            agent_id="proposer",
            role=AgentRole.PROPOSER,
            content=content.strip(),
        )

    async def _mediate(self, topic: str, opinions: list[AgentOpinion]) -> str:
        """协调仲裁，生成共识"""
        opinions_text = "\n".join(f"[{o.role.value}] {o.content}" for o in opinions)

        llm = self._build_llm()
        prompt = f"""你是协调者。综合各方观点，给出最终结论。

问题: {topic}

各方观点:
{opinions_text}

请给出平衡、客观的最终结论。"""
        response = await llm.ainvoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _build_llm(self):
        from langchain_openai import ChatOpenAI
        cfg = self.config.llm
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            temperature=0.5,
            max_tokens=1000,
        )
