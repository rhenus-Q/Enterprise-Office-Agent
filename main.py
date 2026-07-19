"""Repository-level entry point for the Enterprise Office Agent.

`uv run python main.py` launches the Office Agent interactive CLI (the same
interface as `uv run python -m office_agent.cli`). The Enterprise RAG engine
has its own standalone CLI at `enterprise_rag/cli.py`
(`uv run python -m enterprise_rag.cli`). See ADR 020.
"""

from office_agent.cli import main

if __name__ == "__main__":
    main()
