# Smoke-tests every endpoint against a running server and prints what it
# checked, pass or fail. This is the proof-of-working script referenced in
# the README.
#
# Start the server first (docker compose up -d), then:
#     python test_endpoints.py
#
# Point it at the public tunnel instead of localhost to prove the
# internet-facing server works too:
#     BASE_URL=https://your-tunnel.trycloudflare.com python test_endpoints.py

import os
import sys

import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}\n      {detail}")


# ---- start from a clean index ----
requests.delete(f"{BASE_URL}/clear")

# ---- health check ----
r = requests.get(f"{BASE_URL}/")
check("GET / returns 200", r.status_code == 200, r.text)
check("GET / reports zero documents after clear", r.json().get("documents_stored") == 0, r.text)

# ---- /add ----
r1 = requests.post(
    f"{BASE_URL}/add",
    json={
        "text": "Birds are warm-blooded animals with feathers, and most of them can fly.",
        "source": "Birds doc",
    },
)
check("POST /add (doc 1) returns 200", r1.status_code == 200, r1.text)
check("POST /add (doc 1) reports 1 total document", r1.json().get("total_documents") == 1, r1.text)

r2 = requests.post(
    f"{BASE_URL}/add",
    json={
        "text": "Penguins are birds that cannot fly. They swim instead, and an emperor "
        "penguin can stand over a metre tall.",
        "source": "Penguin doc",
    },
)
check("POST /add (doc 2) reports 2 total documents", r2.json().get("total_documents") == 2, r2.text)

# ---- /search ----
r = requests.post(f"{BASE_URL}/search", json={"query": "How tall can a penguin get?"})
check("POST /search returns 200", r.status_code == 200, r.text)
results = r.json().get("results", [])
check("POST /search returns at least one result", len(results) > 0, r.text)
check(
    "POST /search's top result is the penguin chunk, not the birds chunk",
    bool(results) and "penguin" in results[0]["text"].lower(),
    results,
)
check(
    "POST /search's top result carries its source tag",
    bool(results) and results[0].get("source") == "Penguin doc",
    results,
)
check(
    "POST /search's top result scores higher than the second",
    len(results) < 2 or results[0]["score"] >= results[1]["score"],
    results,
)

# ---- /ask: grounded question (the answer is in the indexed documents) ----
r = requests.post(f"{BASE_URL}/ask", json={"query": "How tall can a penguin get?"})
check("POST /ask returns 200", r.status_code == 200, r.text)
data = r.json()
answer = data.get("answer", "").lower()
check(
    "POST /ask's answer mentions a correct height (metre/meter)",
    "metre" in answer or "meter" in answer,
    data,
)
check("POST /ask returns non-empty sources", len(data.get("sources", [])) > 0, data)
check(
    "POST /ask's top source is the penguin chunk",
    bool(data.get("sources")) and "penguin" in data["sources"][0]["text"].lower(),
    data.get("sources"),
)

# ---- /ask: ungrounded question (nothing indexed answers this) ----
r = requests.post(f"{BASE_URL}/ask", json={"query": "What is the capital of France?"})
data = r.json()
answer = data.get("answer", "").lower()
check(
    "POST /ask doesn't invent an answer when its documents don't contain one",
    any(
        phrase in answer
        for phrase in ["don't know", "do not know", "no documents", "no mention", "doesn't", "cannot", "can't"]
    ),
    data,
)

# ---- /ask: sources stay relevant even when the index also holds unrelated
#      documents (a fixed top-k would otherwise force in irrelevant chunks
#      and report them as "sources" the answer didn't actually draw on) ----
for text, source in [
    ("The Eiffel Tower is a wrought-iron lattice tower in Paris, France, completed in 1889.", "Eiffel Tower doc"),
    ("Python is a high-level programming language known for readable syntax.", "Python doc"),
    ("Mount Everest is the tallest mountain above sea level, located in the Himalayas.", "Everest doc"),
]:
    requests.post(f"{BASE_URL}/add", json={"text": text, "source": source})

r = requests.post(f"{BASE_URL}/ask", json={"query": "How tall can a penguin get?"})
data = r.json()
source_texts = " ".join(s["text"].lower() for s in data.get("sources", []))
check(
    "POST /ask's sources exclude unrelated documents even when the index holds them",
    "penguin" in source_texts and "everest" not in source_texts and "python" not in source_texts,
    data.get("sources"),
)
check(
    "POST /ask still answers correctly with unrelated documents in the index",
    "metre" in data.get("answer", "").lower() or "meter" in data.get("answer", "").lower(),
    data,
)

# ---- /clear ----
r = requests.delete(f"{BASE_URL}/clear")
check("DELETE /clear returns 200", r.status_code == 200, r.text)
r = requests.get(f"{BASE_URL}/")
check("GET / reports zero documents after /clear", r.json().get("documents_stored") == 0, r.text)
r = requests.post(f"{BASE_URL}/search", json={"query": "anything"})
check("POST /search after /clear returns no results", r.json().get("results") == [], r.text)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
