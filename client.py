# A tiny client for server.py.
#
# Start the server first, in another terminal:
#     uvicorn server:app --reload
#
# Then run this file:
#     python client.py

import requests

BASE_URL = "http://127.0.0.1:8000"

# Is the server up?
print(requests.get(f"{BASE_URL}/").json())

# Add two pieces of text, each tagged with where it came from. The server
# chunks and embeds each one, and stores the source tag alongside the chunks.
for text, source in [
    ("Birds are warm-blooded animals with feathers, and most of them can fly.", "Bird facts"),
    (
        "Penguins are birds that cannot fly. They swim instead, and an emperor penguin "
        "can stand over a metre tall.",
        "Penguin facts",
    ),
]:
    response = requests.post(f"{BASE_URL}/add", json={"text": text, "source": source})
    print(response.json())

# Ask questions. The server returns the stored text closest in meaning.
for query in ["How tall can a penguin get?", "Do birds have feathers?"]:
    response = requests.post(f"{BASE_URL}/search", json={"query": query})
    print(f"\nQ: {query}")
    for result in response.json()["results"]:
        print(f"   {result['score']:.4f}  ({result['source']})  {result['text']}")

# Ask a question and get a language-model answer, backed by the sources it used.
query = "How tall can a penguin get?"
response = requests.post(f"{BASE_URL}/ask", json={"query": query})
data = response.json()
print(f"\nAsk: {query}")
print(f"Answer: {data['answer']}")
for source in data["sources"]:
    print(f"   source ({source['score']:.4f}, {source['source']}): {source['text']}")
