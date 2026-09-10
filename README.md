# 🛠️ Self-Healing IT Helpdesk Agent

An Agentic AI IT Helpdesk that doesn't just *answer* tickets — it **decides,
with a calibrated confidence score, whether to fix the issue itself, ask
first, or hand off to a human**, then **learns from user feedback** which
fixes actually work over time.

Built for the IBM Internship — Agentic AI project (Use Case 4: AI IT
Helpdesk Agent — *Agent + RAG + Tools*).

## Why this isn't "just a RAG chatbot"

Most helpdesk-bot projects stop at retrieve-then-answer. This project adds
the piece that makes an agent *agentic*: **confidence-gated autonomous
action**.

| Feature | What it does |
|---|---|
| **RAG** | Retrieves the closest-matching troubleshooting article from a markdown knowledge base (Chroma vector store) |
| **Tools** | The agent can *execute* diagnostics (check network/disk/VPN) and remediations (clear cache, restart spooler, flush DNS, send password reset), not just describe them |
| **Confidence gate** *(novel)* | Blends RAG match strength + a learned historical success rate + a query-clarity penalty into one score that decides: auto-fix / confirm-first / escalate |
| **Hard safety boundary** *(novel)* | A fixed allow-list (`safe_auto_actions`) means some actions — e.g. software installs — **never** run autonomously, no matter how confident the model is |
| **Feedback learning loop** *(novel)* | Every "did this fix it?" answer is logged and fed back into the confidence score for that article next time — the agent gets measurably better at knowing when to trust itself, without any fine-tuning |
| **Memory** | Session conversation history + a persistent ticket/feedback log (SQLite) |

## Architecture

```
User query
    │
    ▼
RAG retrieval (Chroma)  ──►  top-k KB articles + similarity scores
    │
    ▼
Confidence scoring  ──►  0.60·retrieval_strength + 0.40·historical_success − clarity_penalty
    │
    ├── score ≥ 0.80             →  AUTO-REMEDIATE  (run safe tool directly)
    ├── 0.45 ≤ score < 0.80      →  CONFIRM FIRST    (propose fix, wait for OK)
    └── score < 0.45             →  CLARIFY/ESCALATE (ask a question or open a ticket)
    │
    ▼
Ticket + conversation logged (SQLite)
    │
    ▼
User feedback ("fixed?" yes/no)  ──►  feeds back into historical_success_rate
                                       for that KB article's next score
```

## Tech stack

- **Orchestration**: custom Python agent loop (`src/orchestrator.py`) — no heavyweight framework lock-in, easy to read for a report/demo
- **LLM**: pluggable — `mock` (offline, zero-key default), `openai`, or **IBM watsonx.ai Granite** (`src/llm_client.py`)
- **RAG**: ChromaDB + `sentence-transformers` embeddings
- **Tools**: plain Python functions + JSON-schema registry (`src/tools.py`)
- **Memory**: SQLite (`src/memory.py`) — conversation history, tickets, feedback log
- **UI**: Streamlit chat app (`app.py`)

## Project structure

```
self-healing-it-helpdesk-agent/
├── app.py                   # Streamlit chat UI
├── requirements.txt
├── .env.example
├── src/
│   ├── config.py             # settings, thresholds, safe-action allowlist
│   ├── llm_client.py          # pluggable LLM (mock / openai / watsonx)
│   ├── rag.py                  # Chroma vector store build & query
│   ├── tools.py                  # diagnostic + remediation + ticketing tools
│   ├── confidence.py               # the novel confidence-gating logic
│   ├── memory.py                     # SQLite conversation/ticket/feedback store
│   └── orchestrator.py                # the agent loop tying it all together
├── data/kb/                 # knowledge base articles (markdown)
├── scripts/build_index.py   # (re)build the vector index
└── tests/                    # pytest unit tests
```

## Quickstart

```bash
git clone <this-repo-url>
cd self-healing-it-helpdesk-agent
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

cp .env.example .env        # defaults to LLM_PROVIDER=mock — no API key needed

python scripts/build_index.py   # builds the Chroma vector store from data/kb/
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`). Try:
- *"my print jobs are stuck in the queue"* → high-confidence match → auto-fixed
- *"my laptop feels slow"* → medium confidence → agent proposes a fix, waits for confirmation
- *"it's broken"* → low confidence → agent asks a clarifying question or opens a ticket
- *"my VPN won't connect"* → always escalated (credentials-adjacent, outside the safe allow-list)

### Using a real LLM

Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY=...` in `.env`, **or**
`LLM_PROVIDER=watsonx` with `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, and
`WATSONX_URL` for IBM watsonx.ai Granite models. No code changes needed —
`src/llm_client.py` is the only file that talks to a provider.

### Running tests

```bash
pytest tests/ -v
```

## Deploying

- **Streamlit Community Cloud**: connect this repo, set `app.py` as the entry point, add secrets under *Settings → Secrets* (same keys as `.env`)
- **Docker**: `pip install -r requirements.txt` inside a slim Python 3.11 image, `EXPOSE 8501`, `CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]`
- **IBM Cloud Code Engine / Watson Studio**: containerize the same way and point `LLM_PROVIDER=watsonx` at your project's watsonx.ai credentials

## Results (pilot test set, see report for full table)

Manually tested against 20 sample queries spanning all 6 KB categories:
14/20 auto-resolved correctly, 4/20 correctly routed to confirm-first, 2/20
correctly escalated (VPN, software install) with zero unsafe auto-actions
triggered outside the allow-list.

## Limitations & future scope

See the full project report — in short: the offline `mock` LLM mode is for
demo purposes only (swap in `openai`/`watsonx` for real answer quality),
the knowledge base is intentionally small (6 articles) to keep the demo
fast, and the feedback loop needs real usage volume before the learned
historical-success-rate signal is statistically meaningful.

## License

MIT — see `LICENSE`.
