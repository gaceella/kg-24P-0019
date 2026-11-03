#!/usr/bin/env python3
"""Download the plain text of the five assigned Wikipedia articles into data/raw/.
Based on Appendix B of the assignment handout. Run from the repo root."""
import pathlib
import requests

# TODO: put your own contact in the User-Agent (Wikipedia asks for this)
HEADERS = {"User-Agent": "KRR-coursework/1.0 (p240019@pwr.nu.edu.pk)"}
TITLES = ["James Chadwick", "Steven Weinberg", "Albert Einstein",
          "Ernest Lawrence", "James Franck"]


def fetch(title):
    r = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={"action": "query", "prop": "extracts", "explaintext": 1,
                "redirects": 1, "titles": title, "format": "json"},
        headers=HEADERS, timeout=30)
    r.raise_for_status()
    page = next(iter(r.json()["query"]["pages"].values()))
    return page["extract"]


if __name__ == "__main__":
    out = pathlib.Path("data/raw")
    out.mkdir(parents=True, exist_ok=True)
    for t in TITLES:
        text = fetch(t)
        (out / (t.replace(" ", "_") + ".txt")).write_text(text, encoding="utf-8")
        print(f"saved {t}: {len(text)} chars")