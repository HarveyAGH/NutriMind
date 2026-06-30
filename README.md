# NutriMind 🥗

> Multi-agent AI nutrition assistant built with LangGraph — stateful memory, longitudinal health analysis, and human-in-the-loop medical flagging.

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.6-green)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-red)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)](https://postgresql.org)
[![LangSmith](https://img.shields.io/badge/LangSmith-Traced-orange)](https://smith.langchain.com)
[![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock-yellow)](https://aws.amazon.com/bedrock/)

---

## What Makes This Different

Most nutrition chatbots are stateless wrappers around a single LLM call. NutriMind is a production-grade multi-agent system that:

- **Remembers everything across sessions** — PostgreSQL-backed checkpointing via LangGraph's PostgresSaver
- **Detects goal drift proactively** — compares your actual 7-day eating patterns against your stated goal before generating any meal plan
- **Flags medical concerns automatically** — 3+ consecutive days under 1200 kcal triggers `interrupt()` and pauses the graph for human review
- **Evaluates its own output** — every meal plan passes through an LLM-as-judge eval gate before being returned to the user
- **Analyzes 14-day longitudinal patterns** — not just today's macros, but iron deficiency trends, calorie adherence rates, and streak tracking

---

## Architecture

```
User Message
     ↓
┌─────────────────────────────────────────┐
│              Supervisor                  │
│  Routes user intent to correct agent    │
└────────┬────────────────────────────────┘
         │
    ┌────┴──────┬────────────┬────────────┬──────────────┐
    ▼           ▼            ▼            ▼              ▼
memory_     nutrition_    planning_    intake_       insight_
agent       rag_agent     agent        agent         agent
    │           │            │            │              │
    └───────────┴────────────┴────────────┴──────────────┘
                             │
                        supervisor
                             │
                           END
```

**Supervisor** routes each message to exactly one specialist agent using LangGraph's `Command` pattern. Every specialist returns via `Command(goto="supervisor")` — no conditional edges needed.

---

## Agents

| Agent | Temperature | Responsibility |
|---|---|---|
| `supervisor` | 0.0 | Routes user intent to correct specialist |
| `memory_agent` | 0.1 | User profiles + meal history (PostgreSQL) |
| `nutrition_rag_agent` | 0.3 | Nutrition Q&A, USDA data, RDA validation |
| `planning_agent` | 0.7 | Adaptive meal plans + goal drift detection + eval gate |
| `intake_agent` | 0.0 | Meal logging + running macros + deficiency detection |
| `insight_agent` | 0.3 | 14-day pattern analysis + medical flagging + streaks |

---

## Tools

| Tool | Pattern | Agent |
|---|---|---|
| `get_user_profile` | File I/O → PostgreSQL | memory_agent |
| `upsert_user_profile` | State Mutation + PostgreSQL | memory_agent |
| `get_meal_history` | File I/O → PostgreSQL | memory_agent |
| `search_nutrition_kb` | RAG Retrieval (FAISS) | nutrition_rag_agent |
| `get_nutrition_info` | API Call (USDA) | nutrition_rag_agent |
| `validate_against_rda` | Computation | nutrition_rag_agent |
| `detect_goal_drift` | Computation + PostgreSQL | planning_agent |
| `score_meal_plan` | LLM-as-Judge Eval Gate | planning_agent |
| `log_meal` | File I/O → PostgreSQL | intake_agent |
| `get_running_macros` | Computation + PostgreSQL | intake_agent |
| `detect_deficiencies` | Computation + PostgreSQL | intake_agent |
| `analyze_nutrition_patterns` | Computation + PostgreSQL | insight_agent |
| `track_streaks` | Computation + PostgreSQL | insight_agent |

---

## Tech Stack

- **Orchestration** — LangGraph `StateGraph` + `Command` routing
- **LLM** — Claude Haiku via AWS Bedrock (`ChatBedrockConverse`)
- **Memory** — LangGraph `PostgresSaver` — cross-session conversation state
- **Database** — PostgreSQL 16 — `user_profiles`, `meal_logs` tables
- **Vector Store** — FAISS index built from nutrition guidelines, NIH fact sheets, and WHO clinical references
- **Observability** — LangSmith tracing on every node and tool call
- **API** — FastAPI with Uvicorn
- **UI** — Streamlit chat interface
- **CI** — GitHub Actions (pytest on push/PR)
- **Package manager** — `uv`

---

## Project Structure

```
NutriMind/
├── agent/
│   ├── __init__.py       # Package init
│   ├── agent.py          # Graph definition, supervisor, all agent nodes
│   ├── tools.py          # 13 tools across 5 patterns
│   ├── app.py            # FastAPI wrapper — /health + /chat endpoints
│   └── db.py             # PostgreSQL connection, table setup, all DB functions
├── rag/
│   ├── vector_store.py   # FAISS vector store (build, search, persist)
│   ├── embeddings.py     # SentenceTransformer embedding pipeline
│   └── data_loader.py    # Load PDF/TXT documents for indexing
├── data/                 # Nutrition knowledge base source documents
├── faiss_store/          # Persisted FAISS index and metadata
├── tests/
│   └── test_tools.py     # 16 unit tests (mocked DB/LLM)
├── streamlit_app.py      # Chat UI
├── docker-compose.yaml   # PostgreSQL local dev container
├── pyproject.toml        # Dependencies (uv)
├── .github/workflows/ci.yaml  # CI pipeline
└── .env                  # Credentials (git-ignored)
```

---

## Setup

### Prerequisites

- Python 3.12+
- `uv` package manager
- AWS account with Bedrock access (Claude Haiku enabled in us-east-1)
- PostgreSQL (local via Docker or hosted)
- LangSmith account (free)

### 1. Clone and install

```bash
git clone https://github.com/HarveyAGH/NutriMind.git
cd NutriMind
uv sync
```

### 2. Environment variables

Create a `.env` file in the root:

```env
# AWS Bedrock
BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0
BEDROCK_REGION=us-east-1
AWS_BEARER_TOKEN_BEDROCK=your_token_here

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/nutrimind

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=NutriMind_Nutritions
```

### 3. Start PostgreSQL

```bash
docker-compose up -d
```

### 4. Run the API

Tables are created automatically on startup.

```bash
uv run uvicorn agent.app:api --host 0.0.0.0 --port 8000
```

### 5. Launch the UI (optional)

```bash
uv run streamlit run streamlit_app.py
```

---

## API Endpoints

### Health check

```bash
curl http://localhost:8000/health
# {"status": "ok", "service": "NutriMind"}
```

### Chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How many calories in 100g chicken breast?", "thread_id": "user_01"}'
```

### Multi-turn memory (same thread_id)

```bash
# Turn 1
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Log that I just ate 100g chicken breast", "thread_id": "user_01"}'

# Turn 2 — agent remembers the chicken breast
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are my macros so far today?", "thread_id": "user_01"}'
```

---

## Key Patterns Demonstrated

**LLM-as-Judge Eval Gate** — `planning_agent` scores every meal plan before returning it. Plans scoring below 7/10 are regenerated automatically.

**Human-in-the-Loop** — `insight_agent` calls `interrupt()` when caloric intake drops below 1200 kcal for 3+ consecutive days. The graph pauses and waits for human review before continuing.

**Goal Drift Detection** — `detect_goal_drift` compares actual 7-day average macros against the user's stated goal. If protein is averaging 40g against a 120g target, `planning_agent` builds the plan around closing that gap.

**RAG-Enhanced Nutrition Knowledge** — FAISS vector store built from:

- Dietary Guidelines for Americans (food groups, caloric targets, macro distribution)
- WHO/FAO chronic disease prevention clinical reference (TRS 916)
- NIH Office of Dietary Supplements health professional fact sheets (macros, micronutrients, RDAs)
- NIH FAQ database (supplements, interactions, regulations)

---

## Observability

All traces visible in LangSmith under project `NutriMind_Nutritions`. Every supervisor routing decision, tool call, and agent response is tracked with latency and cost.

---

## Future Work

- [ ] LangMem integration for episodic cross-session memory
- [ ] React Native frontend
- [ ] Nutritionix API integration for barcode scanning
- [ ] Eval dataset — 20 golden meal plan Q&A pairs
- [ ] Background insight polling (proactive alerts without user prompt)
- [ ] Multi-user support with auth

---

Built by [Ahmed (Harvey)](https://github.com/HarveyAGH) — AI Agent Systems Engineer
