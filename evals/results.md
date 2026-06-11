# Eval results

No eval has been run yet. This file is overwritten by the eval runner:

```powershell
uv run python evals/run_eval.py
```

The full run drives the real graph (OpenAI, and Tavily for web-fallback
rows), so it requires API keys and incurs cost. To check the dataset without
any API calls:

```powershell
uv run python evals/run_eval.py --validate-only
```
