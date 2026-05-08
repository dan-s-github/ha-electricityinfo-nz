## Recommended approach: run a **spec reconciliation pass**

Spec Kit treats specs as living, executable project artifacts, not throwaway scaffolding. Its workflow centers on `/specify`, `/clarify`, `/plan`, `/tasks`, `/analyze`, and `/implement`, with `/analyze` intended for cross-artifact consistency checks. ([GitHub][1])

Use this process:

### 1. Freeze the current implementation

Create a branch/tag:

```bash
git checkout -b reconcile-spec-with-implementation
```

### 2. Ask AI to reverse-map the implementation

Prompt:

```text
Compare the current codebase against the existing Spec Kit artifacts.

Produce:
1. Implemented behaviours not present in the spec
2. Spec requirements not implemented
3. Behaviour that differs from the spec
4. Technical decisions that should be reflected in the plan
5. Tests that prove the actual behaviour
Do not modify files yet.
```

### 3. Classify every mismatch

Use three buckets:

| Case                          | Action                                   |
| ----------------------------- | ---------------------------------------- |
| Built behaviour is correct    | Update `spec.md`, `plan.md`, and tasks   |
| Spec is correct, code drifted | Change code/tests                        |
| Unclear                       | Add clarification questions or decisions |

### 4. Update artifacts in order

Do not only edit the spec. Align the full chain:

1. **spec.md** — what the system now promises
2. **plan.md** — architecture and technical decisions actually used
3. **tasks.md** — mark completed, add missed follow-up tasks
4. **tests** — encode acceptance criteria

Then run:

```text
/analyze
```

Use it to catch contradictions across artifacts before more implementation.

### 5. Add traceability

For each key requirement, add a lightweight mapping:

```markdown
### Requirement: User can export report as PDF

Status: Implemented
Code: src/export/pdfExporter.ts
Tests: tests/export/pdf-export.test.ts
Notes: Uses server-side rendering, not client-side generation.
```

### 6. Make this a recurring rule

For future AI sessions, start with:

```text
Before changing code, read spec.md, plan.md, and tasks.md.
After changing code, list any required spec/plan/task/test updates.
Do not leave implementation/spec drift unresolved.
```

## Best practice

Treat the spec as the **contract**, but allow the implementation to teach you. After AI sessions, reconcile both directions:

```text
spec → code
code → spec
tests → spec
```

The key is not “make the spec match the code blindly.” It is: **decide which source is right for each mismatch, then update the other one.**

[1]: https://github.com/github/spec-kit?utm_source=chatgpt.com "GitHub - github/spec-kit: Toolkit to help you get started with Spec ..."
