# A super simple RAG-style server.
#
# Run it with:
#     uvicorn server:app --reload
#
# Then open http://127.0.0.1:8000/docs in your browser to try every endpoint.

import os

import numpy as np
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, util

app = FastAPI(title="My Simple RAG Server")

OVERLAP = 0.20
MAX_CHUNK_SIZE = 1000
TOP_K = 4

# /ask drops retrieved chunks below this cosine-similarity score before
# building the LLM's context -- without this, a fixed top-k forces in
# irrelevant chunks whenever the index holds unrelated documents, which both
# mislabels them as "sources" and confuses the model into under-answering.
MIN_ASK_SCORE = 0.3

# Where to reach the language model. Inside docker compose this is the
# "ollama" service name; set OLLAMA_URL to override for local/non-Docker runs.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")


# Load a small, fast embedding model (downloads once, ~90 MB).
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
tokenizer = model.tokenizer

# Our "database": just a Python list held in memory.
# Each item looks like: {"text": "...", "embedding": <vector>}
documents = [
    # {"text": "<some text>", "embedding": <>}
]


# ---- Request shapes (what the client must send) ----

class AddRequest(BaseModel):
    text: str
    source: str | None = None


class AddManyRequest(BaseModel):
    texts: list[str]


class SearchRequest(BaseModel):
    query: str
    #top_k: int = 3


class AskRequest(BaseModel):
    query: str


# ---- Endpoints (the URLs the client can call) ----

@app.get("/")
def health_check():
    """Is the server alive?"""
    return {"status": "ok", "documents_stored": len(documents)}


@app.post("/add")
def add_document(request: AddRequest):
    print(request.text)
    # count how much token there are in original request


    def chunk_text(text, chunk_size=50, overlap=0):
        # Tokenize without [CLS]/[SEP]; the model adds those itself when encoding
        ids = tokenizer.encode(text, add_special_tokens=False)
        step = chunk_size - overlap
        chunks = []
        for i in range(0, len(ids), step):
            chunk_ids = ids[i:i + chunk_size]
            chunks.append(tokenizer.decode(chunk_ids, skip_special_tokens=True))
            if i + chunk_size >= len(ids):
                break
        return chunks
    
    chunks = chunk_text(text=request.text,chunk_size= MAX_CHUNK_SIZE, overlap=int(MAX_CHUNK_SIZE*OVERLAP))
    embeddings = model.encode(chunks)

    assert len(chunks) == len(embeddings)

    for chunk, embedding in zip(chunks, embeddings):
        documents.append({"text": chunk, "embedding": embedding, "source": request.source})


    return {"message": "added", "total_documents": len(documents)}


# @app.post("/add_many")
# def add_many_documents(request: AddManyRequest):

#     return {"message": f"added {len(request.texts)}", "total_documents": len(documents)}


def retrieve(query: str, top_k: int = TOP_K):
    if not documents:
        return []

    # embed the search text
    query_embedding = model.encode(query)

    # run similarity against every stored chunk -> shape (num_docs,)
    doc_embeddings = np.stack([doc["embedding"] for doc in documents])
    scores = model.similarity(query_embedding, doc_embeddings).flatten()

    # retrieve top k text
    top = scores.topk(min(top_k, len(scores)))
    return [
        {
            "text": documents[i]["text"],
            "score": round(s, 4),
            "source": documents[i].get("source"),
        }
        for s, i in zip(top.values.tolist(), top.indices.tolist())
    ]


@app.post("/search")
def search(request: SearchRequest):
    return {"query": request.query, "results": retrieve(request.query)}


@app.post("/ask")
def ask(request: AskRequest):
    sources = [s for s in retrieve(request.query) if s["score"] >= MIN_ASK_SCORE]
    if not sources:
        return {
            "query": request.query,
            "answer": "I don't know -- nothing in the indexed documents looks relevant to this question.",
            "sources": [],
        }

    context = "\n\n".join(source["text"] for source in sources)
    messages = [
        {
            "role": "system",
            # Tested against this 1b model specifically: an explicit "say you
            # don't know if the context doesn't have it" instruction made it
            # refuse to answer *correctly-grounded* questions too -- asking
            # it to quote/paraphrase instead gets both correct answers and
            # natural, accurate refusals on unsupported questions.
            "content": "Answer the question using only facts stated in the context below. "
            "Quote or closely paraphrase the relevant sentence from the context.",
        },
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {request.query}"},
    ]

    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        # temperature=0: this is a small model and sampling noise was observed
        # to make it occasionally contradict its own provided context (e.g.
        # inventing a different height than the one in the source chunk).
        # Deterministic decoding is worth more here than varied phrasing.
        json={"model": OLLAMA_MODEL, "messages": messages, "stream": False, "options": {"temperature": 0}},
        timeout=120,
    )
    response.raise_for_status()
    answer = response.json()["message"]["content"].strip()

    return {"query": request.query, "answer": answer, "sources": sources}


@app.delete("/clear")
def clear_documents():
    documents.clear()
    return {"message": "cleared"}



# request = AddRequest(text="pengiuns are 50cm across")
# add_document(request)
# request = AddRequest(text="birds are 20cm across")
# add_document(request)
# request = SearchRequest(query="how wide are penguins")
# search(request)
