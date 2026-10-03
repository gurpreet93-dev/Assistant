"""Knowledge base: ingest contractor documents, chunk them, and search with BM25.

Deliberately not a vector store. A single contractor's KB is a handful of documents
(services, price list, warranty, FAQ, service area), and BM25 over paragraph chunks is
fast, dependency-free and easy to explain. The agent calls `search` as a tool, so the
retrieval backend can be swapped for embeddings later without touching the agent.
"""
import io
import math
import re
from collections import Counter

from pypdf import PdfReader

from app.db import get_db, now_iso

CHUNK_CHARS = 900
STOPWORDS = set(
    "a an and are as at be by do does for from has have how i in is it its me my of on or "
    "our so that the their them they this to us was we what when where which who will with "
    "you your can if any".split()
)


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if name.endswith((".txt", ".md", ".csv")):
        return data.decode("utf-8", errors="replace")
    raise ValueError("Unsupported file type. Upload .txt, .md, .csv or .pdf")


def chunk_text(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    """Greedy paragraph packing. Headings stay attached to the paragraph that follows."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, current = [], ""
    for para in paragraphs:
        if len(para) > max_chars:  # split very long paragraphs on sentence boundaries
            sentences = re.split(r"(?<=[.!?])\s+", para)
        else:
            sentences = [para]
        for piece in sentences:
            if current and len(current) + len(piece) + 2 > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


def add_document(contractor_id: int, filename: str, content: str) -> int:
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO documents (contractor_id, filename, content, created_at) VALUES (?,?,?,?)",
            (contractor_id, filename, content, now_iso()),
        )
        doc_id = cur.lastrowid
        for i, chunk in enumerate(chunk_text(content)):
            db.execute(
                "INSERT INTO chunks (document_id, contractor_id, idx, text) VALUES (?,?,?,?)",
                (doc_id, contractor_id, i, chunk),
            )
    return doc_id


def delete_document(contractor_id: int, doc_id: int) -> None:
    with get_db() as db:
        db.execute("DELETE FROM documents WHERE id=? AND contractor_id=?", (doc_id, contractor_id))


def list_documents(contractor_id: int) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT d.id, d.filename, d.created_at, length(d.content) AS chars, "
            "(SELECT count(*) FROM chunks c WHERE c.document_id=d.id) AS chunk_count "
            "FROM documents d WHERE d.contractor_id=? ORDER BY d.created_at DESC",
            (contractor_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def search(contractor_id: int, query: str, k: int = 4) -> list[dict]:
    """BM25 (k1=1.5, b=0.75) over this contractor's chunks."""
    with get_db() as db:
        rows = db.execute(
            "SELECT c.text, d.filename FROM chunks c JOIN documents d ON d.id=c.document_id "
            "WHERE c.contractor_id=?",
            (contractor_id,),
        ).fetchall()
    if not rows:
        return []
    docs = [tokenize(r["text"]) for r in rows]
    n = len(docs)
    avgdl = sum(len(d) for d in docs) / n or 1
    df = Counter(term for d in docs for term in set(d))
    q_terms = tokenize(query)
    k1, b = 1.5, 0.75

    scored = []
    for row, doc in zip(rows, docs):
        tf = Counter(doc)
        score = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * len(doc) / avgdl))
        if score > 0:
            scored.append({"source": row["filename"], "text": row["text"], "score": round(score, 2)})
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:k]
