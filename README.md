# Campus Customs: Yale merch store with an AI shopping assistant (MGT 409, HW 4)

A customer website for Campus Customs: a **React + Vite + TypeScript** front end and a **Python FastAPI** backend whose shopping assistant is a **PydanticAI agent**. Shoppers can browse products, create an account, chat about merch, see matching items appear on the page, and get honest price and stock answers from a local database.

## Layout

```
hw4/
├── AI_prompts.md            # log of the prompts used to build this project
├── requirements.txt         # Python packages for the backend
├── .env.example             # copy to .env and add your API key
├── .gitignore               # keeps .env, data/, .venv, node_modules out of git
├── README.md
├── frontend/                # Vite React TypeScript app
├── backend/
│   ├── main.py              # FastAPI app: run with uvicorn main:app --reload --port 8000
│   ├── agent.py             # agent wiring, sanity checks, audit trail
│   ├── models.py            # Pydantic / PydanticAI types
│   ├── tools.py             # read-only tools the agent can call
│   ├── prompts/prompt.md    # system prompt (voice, tool rules, safety rules)
│   ├── auth.py              # sign up / log in (hashed passwords, session cookie)
│   └── clean_images.py      # optional: smooths the product photos
└── output/
    ├── harness.md           # how the whole system works (models, tools, safety, specs)
    ├── design.md            # design choices and why
    ├── usability.md         # usability improvements and why
    ├── app_check.html       # live test report (open in a browser)
    ├── app_check_images/    # screenshots linked from app_check.html
    └── audit_trail.json     # append-only log of every agent run
```

## 1. Place the data pack (not in git)

Put the course data pack in `data/` next to `backend/`:

```
hw4/data/
├── campus_customs.db
└── products/          # images referenced by the catalogue
```

## 2. Set up once

Requires Python 3.12+ and Node 20+.

```bash
cd hw4
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then edit .env and set PORTKEY_API_KEY
cd frontend && npm install && cd ..
```

Optional: `.venv/bin/python backend/clean_images.py` creates smoother copies of the product photos in `data/products_clean/` (the site falls back to the originals without it).

## 3. Run the back end and front end

Use two terminals.

```bash
# Terminal 1: backend API + agent (http://localhost:8000)
cd hw4
source .venv/bin/activate
cd backend
uvicorn main:app --reload --port 8000
```

```bash
# Terminal 2: website (http://localhost:5173)
cd hw4/frontend
npm run dev
```

Open **http://localhost:5173**. The Vite dev server forwards `/api` and `/media` to the backend.

**Try it:** click the bulldog chat button and ask "What hoodies do you have?" (matching items appear on the page), open a product and ask "Is this in stock in my size?", or log in with the seed test user `test@campuscustoms.yale.edu` / `password`.

On first start the backend adds a few tables to `campus_customs.db` (`sessions`, `chat_runs`, `chat_feedback`) and two columns to `chat_messages`; the original data is kept.

## Configuration (`.env`)

| Variable | Meaning |
|---|---|
| `PORTKEY_API_KEY` | Your Portkey gateway key (required for the agent) |
| `PORTKEY_BASE_URL` | Default `https://api.portkey.ai/v1` |
| `MODEL_NAME` | Default `gpt-6-luna` (any OpenAI 5.6 or 6 series model available through Portkey) |

More detail on every part of the system is in [`output/harness.md`](output/harness.md).
