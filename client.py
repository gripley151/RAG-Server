# A tiny client for server.py.
#
# Start the server first, in another terminal:
#     uvicorn server:app --reload
#
# Then run this file:
#     python client.py

import os

import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")

# Is the server up?
print(requests.get(f"{BASE_URL}/").json())

# Add two pieces of text, each tagged with where it came from. The server
# chunks and embeds each one, and stores the source tag alongside the chunks.
for text, source in [
    (
        "In Isaac Asimov's I, Robot, robots must obey the Three Laws of Robotics: "
        "a robot may not injure a human being, a robot must obey orders from human "
        "beings, and a robot must protect its own existence, in that order of priority.",
        "I, Robot facts",
    ),
    (
        "In Isaac Asimov's Foundation, the mathematician Hari Seldon develops "
        "psychohistory, a science that predicts the behavior of large populations, "
        "and uses it to foresee the collapse of the Galactic Empire.",
        "Foundation facts",
    ),
]:
    response = requests.post(f"{BASE_URL}/add", json={"text": text, "source": source})
    print(response.json())

# Ask questions. The server returns the stored text closest in meaning.
for query in ["What are the Three Laws of Robotics?", "What is psychohistory?"]:
    response = requests.post(f"{BASE_URL}/search", json={"query": query})
    print(f"\nQ: {query}")
    for result in response.json()["results"]:
        print(f"   {result['score']:.4f}  ({result['source']})  {result['text']}")

# Ask a question and get a language-model answer, backed by the sources it used.
query = "What are the Three Laws of Robotics?"
response = requests.post(f"{BASE_URL}/ask", json={"query": query})
data = response.json()
print(f"\nAsk: {query}")
print(f"Answer: {data['answer']}")
for source in data["sources"]:
    print(f"   source ({source['score']:.4f}, {source['source']}): {source['text']}")
