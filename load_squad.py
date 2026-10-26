# Loads a small slice of SQuAD (Wikipedia paragraphs with real questions and
# known answers) into the running RAG server, then asks a handful of the real
# questions and shows how the server's answer compares to SQuAD's own
# expected answer. This is the "did /search and /ask actually work" check
# that SQuAD gives you for free and the other datasets in the assignment don't.
#
# Start the server first (see README), then run:
#     python load_squad.py

import os

import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
SQUAD_URL = "https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v1.1.json"
NUM_PARAGRAPHS = 5       # how many SQuAD paragraphs to index
QUESTIONS_PER_PARAGRAPH = 2

print("Downloading a slice of SQuAD...")
squad = requests.get(SQUAD_URL, timeout=60).json()
article = squad["data"][0]
article_title = article["title"]
paragraphs = article["paragraphs"][:NUM_PARAGRAPHS]

qa_pairs = []
for i, paragraph in enumerate(paragraphs, 1):
    source = f"SQuAD: {article_title} (paragraph {i})"
    response = requests.post(f"{BASE_URL}/add", json={"text": paragraph["context"], "source": source})
    print(response.json())
    for qa in paragraph["qas"][:QUESTIONS_PER_PARAGRAPH]:
        qa_pairs.append((qa["question"], qa["answers"][0]["text"]))

print(f"\nLoaded {len(paragraphs)} paragraphs, {len(qa_pairs)} sample questions. Asking a few:\n")
for question, expected in qa_pairs[:5]:
    response = requests.post(f"{BASE_URL}/ask", json={"query": question})
    data = response.json()
    print(f"Q: {question}")
    print(f"   expected (SQuAD): {expected}")
    print(f"   server answer:    {data['answer']}")
    if data["sources"]:
        top = data["sources"][0]
        print(f"   top source [{top.get('source')}] ({top['score']:.4f}): {top['text'][:120]}...")
    print()
