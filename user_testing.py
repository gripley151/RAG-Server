# Interactive command-line client for manually testing the RAG server --
# unlike test_endpoints.py (fixed assertions) and test_document.py (fixed
# script), this one lets you type your own documents and questions at the
# server while it's running, so you can poke at it by hand.
#
# Start the server first (docker compose up -d), then from a Windows
# terminal (cmd or PowerShell):
#     python user_testing.py
#
# Point it at the public tunnel instead of localhost:
#     set BASE_URL=https://your-tunnel.trycloudflare.com
#     python user_testing.py
# (PowerShell: $env:BASE_URL = "https://your-tunnel.trycloudflare.com")

import os
import sys

import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")

HELP = """
Commands:
  add [<source> ::] <text>
                  add a document (it gets chunked + embedded server-side),
                  optionally tagged with a source name, e.g.:
                  add Wikipedia: Foundation :: Hari Seldon develops psychohistory.
  search <query>  show the stored chunks closest to a query, with scores and sources
  ask <query>     ask a question; the model answers from retrieved chunks
  status          show server health and how many chunks are stored
  clear           wipe the in-memory index
  help            show this message
  quit / exit     leave
"""


def show_status():
    r = requests.get(f"{BASE_URL}/")
    r.raise_for_status()
    print(r.json())


def do_add(arg):
    if not arg:
        print("usage: add [<source> ::] <text>")
        return
    if " :: " in arg:
        source, _, text = arg.partition(" :: ")
        source, text = source.strip(), text.strip()
    else:
        source, text = None, arg
    r = requests.post(f"{BASE_URL}/add", json={"text": text, "source": source})
    r.raise_for_status()
    print(r.json())


def do_search(query):
    if not query:
        print("usage: search <query>")
        return
    r = requests.post(f"{BASE_URL}/search", json={"query": query})
    r.raise_for_status()
    data = r.json()
    results = data.get("results", [])
    if not results:
        print("(no results -- index is empty?)")
        return
    for i, res in enumerate(results, 1):
        tag = f" ({res['source']})" if res.get("source") else ""
        print(f"  {i}. [{res['score']:.4f}]{tag} {res['text']}")


def do_ask(query):
    if not query:
        print("usage: ask <query>")
        return
    print("  thinking...")
    r = requests.post(f"{BASE_URL}/ask", json={"query": query})
    r.raise_for_status()
    data = r.json()
    print(f"\n  Answer: {data.get('answer')}\n")
    sources = data.get("sources", [])
    if sources:
        print("  Sources:")
        for i, s in enumerate(sources, 1):
            tag = f" ({s['source']})" if s.get("source") else ""
            print(f"    {i}. [{s['score']:.4f}]{tag} {s['text']}")
    else:
        print("  Sources: (none -- nothing in the index cleared the relevance floor)")


def do_clear():
    r = requests.delete(f"{BASE_URL}/clear")
    r.raise_for_status()
    print(r.json())


def main():
    print(f"RAG-Pipe user testing -- talking to {BASE_URL}")
    try:
        show_status()
    except requests.exceptions.ConnectionError:
        print(f"Could not reach {BASE_URL} -- is the server running? (docker compose up -d)")
        sys.exit(1)
    print(HELP)

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        command, _, rest = line.partition(" ")
        command = command.lower()
        rest = rest.strip()

        try:
            if command == "add":
                do_add(rest)
            elif command == "search":
                do_search(rest)
            elif command == "ask":
                do_ask(rest)
            elif command == "status":
                show_status()
            elif command == "clear":
                do_clear()
            elif command == "help":
                print(HELP)
            elif command in ("quit", "exit"):
                break
            else:
                print(f"unknown command: {command!r} (try 'help')")
        except requests.exceptions.ConnectionError:
            print(f"Could not reach {BASE_URL} -- is the server still running?")
        except requests.exceptions.HTTPError as e:
            print(f"server returned an error: {e}")


if __name__ == "__main__":
    main()
