# Handoffs

Use one section per handoff.

```md
## Handoff: `H-T1-T3-001`
- From: `thread1`
- To: `thread3`
- Date: `2026-03-14`
- Related Task IDs: `T1-BACKEND-001`
- Summary: Explain what changed and why it is ready for the next stage.
- Files/Artifacts:
  - `path/or/artifact`
- Verification done:
  - tests or manual checks
- Risks/Open questions:
  - remaining concerns
- Requested action:
  - what the receiving thread should do next
```

`thread3` should make the merge gate explicit with either `ALLOW_MERGE_TO_BASE` or `BLOCK_MERGE_TO_BASE`.
