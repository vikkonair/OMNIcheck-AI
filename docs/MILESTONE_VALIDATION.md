# Milestone Validation Policy

A milestone is successful only after all applicable gates pass:

1. Unit and integration tests pass on Python 3.12.
2. Sanitized fixtures cover new formats, policies, and failure paths.
3. The approved collected customer dataset is processed read-only end to end.
4. All generated files and temporary job configuration remain outside the
   customer source directory.
5. The source file count, sizes, and SHA-256 values remain unchanged.
6. Scope validation proves that logical target-database checks use Primary
   evidence only. OS evidence remains eligible from every configured node, and
   node-local target-database configuration remains eligible from Primary,
   Standby, and DR for cross-node comparison.
7. Unknown or ambiguous evidence remains visible as `pending`; it is never
   silently accepted or dropped.
8. Customer evidence, normalized output, and temporary configuration are never
   committed to Git.
9. The milestone report records pass/fail results and known pending coverage.
10. A Git commit and version tag are created only after the applicable gates
    pass.

For report-rendering milestones, the gate additionally requires the approved
sanitized V4 template, DOCX/PDF content QA, rendered-page inspection, and
Traditional Chinese glyph verification.
