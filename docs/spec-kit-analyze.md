`/analyze` is essentially a **consistency and coverage audit** across the Spec Kit artifacts before—or after—implementation.

It does **not** primarily write code.
It inspects whether your:

* constitution
* spec
* plan
* tasks
* implementation assumptions

still agree with each other.

## What it checks

### 1. Cross-artifact consistency

Example:

| Artifact   | Says                 |
| ---------- | -------------------- |
| `spec.md`  | OAuth login required |
| `plan.md`  | JWT-only auth        |
| `tasks.md` | No auth tasks        |

`/analyze` flags this mismatch.

---

### 2. Coverage gaps

Checks whether all requirements are represented in:

* architecture
* tasks
* implementation steps
* tests

Example:

```text
Requirement exists:
- "Users can export CSV"

But:
- no task
- no API endpoint
- no test
```

---

### 3. Constitution violations

The constitution is treated as authoritative.

Example:

```markdown
Constitution:
- No automated UI testing
```

But:

```markdown
plan.md:
- Add Playwright suite
```

That becomes a CRITICAL issue. ([CodeStandUp ‍][1])

---

### 4. Dependency validation

Checks task ordering and architectural dependencies.

Example:

```text
Frontend integration task appears before API exists.
```

or

```text
Migration task missing before repository changes.
```

---

### 5. Ambiguities and contradictions

Looks for vague or conflicting statements.

Example:

```text
spec.md:
- "near real-time updates"

plan.md:
- nightly batch processing
```

---

## What it outputs

Usually a table like:

| ID | Severity | Location             | Problem                  | Recommendation          |
| -- | -------- | -------------------- | ------------------------ | ----------------------- |
| C1 | Critical | spec vs constitution | automated tests conflict | remove test requirement |
| G2 | Medium   | tasks.md             | missing retry handling   | add implementation task |

---

# In practice

The most valuable use cases are:

## Before implementation

```text
/specify
/clarify
/plan
/tasks
/analyze
/implement
```

This catches planning defects early.

---

## After several AI coding sessions

This is the important one for your question.

You can use `/analyze` as a **drift detector**:

```text
Compare current implementation with spec artifacts.
Identify:
- implemented but undocumented behavior
- outdated tasks
- architectural drift
- missing tests
- stale assumptions
```

This is where Spec Kit becomes useful beyond greenfield generation.

---

# What `/analyze` does NOT do well

By default it is weaker at:

* reverse engineering mature codebases
* reconstructing architecture from implementation
* updating specs automatically

The community has identified this gap already. ([GitHub][2])

So many teams extend it with a custom reconciliation prompt like:

```text
Treat implementation as partially authoritative.
Update spec artifacts to reflect accepted implementation reality.
```

---

# Recommended workflow for AI-heavy development

After any substantial AI-assisted coding:

## Run a reconciliation analyze

Prompt:

```text
Analyze differences between:
- current codebase
- spec.md
- plan.md
- tasks.md

Classify:
1. spec missing implemented behavior
2. implementation violating spec
3. obsolete tasks
4. undocumented architectural decisions
5. missing tests
```

Then:

* update specs
* regenerate tasks if needed
* re-run `/analyze`

That keeps the spec from becoming historical fiction.

[1]: https://codestandup.com/posts/2025/github-spec-kit-tutorial-analyze-command-implementing-tasks/?utm_source=chatgpt.com "GitHub Spec Kit Tutorial 05 - Analyze Command & Implementing Tasks"
[2]: https://github.com/github/spec-kit/issues/438?utm_source=chatgpt.com "Add analyze command for reverse engineering existing codebases ... - GitHub"
