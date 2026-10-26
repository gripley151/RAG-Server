# A real client test: loads a multi-paragraph document into the RAG server,
# then asks it a graduated set of questions -- starting with easy, single-fact
# lookups and working up through multi-hop questions (the answer spans two
# paragraphs), one inference question (the answer isn't stated anywhere
# verbatim, it has to be synthesized), and deliberate trick questions (an
# unanswerable spec question, and a false-premise question) to check the
# server doesn't just make something up when it can't actually answer.
#
# Start the server first (see README), then run:
#     python test_document.py

import os

import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")

# ---- The document, as five standalone paragraphs (about metal detectors --
# chosen because it supports genuinely multi-hop and inference questions,
# not just more bird facts). Each paragraph is added separately, as the
# starter client.py does, rather than as one giant /add call. ----

DOCUMENT = [
    (
        "History",
        "The first patent for a metal-detecting device was awarded in 1881 to Alexander "
        "Graham Bell, who built it in an unsuccessful attempt to locate a bullet lodged in "
        "President James Garfield after an assassination attempt. Portable metal detectors "
        "as a widely used hobbyist tool emerged after World War II, when ex-military "
        "personnel adapted mine-detection technology for treasure hunting. Gerhard Fischer, "
        "a German-American engineer, patented one of the first practical, commercially sold "
        "metal detectors in 1925 and later founded Fisher Research Laboratory, a company "
        "still making detectors today.",
    ),
    (
        "How it works",
        "A metal detector works through electromagnetic induction. A coil inside the "
        "detector's search head is energized with an alternating electric current, which "
        "creates an oscillating magnetic field around the coil. When that magnetic field "
        "passes over a conductive metal object, it induces small electric currents, called "
        "eddy currents, inside the object. Those eddy currents generate their own secondary "
        "magnetic field, which the detector's receiver coil picks up as a disturbance. The "
        "detector's circuitry converts that disturbance into an audible tone or a visual "
        "signal, alerting the operator that metal is nearby.",
    ),
    (
        "VLF vs. Pulse Induction",
        "Most hobbyist metal detectors use one of two main technologies. Very Low Frequency "
        "(VLF) detectors, the most common type, transmit a continuous signal, typically "
        "between 3 kHz and 30 kHz, and can often distinguish between different kinds of "
        "metal, a feature called discrimination, by analyzing the phase shift between the "
        "transmitted and received signal. Pulse Induction (PI) detectors instead send short, "
        "powerful bursts of current through the coil and measure how long it takes the "
        "induced eddy currents to decay. PI detectors generally cannot discriminate between "
        "metal types as well as VLF detectors, but they are far less affected by mineralized "
        "or salty ground, which makes them popular for beach and gold-prospecting detectors "
        "in highly mineralized soil.",
    ),
    (
        "Limitations",
        "Ground mineralization is one of the biggest challenges for metal detecting. Soils "
        "with a high iron oxide content, common in many gold-bearing regions, generate their "
        "own magnetic response that can mimic or mask the signal from a real target, "
        "confusing a detector's circuitry. This is often called 'ground noise' or 'chatter.' "
        "Detectors address this with a feature called ground balance, which tunes the device "
        "to ignore the magnetic response of the mineralized soil itself while still picking "
        "up genuine metal targets. Another common limitation is trash discrimination: in "
        "areas with lots of bottle caps, pull tabs, and foil, even a well-tuned detector "
        "produces frequent false signals, which is why experienced users rely on both the "
        "detector's discrimination settings and the sound of the tone to judge whether a "
        "target is worth digging.",
    ),
    (
        "Modern advances",
        "Modern metal detectors increasingly use digital signal processing and onboard "
        "microprocessors instead of purely analog circuitry, which allows for "
        "multi-frequency operation, transmitting and analyzing several frequencies "
        "simultaneously to improve both depth and discrimination across different soil "
        "types. Some newer consumer detectors include wireless audio, smartphone app "
        "connectivity, and customizable discrimination profiles. There is also growing "
        "hobbyist and research interest in applying machine learning directly to a "
        "detector's raw audio or signal data, training a classifier to recognize the "
        "acoustic signature of specific target types in real time on small embedded devices "
        "like a Raspberry Pi, rather than relying solely on the manufacturer's built-in "
        "discrimination circuitry.",
    ),
]

# ---- Questions, easy to hard. "expect" is a loose check (a substring that
# should appear for a correct answer), not an exact match -- the model
# phrases things in its own words. "hop" notes which paragraph(s) the answer
# actually requires, so it's visible when a question needed more than one. ----

QUESTIONS = [
    {
        "level": "1. Easy -- single fact, exact wording in the source",
        "query": "What physical principle do metal detectors use to sense metal?",
        "hop": "How it works",
        "expect": ["electromagnetic induction"],
    },
    {
        "level": "1. Easy -- single fact, exact wording in the source",
        "query": "Who built an early metal-detecting device to try to find a bullet in President Garfield?",
        "hop": "History",
        "expect": ["bell"],
    },
    {
        "level": "2. Medium -- single chunk, but asked in different words than the text uses",
        "query": "Why does a buried metal object cause a signal in the detector's coil at all?",
        "hop": "How it works",
        "expect": ["eddy current"],
    },
    {
        "level": "2. Medium -- single chunk, specific number",
        "query": "What's the typical frequency range for a VLF metal detector?",
        "hop": "VLF vs. Pulse Induction",
        "expect": ["3", "30"],
    },
    {
        "level": "3. Hard -- multi-hop, needs two paragraphs combined",
        "query": "Why would someone hunting for gold in heavily mineralized soil prefer a "
        "pulse induction detector over a VLF detector?",
        "hop": "VLF vs. Pulse Induction + Limitations",
        "expect": ["mineral"],
    },
    {
        "level": "3. Hard -- multi-hop, needs two paragraphs combined",
        "query": "What feature helps a VLF detector cope with the ground noise caused by "
        "mineralized soil?",
        "hop": "Limitations + VLF vs. Pulse Induction",
        "expect": ["ground balance"],
    },
    {
        "level": "4. Inference -- answer isn't stated verbatim anywhere, has to be synthesized",
        "query": "Would a hobbyist machine-learning project classifying metal-detector audio "
        "on a Raspberry Pi most naturally build on VLF or PI detector hardware, and why?",
        "hop": "VLF vs. Pulse Induction + Modern advances (synthesis, not a direct quote)",
        "expect": [],  # no simple substring check -- read this one yourself
    },
    {
        "level": "5. Trick -- unanswerable, specific product spec not in the document",
        "query": "What is the battery life of the Minelab Equinox 800?",
        "hop": "none -- should refuse",
        "expect": ["no mention", "don't know", "do not know", "not", "n/a", "cannot"],
    },
    {
        "level": "5. Trick -- false premise, nothing in the document supports this",
        "query": "In what year were metal detectors banned in the United States?",
        "hop": "none -- should refuse, not invent a year",
        "expect": ["no mention", "don't know", "do not know", "not", "n/a", "cannot"],
    },
]


def main():
    print(f"Clearing index and loading {len(DOCUMENT)} paragraphs...\n")
    requests.delete(f"{BASE_URL}/clear")
    for title, text in DOCUMENT:
        r = requests.post(f"{BASE_URL}/add", json={"text": text, "source": title})
        print(f"  added '{title}' -> {r.json()}")

    print()
    for q in QUESTIONS:
        r = requests.post(f"{BASE_URL}/ask", json={"query": q["query"]})
        data = r.json()
        answer = data.get("answer", "")
        sources = data.get("sources", [])

        print(f"[{q['level']}]")
        print(f"  Q: {q['query']}")
        print(f"  expects answer to touch on: {q['hop']}")
        print(f"  A: {answer}")
        if sources:
            top = sources[0]
            print(f"  top source [{top.get('source')}] ({top['score']:.4f}): {top['text'][:90]}...")
        else:
            print("  (no sources returned)")

        if q["expect"]:
            hit = any(phrase in answer.lower() for phrase in q["expect"])
            print(f"  check: {'PASS' if hit else 'CHECK MANUALLY'} (looked for {q['expect']})")
        print()


if __name__ == "__main__":
    main()
