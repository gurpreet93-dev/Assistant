"""Compare chunking strategies on your own questions and pick one with data.

    python -m scripts.chunking_experiment              # local keyword search (free, instant)
    python -m scripts.chunking_experiment --pinecone   # real semantic search (uses free-tier units)

Inputs:  sample_kb/*            the documents
         evals/retrieval_questions.json   question + text the right chunk must contain
Metric:  recall@3 = share of questions where a correct chunk is in the top 3 results.
Then set CHUNK_MAX_CHARS in .env to the winner (the app reads it in app/knowledge.py).
"""
import json
import sys
import time
from pathlib import Path

from app import knowledge

ROOT = Path(__file__).resolve().parent.parent
K = 3


def fixed_size(text: str, source: str, size: int = 500) -> list[dict]:
    """The naive baseline (Pinecone quickstart style): cut every `size` characters."""
    return [{"section": "", "text": text[i:i + size]} for i in range(0, len(text), size)]


STRATEGIES = {
    "fixed-500 (baseline)": lambda t, s: fixed_size(t, s, 500),
    "headings-400": lambda t, s: knowledge.chunk_text(t, s, max_chars=400),
    "headings-800": lambda t, s: knowledge.chunk_text(t, s, max_chars=800),
    "headings-1200": lambda t, s: knowledge.chunk_text(t, s, max_chars=1200),
    "headings-800-no-header": lambda t, s: knowledge.chunk_text(t, s, max_chars=800, contextual_header=False),
}


def load_docs() -> list[tuple[str, str]]:
    docs = []
    for path in sorted((ROOT / "sample_kb").iterdir()):
        if path.suffix.lower() in knowledge.SUPPORTED:
            docs.append((path.name, knowledge.extract_text(path.name, path.read_bytes())))
    return docs


def hit(text: str, must: list[str]) -> bool:
    return all(m.lower() in text.lower() for m in must)


def run_local(chunks: list[str], questions: list[dict]) -> list[bool]:
    return [any(hit(chunks[i], q["must_contain"]) for i, _ in knowledge.bm25_rank(q["q"], chunks)[:K])
            for q in questions]


def run_pinecone(name: str, chunks: list[str], questions: list[dict]) -> list[bool]:
    from app import vectorstore
    index = vectorstore._index()
    ns = "exp-" + "".join(c if c.isalnum() else "-" for c in name.lower())[:40]
    records = [{"_id": f"{ns}-{i}", "chunk_text": c} for i, c in enumerate(chunks)]
    for i in range(0, len(records), vectorstore.UPSERT_BATCH):
        index.upsert_records(records=records[i:i + vectorstore.UPSERT_BATCH], namespace=ns)
    time.sleep(10)  # Pinecone indexes asynchronously
    try:
        out = []
        for q in questions:
            hits = index.search(namespace=ns, top_k=K, inputs={"text": q["q"]}, fields=["chunk_text"]).result.hits
            out.append(any(hit(h.fields.get("chunk_text", ""), q["must_contain"]) for h in hits))
        return out
    finally:
        index.delete_namespace(namespace=ns)


def main() -> None:
    use_pinecone = "--pinecone" in sys.argv
    questions = json.loads((ROOT / "evals" / "retrieval_questions.json").read_text())
    docs = load_docs()
    print(f"{len(docs)} documents, {len(questions)} questions, backend={'pinecone' if use_pinecone else 'local BM25'}\n")
    rows = []
    for name, strategy in STRATEGIES.items():
        chunks = [c["text"] for src, text in docs for c in strategy(text, src)]
        results = run_pinecone(name, chunks, questions) if use_pinecone else run_local(chunks, questions)
        rows.append((name, sum(results), len(chunks), [q["q"] for q, ok in zip(questions, results) if not ok]))
    print(f"{'strategy':28} {'recall@3':>9} {'chunks':>7}")
    for name, ok, n, _ in rows:
        print(f"{name:28} {ok:>4}/{len(questions):<4} {n:>7}")
    for name, _, _, missed in rows:
        if missed:
            print(f"\n{name} missed:\n  - " + "\n  - ".join(missed))


if __name__ == "__main__":
    main()
