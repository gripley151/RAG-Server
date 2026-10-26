# RAG-Pipe

A small retrieval-augmented generation (RAG) server. It stores text, finds the
chunks that match a question, and uses a language model (served locally by
Ollama) to answer the question from those chunks — returning both the answer
and the chunks it used as sources.

Built on top of the course's RAG-Pipe starter code (`/add`, `/search`), with a
new `/ask` endpoint added for generation, plus Docker and Cloudflare Tunnel
packaging.

## Start the server with Docker

Everything — the FastAPI server, the embedding model, and the Ollama language
model — starts with one command. No local Python environment or local Ollama
install needed.

```
docker compose up -d
```

First run only: this builds the server image, pulls the `ollama/ollama`
image, and the `ollama` container automatically pulls the `llama3.2:1b`
model it uses (~1.3 GB, one-time download, cached in a Docker volume after
that). Check readiness with:

```
docker compose exec ollama ollama list
```

Once `llama3.2:1b` shows up in that list, the server is ready at
`http://localhost:8000`. Confirm with:

```
curl http://localhost:8000/
# {"status":"ok","documents_stored":0}
```

To stop everything: `docker compose down` (add `-v` to also delete the
downloaded model).

## Open the tunnel

With the containers running, make the server reachable from the internet:

```
cloudflared tunnel --url http://localhost:8000
```

This prints a public `https://<random-words>.trycloudflare.com` URL in the
terminal — no Cloudflare account needed. Leave this running for as long as
the server needs to be reachable; closing it (or the server) ends the public
URL.

## Endpoints

### `POST /add` — chunk and store a document

`source` is optional — a free-text label (a title, filename, URL, anything
that identifies where the text came from). It's stored alongside every chunk
produced from that text and returned later by `/search` and `/ask`, so the
caller can see not just *which chunk* answered a question but *which
original document* it came from. Omit it and chunks are stored with
`source: null`.

```
curl -X POST http://localhost:8000/add \
  -H "Content-Type: application/json" \
  -d '{"text": "Penguins are birds that cannot fly. They swim instead, and an emperor penguin can stand over a metre tall.", "source": "Penguin facts"}'
```

```json
{"message": "added", "total_documents": 1}
```

### `POST /search` — find the stored chunks closest to a query

```
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "How tall can a penguin get?"}'
```

```json
{"query":"How tall can a penguin get?","results":[{"text":"penguins are birds that cannot fly. they swim instead, and an emperor penguin can stand over a metre tall.","score":0.78,"source":"Penguin facts"},{"text":"birds are warm - blooded animals with feathers, and most of them can fly.","score":0.5292,"source":"Bird facts"}]}
```

### `POST /ask` — get an answer, grounded in the retrieved chunks

```
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "How tall can a penguin get?"}'
```

```json
{
  "query": "How tall can a penguin get?",
  "answer": "According to the context, an emperor penguin can stand over a metre tall.",
  "sources": [
    {"text": "penguins are birds that cannot fly. they swim instead, and an emperor penguin can stand over a metre tall.", "score": 0.78, "source": "Penguin facts"}
  ]
}
```

(The bird-facts chunk shows up in `/search` above since that endpoint returns raw top-k, but `/ask` filters it out here — its score falls below `MIN_ASK_SCORE`, so it's not relevant enough to use as context for this specific question.)

`/ask` is grounded in the retrieved chunks, not the model's own training data —
asking something the indexed documents don't cover gets a refusal instead of a
guess, and an empty `sources` list (nothing cleared the relevance floor):

```
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of France?"}'
```

```json
{"query":"What is the capital of France?","answer":"I don't know -- nothing in the indexed documents looks relevant to this question.","sources":[]}
```

### `DELETE /clear` — empty the in-memory index

```
curl -X DELETE http://localhost:8000/clear
```

## Testing

`test_endpoints.py` is a smoke test that exercises every endpoint against a
running server and prints a pass/fail line for each check — the proof the
server behaves as expected, not just that it doesn't crash:

```
python test_endpoints.py
```

```
PASS  GET / returns 200
PASS  GET / reports zero documents after clear
PASS  POST /add (doc 1) returns 200
PASS  POST /add (doc 1) reports 1 total document
PASS  POST /add (doc 2) reports 2 total documents
PASS  POST /search returns 200
PASS  POST /search returns at least one result
PASS  POST /search's top result is the penguin chunk, not the birds chunk
PASS  POST /search's top result carries its source tag
PASS  POST /search's top result scores higher than the second
PASS  POST /ask returns 200
PASS  POST /ask's answer mentions a correct height (metre/meter)
PASS  POST /ask returns non-empty sources
PASS  POST /ask's top source is the penguin chunk
PASS  POST /ask doesn't invent an answer when its documents don't contain one
PASS  POST /ask's sources exclude unrelated documents even when the index holds them
PASS  POST /ask still answers correctly with unrelated documents in the index
PASS  DELETE /clear returns 200
PASS  GET / reports zero documents after /clear
PASS  POST /search after /clear returns no results

20 passed, 0 failed
```

It can also point at the public tunnel instead of localhost, to prove the
internet-facing server works, not just the local one. `client.py`,
`load_squad.py`, `test_document.py`, and `user_testing.py` all honor this
the same way:

```
# bash/macOS/Linux
BASE_URL=https://your-tunnel.trycloudflare.com python test_endpoints.py

# PowerShell
$env:BASE_URL = "https://your-tunnel.trycloudflare.com"
python test_endpoints.py
```

`client.py` runs the birds/penguins demo above end-to-end against a running
server, tagging each document with a `source` (`"Bird facts"`, `"Penguin
facts"`) and printing it alongside each result (`python client.py`). `load_squad.py` downloads a small slice of
SQuAD (Wikipedia paragraphs paired with real questions and known answers),
tags each paragraph with a `source` like `"SQuAD: <article title> (paragraph
N)"`, and checks the server's `/ask` answers against SQuAD's own expected
answers — in testing, all 5 sample questions got answers matching SQuAD's
golden answers (`python load_squad.py`).

`test_document.py` is the most thorough check: it loads a real 5-paragraph
document (how metal detectors work), tagging each paragraph with its section
title (`"History"`, `"How it works"`, etc.) as its `source`, and asks a
graduated set of questions —
easy single-fact lookups, medium paraphrased/numeric questions, hard
multi-hop questions whose answer spans two paragraphs, one inference
question whose answer isn't written anywhere verbatim, and two trick
questions (an unanswerable spec question, and a false-premise question) to
confirm the server refuses rather than invents an answer. Run it with
`python test_document.py`. In testing: all 8 fact-based questions (easy
through hard multi-hop, plus both trick questions) got correct, grounded
answers. The one inference question — "would a Pi-based ML audio classifier
build on VLF or PI hardware, and why?" — got a directionally reasonable
answer (VLF) but the model's justification mostly restated a retrieved
paragraph rather than genuinely connecting discrimination capability to the
classification use case. That's a real limitation of using a 1B-parameter
model for synthesis, not a retrieval or prompting bug — worth knowing before
the live grading session, in case a question like that comes up.

`user_testing.py` is for poking at the server by hand instead of running a
fixed script — a small interactive command-line client with `add`,
`search`, `ask`, `status`, and `clear` commands. `add` optionally takes a
`<source> :: <text>` form to tag the document, the same way the other
clients do:

```
python user_testing.py
```

```
RAG-Pipe user testing -- talking to http://127.0.0.1:8000
{'status': 'ok', 'documents_stored': 0}
> add Penguin facts :: Penguins are birds that cannot fly. They swim instead, and an emperor penguin can stand over a metre tall.
{'message': 'added', 'total_documents': 1}
> ask how tall can a penguin get
  Answer: According to the context, an emperor penguin can stand over a metre tall.
  Sources:
    1. [0.7788] (Penguin facts) penguins are birds that cannot fly. they swim instead, and an emperor penguin can stand over a metre tall.
```

It also honors `BASE_URL`, so the same tool can be pointed at the
Cloudflare tunnel to test the public endpoint by hand:

```
# bash/macOS/Linux
BASE_URL=https://your-tunnel.trycloudflare.com python user_testing.py

# PowerShell
$env:BASE_URL = "https://your-tunnel.trycloudflare.com"
python user_testing.py
```

## Design notes

- Embedding model: `BAAI/bge-small-en-v1.5`, chosen deliberately off the
  MTEB leaderboard rather than left at the starter code's default
  (`all-MiniLM-L6-v2`). It scores noticeably higher than MiniLM on the
  leaderboard's retrieval benchmarks specifically, while staying the same
  size class (~130 MB, 384-dim) — same CPU/Docker cost, better-tuned for
  exactly what this server needs (ranking passages against a query). The
  one implementation detail that comes with it: bge models expect an
  instruction prefix ("Represent this sentence for searching relevant
  passages: ") on the query side only, not on stored documents — handled
  in `retrieve()`. Baked into the Docker image at build time so `/add` has
  no first-request download delay.
- Chunking: 1000-token chunks with 200-token overlap, so a sentence that
  falls on a chunk boundary still appears intact in at least one chunk.
- Retrieval: cosine similarity over an in-memory list (`TOP_K = 4` for
  `/search`). No persistent database — the index resets whenever the server
  restarts, which is fine at homework scale.
- `/ask`'s sources are filtered by a relevance floor (`MIN_ASK_SCORE = 0.3`),
  not just "whatever the top-k happened to be." Found this the hard way:
  with a fixed top-k and no floor, adding a few unrelated documents (Mount
  Everest, Python, the Eiffel Tower) alongside the penguin one made `/ask`
  report those irrelevant chunks as "sources" for a penguin question, *and*
  the noise in the context made the model wrongly answer "I don't know"
  even though the correct chunk was right there. Filtering by score before
  building the prompt fixed both the mislabeled sources and the answer
  quality. `test_endpoints.py` has a regression check for this.
- Language model: `llama3.2:1b` via Ollama, run as its own `docker compose`
  service (`ollama`) so the whole stack starts with Docker alone. The
  `rag-server` container reaches it at `http://ollama:11434` over the
  compose network.
- `/ask` uses Ollama's `/api/chat` endpoint (system + user messages) rather
  than `/api/generate` with a single raw prompt string — `/api/generate`
  made this model answer "I don't know" even when the retrieved context
  clearly contained the answer.
- `/ask` calls Ollama with `temperature: 0`. At default temperature, asking
  the exact same grounded question repeatedly gave a different answer each
  time, including one outright wrong one that contradicted its own provided
  context. `temperature: 0` makes it deterministic.
- The system prompt explicitly asks the model to quote/paraphrase the
  context rather than telling it "say you don't know if the answer isn't
  there" — counterintuitively, the explicit don't-know instruction made this
  small model refuse to answer questions it *could* answer correctly; the
  quote-only instruction gets both correct answers and accurate natural
  refusals (e.g. "There is no mention of X in the provided context").

## AI Use Statement

I used Claude Code throughout this assignment as a coding assistant, and I
reviewed and tested everything it produced against the running containers
before accepting it.

- I used it to design and implement the `/ask` endpoint (retrieval plus the
  Ollama integration), starting from the existing `/add`/`/search` starter
  code.
- I used it to debug several model-behavior issues I found through live
  testing: `/api/generate` vs. `/api/chat` prompting, a fixed-top-k source
  list that wrongly included irrelevant documents once the index held
  unrelated text (fixed with a relevance-score floor), answer
  nondeterminism at default temperature (fixed with `temperature: 0`), and
  an explicit "say you don't know" instruction that paradoxically made the
  model refuse answerable questions (fixed by asking it to quote/paraphrase
  instead). I verified each fix by re-running the test suite and the live
  containers myself.
- I used it to write the Dockerfile and docker-compose setup (including the
  Ollama entrypoint script that auto-pulls the model on first start),
  `test_endpoints.py`, `test_document.py`, `user_testing.py`, and this
  README, and I ran all of it against my own containers to confirm the
  documented behavior matches reality.
- All architectural decisions (model choice, chunking parameters, the
  relevance-score floor, temperature setting) were made and verified by me
  based on observed test results, not accepted blindly from suggestions.
