# promptctl

> Git for prompts. Version, diff, eval, and rollback LLM prompts like source code — with behavior tracking that git alone can't provide.

---

## Why this exists

Every team shipping LLM features eventually hits the same wall: a prompt changes, something breaks in production, and nobody knows which change caused it or what the prompt looked like before.

Git tracks text. `promptctl` tracks **behavior**. Every commit runs your eval suite and stores the score alongside the prompt. You see not just what changed, but what it cost.

```
$ promptctl commit -m "tighter tone, fewer hedges"

Running eval suite (84 test cases)...
  accuracy       84% → 66%  ▼ 18%
  faithfulness   71% → 79%  ▲ 8%
  latency        1.4s → 1.1s

Commit a3f9c2 saved. ⚠ accuracy regression detected.
Suggested rollback: e71b4a (acc: 84%)
```

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Data model](#data-model)
- [Project structure](#project-structure)
- [Tech stack](#tech-stack)
- [CLI reference](#cli-reference)
- [UI reference](#ui-reference)
- [Eval system](#eval-system)
- [CI/CD integration](#cicd-integration)
- [API reference](#api-reference)
- [Getting started](#getting-started)
- [Roadmap](#roadmap)

---

## Features

| Feature | Description |
|---|---|
| **Commit** | Save a prompt version with a message; triggers eval automatically |
| **Diff** | Line-by-line diff between any two commits, paired with score delta |
| **Rollback** | Restore any previous version in one command |
| **Eval runner** | Run a configurable test suite against any commit |
| **Score history** | Chart every metric over time; spot regressions visually |
| **Branching** | Run two prompt strategies in parallel with isolated eval tracking |
| **Branch compare** | Side-by-side metric comparison across branches |
| **CI gate** | GitHub Actions step that fails a PR if a metric drops below threshold |
| **Multi-model** | Track evals across GPT-4o, Claude, Mistral on the same prompt |
| **Web UI** | Dashboard with commit timeline, diff viewer, eval breakdown, branch compare |

---

## Architecture

```
promptctl/
├── cli/          # Typer-based CLI (promptctl commit, diff, rollback...)
├── core/         # Business logic: commit engine, diff engine, eval runner
├── storage/      # SQLite persistence layer (prompts, commits, scores, branches)
├── evals/        # Eval strategies: exact match, embedding similarity, LLM-as-judge
├── api/          # FastAPI backend — serves the web UI and external integrations
├── ui/           # React frontend — dashboard, diff viewer, branch compare
└── ci/           # GitHub Actions composite action
```

### Request flow

```
User edits prompt file
        │
        ▼
promptctl commit -m "..."
        │
        ├─► core/commit.py — hash prompt, store in SQLite
        │
        └─► core/eval_runner.py — run test suite against new commit
                │
                ├─► evals/exact_match.py
                ├─► evals/embedding_similarity.py
                └─► evals/llm_judge.py
                        │
                        ▼
                storage/db.py — persist eval scores
                        │
                        ▼
                CLI prints score diff vs previous commit
```

---

## Data model

Three tables. Keep it simple.

### `commits`

```sql
CREATE TABLE commits (
  id          TEXT PRIMARY KEY,   -- sha256 hash of prompt content (first 7 chars = short hash)
  prompt_id   TEXT NOT NULL,      -- logical name of the prompt (e.g. "customer-support")
  branch      TEXT NOT NULL DEFAULT 'main',
  content     TEXT NOT NULL,      -- full prompt text
  message     TEXT NOT NULL,      -- commit message
  model       TEXT NOT NULL,      -- e.g. "gpt-4o", "claude-sonnet-4-6"
  parent_id   TEXT,               -- previous commit id (null for first commit)
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### `eval_scores`

```sql
CREATE TABLE eval_scores (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  commit_id   TEXT NOT NULL REFERENCES commits(id),
  metric      TEXT NOT NULL,      -- e.g. "accuracy", "faithfulness", "latency"
  value       REAL NOT NULL,      -- 0.0 to 1.0 for ratios, seconds for latency
  n_cases     INTEGER NOT NULL,   -- number of test cases run
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### `test_cases`

```sql
CREATE TABLE test_cases (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  prompt_id   TEXT NOT NULL,      -- which prompt this test suite belongs to
  input       TEXT NOT NULL,      -- user message sent to the LLM
  expected    TEXT NOT NULL,      -- expected output (used by exact match and LLM judge)
  tags        TEXT,               -- optional JSON array of tags e.g. ["empathy", "refund"]
  active      BOOLEAN DEFAULT TRUE
);
```

### `branches`

```sql
CREATE TABLE branches (
  name        TEXT NOT NULL,
  prompt_id   TEXT NOT NULL,
  head_id     TEXT REFERENCES commits(id),   -- current tip commit
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (name, prompt_id)
);
```

---

## Project structure

```
promptctl/
│
├── cli/
│   ├── __init__.py
│   ├── main.py              # Typer app, registers all commands
│   ├── commands/
│   │   ├── commit.py        # promptctl commit
│   │   ├── diff.py          # promptctl diff
│   │   ├── log.py           # promptctl log
│   │   ├── rollback.py      # promptctl rollback
│   │   ├── branch.py        # promptctl branch / merge / compare
│   │   ├── eval.py          # promptctl eval (run evals manually)
│   │   └── check.py         # promptctl check (CI gate)
│   └── output.py            # Rich-based terminal formatting
│
├── core/
│   ├── commit_engine.py     # Hashing, parent chain, branch pointer updates
│   ├── diff_engine.py       # Line diff + score delta computation
│   └── eval_runner.py       # Orchestrates evals, collects scores, persists results
│
├── evals/
│   ├── base.py              # Abstract BaseEvaluator
│   ├── exact_match.py       # String equality after normalization
│   ├── embedding_sim.py     # Cosine similarity via OpenAI / local embeddings
│   └── llm_judge.py         # GPT-4o / Claude as judge (returns 0–1 score + reasoning)
│
├── storage/
│   ├── db.py                # SQLite connection, migrations
│   ├── commits.py           # CRUD for commits table
│   ├── scores.py            # CRUD for eval_scores table
│   ├── branches.py          # CRUD for branches table
│   └── test_cases.py        # CRUD for test_cases table
│
├── api/
│   ├── main.py              # FastAPI app
│   └── routes/
│       ├── commits.py       # GET /commits, GET /commits/:id
│       ├── diff.py          # GET /diff?from=&to=
│       ├── scores.py        # GET /scores/:commit_id
│       ├── branches.py      # GET /branches, POST /branches/compare
│       └── test_cases.py    # CRUD for test cases
│
├── ui/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── History.tsx      # Commit timeline
│   │   │   ├── Diff.tsx         # Side-by-side diff + score delta
│   │   │   ├── EvalReport.tsx   # Metric breakdown + failed cases
│   │   │   └── Branches.tsx     # Branch compare view
│   │   ├── components/
│   │   │   ├── CommitRow.tsx
│   │   │   ├── ScoreChip.tsx
│   │   │   ├── DiffPanel.tsx
│   │   │   ├── MetricBar.tsx
│   │   │   └── ScoreChart.tsx   # Recharts line chart over time
│   │   └── api/
│   │       └── client.ts        # Typed fetch wrappers
│   └── package.json
│
├── ci/
│   └── action.yml           # GitHub Actions composite action
│
├── tests/
│   ├── test_commit_engine.py
│   ├── test_diff_engine.py
│   ├── test_eval_runner.py
│   └── fixtures/
│       └── sample_test_cases.json
│
├── promptctl.yaml           # Project-level config (see Config section)
├── pyproject.toml
└── README.md
```

---

## Tech stack

### Backend / CLI

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Ecosystem for LLM tooling |
| CLI framework | [Typer](https://typer.tiangolo.com/) | Type-annotated, auto-help, clean UX |
| Terminal output | [Rich](https://github.com/Textualize/rich) | Diffs, tables, progress bars |
| Storage | SQLite via `sqlite3` stdlib | Zero-dependency, file-based, portable |
| HTTP API | FastAPI + Uvicorn | Async, auto OpenAPI docs |
| LLM calls | `openai` + `anthropic` SDKs | Multi-model support |
| Embeddings | `openai` (text-embedding-3-small) or local via `sentence-transformers` | Semantic similarity eval |
| Config | PyYAML | `promptctl.yaml` project config |
| Testing | pytest + pytest-asyncio | |

### Frontend

| Layer | Choice | Why |
|---|---|---|
| Framework | React + TypeScript | |
| Routing | React Router v6 | |
| Charts | Recharts | Score history line chart |
| Diff rendering | `diff` npm package | Compute line diffs client-side |
| Styling | Tailwind CSS | |
| Build | Vite | |

---

## CLI reference

### `promptctl init`

Initialize a new prompt project in the current directory.

```bash
promptctl init --name customer-support --model gpt-4o
```

Creates `promptctl.yaml` and `prompts/customer-support.txt`.

---

### `promptctl commit`

Save the current prompt and run evals.

```bash
promptctl commit -m "tighter tone, fewer hedges"
promptctl commit -m "add json output" --skip-eval       # skip eval for speed
promptctl commit -m "test" --branch feature/formal-tone # commit to a specific branch
```

**What it does:**
1. Reads the prompt file defined in `promptctl.yaml`
2. Computes SHA-256 hash of content
3. Stores commit in SQLite with parent pointer
4. Runs eval suite (unless `--skip-eval`)
5. Prints score diff vs parent commit

---

### `promptctl log`

Show commit history with scores.

```bash
promptctl log
promptctl log --branch feature/formal-tone
promptctl log --limit 10
```

Output:
```
a3f9c2  tighter tone, fewer hedges     acc ▼18%  faith ▲8%   2h ago
e71b4a  add json output instruction    acc ▲6%   faith ▲3%   1d ago
c29d11  initial system prompt          baseline              3d ago
```

---

### `promptctl diff`

Show line diff and score delta between two commits.

```bash
promptctl diff HEAD~1          # compare current vs one before
promptctl diff a3f9c2 e71b4a   # compare two specific commits
```

---

### `promptctl rollback`

Restore a previous commit as the new HEAD.

```bash
promptctl rollback HEAD~1
promptctl rollback e71b4a
```

Creates a new commit pointing to the restored content (non-destructive — history is preserved).

---

### `promptctl eval`

Run the eval suite against any commit without committing.

```bash
promptctl eval                 # eval current prompt file (not committed)
promptctl eval --commit e71b4a # eval a specific commit
promptctl eval --model claude-sonnet-4-6  # override model
```

---

### `promptctl branch`

Manage branches for A/B testing.

```bash
promptctl branch create feature/conversational
promptctl branch list
promptctl branch switch feature/conversational
promptctl branch compare main feature/conversational   # side-by-side metric table
promptctl branch merge feature/conversational          # merge winning branch to main
```

---

### `promptctl check`

CI gate — exits with code 1 if any metric is below threshold.

```bash
promptctl check --min-accuracy 0.80
promptctl check --min-accuracy 0.80 --min-faithfulness 0.70
promptctl check --commit e71b4a     # check a specific commit (default: HEAD)
```

---

## UI reference

The web UI is served by the FastAPI backend at `http://localhost:8000/ui`.

### Pages

**History** — `/`
Commit timeline. Each row shows: short hash, message, per-metric score chips (green/red delta), branch badge, timestamp. Click any row to open the diff view.

**Diff** — `/diff/:fromId/:toId`
Left/right panels showing line-level changes. Header bar shows metric deltas. Regression metrics highlighted in red.

**Eval report** — `/eval/:commitId`
Metric cards (accuracy, faithfulness, latency). Failed test cases listed with input, expected output, actual output, and score. Filter by tag.

**Branches** — `/branches`
Side-by-side metric bars for all branches. Winner highlighted. Merge and delete buttons.

**Score history** — `/history`
Line chart of each metric over time across all commits on a branch. Hover for commit details.

---

## Eval system

### Test case format

Define test cases in `test_cases.json` (or add via UI):

```json
[
  {
    "input": "What is your refund policy?",
    "expected": "Our refund policy allows returns within 30 days of purchase.",
    "tags": ["policy", "factual"]
  },
  {
    "input": "I'm really frustrated with my order.",
    "expected": "I'm sorry to hear that. Let me help resolve this for you.",
    "tags": ["empathy", "escalation"]
  }
]
```

### Eval strategies

Three built-in evaluators, each returns a score from 0.0 to 1.0:

**1. Exact match** (`evals/exact_match.py`)
After lowercasing and stripping punctuation, checks if expected string appears in the actual output. Fast and cheap. Good for structured outputs (JSON, codes, dates).

**2. Embedding similarity** (`evals/embedding_sim.py`)
Computes cosine similarity between embeddings of expected and actual output. Catches semantically correct answers with different wording. Uses `text-embedding-3-small` by default.

**3. LLM-as-judge** (`evals/llm_judge.py`)
Sends a structured prompt to a judge model (default: `gpt-4o`) asking it to rate the output on a scale from 0 to 1 on accuracy, faithfulness, and tone. Returns score + one-line reasoning. Most expensive but most accurate for complex cases.

### Configuring evals

In `promptctl.yaml`:

```yaml
evals:
  strategies:
    - exact_match          # always run
    - embedding_similarity # run if exact match fails
    - llm_judge            # run for final score
  judge_model: gpt-4o
  embedding_model: text-embedding-3-small
  metrics:
    accuracy:
      weight: 0.5
    faithfulness:
      weight: 0.3
    latency:
      weight: 0.2
  thresholds:             # used by `promptctl check`
    accuracy: 0.80
    faithfulness: 0.70
```

---

## CI/CD integration

### GitHub Actions

Add to `.github/workflows/prompt-check.yml`:

```yaml
name: Prompt eval gate

on:
  pull_request:
    paths:
      - 'prompts/**'

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install promptctl
        run: pip install promptctl

      - name: Run eval gate
        run: promptctl check --min-accuracy 0.80 --min-faithfulness 0.70
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

On failure, `promptctl check` prints which metric failed, the actual score, and the suggested rollback commit.

### PR comment bot (optional)

Add this step after the check to post a score summary as a PR comment:

```yaml
      - name: Post eval summary
        run: promptctl report --format github-comment > comment.md
        
      - uses: marocchino/sticky-pull-request-comment@v2
        with:
          path: comment.md
```

---

## Config reference (`promptctl.yaml`)

```yaml
# Project name
name: customer-support

# Prompt file to track (relative to project root)
prompt_file: prompts/customer-support.txt

# Default model for LLM calls
model: gpt-4o

# Test cases file
test_cases: test_cases.json

# Eval config (see Eval system section)
evals:
  strategies: [exact_match, embedding_similarity, llm_judge]
  judge_model: gpt-4o
  embedding_model: text-embedding-3-small
  metrics:
    accuracy: { weight: 0.5 }
    faithfulness: { weight: 0.3 }
    latency: { weight: 0.2 }
  thresholds:
    accuracy: 0.80
    faithfulness: 0.70

# SQLite database path (default: .promptctl/db.sqlite)
db_path: .promptctl/db.sqlite

# API server config
api:
  host: 0.0.0.0
  port: 8000
```

---

## API reference

The FastAPI backend auto-generates docs at `http://localhost:8000/docs`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/commits` | List all commits (filter by branch, prompt_id) |
| `GET` | `/api/commits/:id` | Get a single commit with scores |
| `GET` | `/api/diff` | `?from=<id>&to=<id>` — line diff + score delta |
| `GET` | `/api/scores/:commitId` | All eval scores for a commit |
| `GET` | `/api/scores/history` | Score over time for a prompt/branch |
| `GET` | `/api/branches` | List all branches |
| `POST` | `/api/branches/compare` | `{ branches: [a, b] }` — side-by-side metrics |
| `GET` | `/api/test-cases` | List test cases for a prompt |
| `POST` | `/api/test-cases` | Create a test case |
| `DELETE` | `/api/test-cases/:id` | Delete a test case |
| `POST` | `/api/eval` | Trigger eval run on a commit |

---

## Getting started

### Install

```bash
pip install promptctl
```

Or from source:

```bash
git clone https://github.com/yourname/promptctl
cd promptctl
pip install -e ".[dev]"
```

### Environment variables

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...   # optional, for Claude judge/model
```

### Quickstart

```bash
# 1. Init a new prompt project
mkdir my-chatbot && cd my-chatbot
promptctl init --name support-bot --model gpt-4o

# 2. Write your first prompt
echo "You are a helpful customer support agent. Be concise and empathetic." > prompts/support-bot.txt

# 3. Add test cases
promptctl test-cases add --input "What's your refund policy?" --expected "Returns accepted within 30 days."
promptctl test-cases add --input "I'm frustrated with my order." --expected "I'm sorry to hear that, let me help."

# 4. Commit and run evals
promptctl commit -m "initial prompt"

# 5. Edit and iterate
echo "You are a helpful customer support agent. Be direct and brief." > prompts/support-bot.txt
promptctl commit -m "make tone more direct"
# → will show score diff automatically

# 6. Open the UI
promptctl serve
# → http://localhost:8000/ui

# 7. Rollback if needed
promptctl rollback HEAD~1
```

---

## Roadmap

### v0.1 — MVP
- [x] `commit`, `log`, `diff`, `rollback` commands
- [x] SQLite storage
- [x] Exact match + embedding similarity evals
- [x] Rich CLI output

### v0.2 — Evals
- [ ] LLM-as-judge evaluator
- [ ] Test case management (add, list, delete, tag)
- [ ] `promptctl eval` standalone command
- [ ] Score history chart (terminal sparklines via Rich)

### v0.3 — UI
- [ ] FastAPI backend
- [ ] React UI: history, diff, eval report pages
- [ ] Score history line chart (Recharts)

### v0.4 — Branching
- [ ] `branch create / switch / compare / merge`
- [ ] Branch compare UI page

### v0.5 — CI/CD
- [ ] `promptctl check` command
- [ ] GitHub Actions composite action
- [ ] PR comment report

### v1.0 — Multi-model
- [ ] Run same eval suite against multiple models
- [ ] Model comparison view in UI
- [ ] `pip install promptctl` on PyPI

---

## Contributing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run type checking
mypy promptctl/

# Format
ruff format .
```

---

## License

MIT
