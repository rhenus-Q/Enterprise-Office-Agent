from dotenv import load_dotenv

# Load .env before importing app.
# Importing graph.graph triggers module-level init of nodes / chains
# (constructing ChatOpenAI / OpenAIEmbeddings / retriever), which needs the env vars.
load_dotenv()

from graph.graph import app  # noqa: E402


def main():
    print("Enterprise Knowledge Assistant")
    print("Type 'exit' to quit.\n")

    while True:
        question = input("Enter your question:\n> ").strip()

        if question.lower() in ["exit", "quit", "q"]:
            print("Bye.")
            break

        if not question:
            continue

        # Initialize the full GraphState so nodes / conditional functions never read a missing key.
        result = app.invoke(
            {
                "question": question,
                "documents": [],
                "generation": "",
                "web_search": False,
                "retries": 0,
            }
        )

        print("\nAnswer:")
        # Prefer "generation" from result; if absent, print the whole result.
        print(result.get("generation", result))
        print("-" * 80)


if __name__ == "__main__":
    main()