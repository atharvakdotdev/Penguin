import os
import chromadb
import ollama

# -------------------------
# Configuration
# -------------------------

DB_PATH = "./chroma_db"
DATA_PATH = "RAG/rag_data"

EMBEDDING_MODEL = "nomic-embed-text"

client = chromadb.PersistentClient(path=DB_PATH)

collection = client.get_or_create_collection(
    name="problem_solutions"
)

def chunk_text(text):
    chunks = []

    pairs = text.split("\n\nProblem:\n")

    for pair in pairs:
        if not pair.strip():
            continue

        problem, solution = pair.split("\n\nSolution:\n", 1)

        chunks.append(
            f"Problem:\n{problem.strip()}\n\n"
            f"Solution:\n{solution.strip()}"
        )

    return chunks


def add_documents():

    for filename in os.listdir(DATA_PATH):

        path = os.path.join(DATA_PATH, filename)

        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_text(text)

        for i, chunk in enumerate(chunks):

            # Embed the problem, not the solution.
            problem = chunk.split("\n\nSolution:\n", 1)[0]

            embedding = ollama.embeddings(
                model="nomic-embed-text",
                prompt=problem
            )["embedding"]

            collection.upsert(
                ids=[f"{filename}_{i}"],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "source": filename,
                    "chunk": i
                }]
            )
# -------------------------
# Retrieve solutions
# -------------------------

def search(hypothesis, n_results=3):

    embedding = ollama.embeddings(
        model=EMBEDDING_MODEL,
        prompt=str(hypothesis)
    )["embedding"]

    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results
    )

    return results["documents"][0]


# -------------------------
# RAG interface for Penguin
# -------------------------

def get_solutions(hypothesis):

    results = search(hypothesis)

    return "\n\n".join(
        f"- {solution}"
        for solution in results
    )


if __name__ == "__main__":

    add_documents()

    hypothesis = input("Hypothesis: ")

    print("\nRelevant solutions:\n")
    print(get_solutions(hypothesis))