# AI Advisor Agent

An AI Agent + RAG project for generating decision reports and AI knowledge Q&A. This project can break down user's vague ideas into concrete implementation steps.

## Features

- **Core Pipeline**: Intent parsing → Task decomposition → Knowledge retrieval → Thinking → Tool calling → Summarization
- **Memory System**: Hot-warm-cold three-layer architecture with vector + knowledge graph dual storage
- **Reflection Mechanism**: Self-correction, agent debate, global fallback with human-in-the-loop
- **Learning System**: Bad case capture, classification, golden test set, regression testing
- **Production Ready**: Gray testing, circuit breaker, permission control, concurrency optimization

## Project Structure

```
ai-advisor-agent/
├── src/
│   ├── core/           # Core pipeline components
│   ├── memory/         # Memory system (hot/warm/cold)
│   ├── reflection/     # Reflection mechanisms
│   ├── learning/       # Learning and feedback systems
│   ├── production/     # Production safeguards
│   └── utils/          # Utilities and helpers
├── tests/              # Test files
├── data/               # Data storage
├── docs/               # Documentation
└── scripts/            # Helper scripts
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
make check

# Start development
make done
```

## Documentation

- [Architecture Decisions](DECISIONS.md)
- [Project Features](feature_list.json)
- [Progress Log](progress.md)
- [Session Handoff](session-handoff.md)