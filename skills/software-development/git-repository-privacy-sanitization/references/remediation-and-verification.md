# Remediation and Verification Matrix

Load this reference only after findings exist. It does not grant mutation authority.

## Approval Matrix

| Finding surface | Typical remediation | Required approval | Verification |
|---|---|---|---|
| Current file content | Targeted substitution or removal | Exact files/findings | Re-scan worktree, index, and candidate diff |
| Filename or directory | Rename to neutral term | Exact paths and downstream references | Tree inventory and link/import tests |
| Commit author/committer | Rewrite named commits or replacement branch | Exact metadata fields and refs | Commit traversal in clean single-ref clone |
| Commit message | Rewrite named commits | Exact commits and replacement text policy | Message scan across intended refs |
| Secret in any reachable commit | Rotate/revoke, then rewrite or remove | Credential response plus exact refs | Provider-side rotation proof and history scan |
| Ignored/generated file | Remove or exclude from publication artifact | Exact file or generated class | Archive/build inventory |
| Unreachable local commit, tag, tree, or blob | Local pruning | Local Git cleanup approval | `git fsck` and object traversal |
| Local `.git/config` | Edit local-only config | Exact key | Config readback without printing sensitive values |
| Remote branch/tag | Force-with-lease update or tag replacement | Separate remote approval | Remote API/ref readback and fresh clone |

## Redaction Strategy

Prefer the smallest replacement that preserves meaning:

- person or account name → role label;
- username → `<user>`;
- hostname → `<host>` or role-based node label;
- IP address → `<ip-address>` or reserved documentation address when protocol shape matters;
- home path → `<home>/<relative-path>`;
- private URL → `<service-url>`;
- environment-specific project label → neutral functional label;
- secret → environment-variable or secret-manager reference, followed by rotation when live.

Do not replace one real identifier with another real identifier. Avoid reversible partial masking when the remaining suffix still identifies the person or system.

## History-Rewrite Sequence

1. Freeze the intended source ref and record its object ID.
2. Create a complete rollback bundle outside the repository.
3. Verify the bundle and record its included ref.
4. Build one replacement history using only approved transformations.
5. Keep backup refs outside the audit scope for the proposed publication ref.
6. Traverse replacement commits, messages, metadata, trees, and blobs.
7. Verify tree equivalence except for approved changes.
8. Run normal privacy hooks on the replacement commit flow.
9. Create a single-ref bundle and clone it into an isolated directory.
10. Re-run the full privacy scan against that clone.
11. Present the replacement ref and audit result before requesting remote approval.
12. If approved, update the remote using the agreed lease protection.
13. Read back remote refs and audit a fresh remote clone.

A local replacement does not sanitize an existing remote. A force-push does not remove forks, caches, release archives, package copies, or already-cloned histories.

## Consent Prompt Shape

Present one recommended action and bounded alternatives:

```text
I found <count> findings in <surfaces>.

Recommended approval:
- Group A: remediate findings <IDs> with <specific substitutions>.
- Group B: rewrite ref <name> for findings <IDs>.

Not included:
- remote push;
- file deletion;
- local object pruning;
- secret rotation.

Approve the recommended groups, select a subset, or classify the ambiguous findings first.
```

Never put raw matched values into the prompt. If the user cannot identify a finding from category and location, provide a non-reversible fingerprint and surrounding neutral context—not the private value.

## Verification Report

Report these assurance layers separately:

- **Content:** files and filenames.
- **History:** commits, messages, metadata, and reachable blobs.
- **Secrets:** scanners used, rotation state, and gaps.
- **Local residue:** ignored files, reflogs, unreachable objects, and local config.
- **Remote:** exact refs and fresh-clone result.
- **Exceptions:** intentional public identity, official references, and approved placeholders.
- **Coverage:** skipped files, byte limits, unavailable tools, and unscanned external copies.

Use “no disallowed findings in the tested surfaces,” not an unsupported claim of universal certainty.
