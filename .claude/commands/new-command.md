---
description: Create a new Claude Code command file from a command name and purpose
argument-hint: 'Command name plus purpose, e.g. "review-config: review config files for safety and consistency"'
allowed-tools: Read, Write, Glob, Grep, Bash(git status:*)
---

You are creating a new Claude Code command file for this Agentic RAG project.

User input: $ARGUMENTS

This is a command-file creation task.

Create exactly one new file under:

`.claude/commands/`

Do not modify existing command files.

Do not modify `CLAUDE.md`.

Do not modify application code.

Do not modify tests.

Do not modify eval files.

Do not modify README.

Do not modify roadmap files.

Do not modify prompts.

Do not modify model names.

Do not modify corpus documents.

Do not modify `.env` or `.env.example`.

Do not run tests.

Do not run full eval.

Do not run `ingestion.py`.

Do not run `tests/chains/`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

Use as few tools as possible.

## Goal

Create a safe, focused, reusable Claude Code command file from the user's requested command name and purpose.

The new command should be:

* narrow in scope
* explicit about allowed modifications
* explicit about forbidden operations
* consistent with existing project commands
* safe for this Agentic RAG project
* easy to review with `/review-command`

This task only creates the initial command file.

It does not review the command.

It does not fix other commands.

It does not write a command review report.

## Step 1. Validate and parse input

If `$ARGUMENTS` is empty, stop and ask the user for:

* a command name
* a short purpose description

The user input should contain both:

* command name
* command purpose

Accepted examples:

* `review-config: review config files for safety and consistency`
* `/review-config review config files for safety and consistency`
* `review-config - review config files for safety and consistency`
* `create-eval-row: create a new eval dataset row from a scenario description`

Normalize the command name:

* trim whitespace
* remove a leading `/` if present
* remove a trailing `.md` if present
* convert spaces and underscores to hyphens
* lowercase it
* keep only letters, numbers, and hyphens
* collapse repeated hyphens
* strip leading or trailing hyphens

The final command path must be:

`.claude/commands/<command-name>.md`

If the command name is empty after normalization, stop and ask for a clearer command name.

If the purpose is missing or too vague, stop and ask for a clearer purpose.

## Step 2. Check for existing command file

Use `Glob` to check whether the target file already exists:

`.claude/commands/<command-name>.md`

If the command file already exists, stop.

Do not overwrite it.

Do not create a suffixed duplicate.

Tell the user the command already exists and suggest using `/review-command /<command-name>` or manually editing the existing command.

## Step 3. Read minimal project context

Read:

* `CLAUDE.md`

Then read only relevant peer commands for style.

Prefer these if they exist:

* `.claude/commands/review-diff.md`
* `.claude/commands/arch-review.md`
* `.claude/commands/review-command.md`
* `.claude/commands/update-claude-md.md`
* `.claude/commands/implement-spec.md`
* `.claude/commands/new-spec.md`
* `.claude/commands/plan-spec.md`

Do not read unrelated project files unless needed to avoid creating an unsafe command.

Run only:

```powershell
git status --short
```

Do not run tests.

## Step 4. Decide the command category

Classify the requested new command into one of these categories:

* read-only review command
* documentation/report-writing command
* single-file edit command
* spec/plan workflow command
* implementation command
* validation/check command
* other

Use the category to choose narrow `allowed-tools`.

Do not grant tools just because peer commands have them.

Grant only what the new command actually needs.

## Step 5. Choose safe allowed-tools

Use the narrowest safe tool set.

Common patterns:

### Read-only review command that writes no report

Use:

`allowed-tools: Read, Glob, Grep, Bash(git status:*)`

### Review/report command that writes a report

Use:

`allowed-tools: Read, Write, Glob, Grep, Bash(git status:*), Bash(mkdir:*)`

### Single-file documentation edit command

Use:

`allowed-tools: Read, Edit, Glob, Grep, Bash(git status:*), Bash(git diff:*)`

### Implementation command

Only grant implementation tools if the command is explicitly an implementation command.

Prefer narrow Bash permissions.

Never grant broad Bash.

Do not use:

* `Bash(*)`
* `Bash(uv run:*)`
* broad test permissions
* full eval permission
* ingestion permission
* API-key command permission

unless the user explicitly requested that class of command and the command clearly needs it.

## Step 6. Generate the new command file

Create exactly one new file:

`.claude/commands/<command-name>.md`

Use this structure:

```markdown
---
description: <short action-oriented description>
argument-hint: <clear example of expected input>
allowed-tools: <narrow tool list>
---

<command body>
```

Frontmatter rules for the generated file:

* No blank line between the opening `---` and the first key.
* Closing delimiter must be exactly `---` (not a long dash run).
* If `argument-hint` contains `: `, quote the value with single quotes.

The command body must include:

* role statement
* `User input: $ARGUMENTS`
* task scope
* exactly what files or directories may be modified
* exactly what files or directories must not be modified
* no-commit rule
* no-branch rule
* forbidden tests/eval/ingestion/API commands unless explicitly needed
* minimal context-reading instructions
* main task steps
* validation steps
* final response format

For any command that can modify files, include:

* "Modify only: ..."
* "Do not modify any other file."
* "Do not create unrelated files."

For any command that writes a report, include:

* exact report directory
* filename convention
* collision handling
* "Use `Write` only for the selected report file."

For any command that edits an existing file, include:

* "Use `Edit` only for the target file."
* scoped `git diff -- <target file>` validation

For any review-only command, include:

* "Do not modify the thing being reviewed."
* "Do not fix issues during review."
* "Write findings only if the command is a report-writing command."

## Step 7. Project safety requirements

Every generated command must protect these project-critical areas unless the command's explicit purpose requires touching them:

* prompts
* model names
* corpus documents
* `.env`
* `.env.example`
* graph behavior
* graph routing
* graph nodes
* `stop_reason` semantics
* fallback policy semantics
* privacy mode
* full eval
* `ingestion.py`
* `tests/chains/`
* API-key-requiring commands
* commits
* branch creation or switching

Implementation commands may touch code only when their purpose explicitly requires it.

Documentation commands must not touch code.

Review commands must not fix code.

## Step 8. Validate the new command file

Run only:

```powershell
git status --short
git diff --stat -- .claude/commands/<command-name>.md
```

Because the new command file is untracked, `git diff --stat` may show no output. That is expected.

Do not run tests.

Do not run full eval.

Do not run `ingestion.py`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

## Step 9. Final response

Report:

* new command file path
* command name
* command category
* allowed tools chosen
* why those tools are necessary
* confirmation that no other files were modified
* `git status --short`
* `git diff --stat -- .claude/commands/<command-name>.md`

Then recommend the next step:

`/review-command /<command-name>`

Do not commit.
