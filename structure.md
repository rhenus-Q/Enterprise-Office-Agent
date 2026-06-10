# Agentic RAG Architecture

## Prerequisites

Runtime entry point: `main.py` is responsible for receiving user questions and invoking the graph app.

Knowledge base preparation: `ingestion.py` is responsible for loading documents, splitting them into chunks, generating embeddings, and storing them in the vector database.

## Goal

Design an enterprise internal document Q&A assistant.

## Features

The assistant should be able to query a vector database and perform web search when needed.

## Process

### 1. Question routing

The user question first goes through the `question_router`.

The router decides whether the question should go to:

```text
question_router
├── websearch → generate
└── retrieve
```

### 2. Vector database retrieval path

If the question is routed to the vector database:

```text
retrieve
→ grade_documents
```

`grade_documents` checks whether the retrieved documents are relevant to the user question.

```text
grade_documents
├── relevant documents found
│   └── keep relevant documents → generate
└── no relevant documents found
    └── websearch → generate
```

The purpose of this step is to filter out irrelevant documents before generation.

### 3. Answer generation

The `generate` node uses the user question and the selected documents to generate an answer.

```text
generate
→ check whether the answer is grounded in the documents
```

### 4. Answer grounding and usefulness check

After generation, the answer is checked in two layers:

#### 4.1 Grounding check

Check whether the generated answer is grounded in the provided documents.

```text
generation
├── grounded in documents
└── not grounded in documents
```

If the answer is not grounded in the documents, it may contain hallucination.

```text
not grounded → hallucination risk → regenerate
```

#### 4.2 Usefulness check

If the answer is grounded in the documents, check whether it actually answers the user question.

```text
grounded
├── useful → end
└── not useful → grounded in documents but does not answer the question → websearch
```

## Summary

The workflow contains three quality-control layers:

```text
1. Document relevance check
   Are the retrieved documents relevant to the question?

2. Grounding check
   Is the generated answer based on the provided documents?

3. Usefulness check
   Does the generated answer actually answer the user question?
```

The full workflow is:

```text
question
→ question_router
    ├── websearch → generate
    └── retrieve → grade_documents
            ├── relevant documents → generate
            └── no relevant documents → websearch → generate

generate
→ grounding check
    ├── not grounded → regenerate
    └── grounded → usefulness check
            ├── useful → end
            └── not useful → websearch
```
