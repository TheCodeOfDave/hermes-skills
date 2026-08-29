---
name: git-repository-privacy-sanitization
description: Use when scanning or sanitizing a Git repository for personal, private, secret, or environment-specific information. Retrieves user-specific identifiers without persisting them, reports redacted findings, and requires explicit approval before every removal or history rewrite.
version: 1.0.0
author: Hermes Skills Contributors
license: MIT
metadata:
  hermes:
    tags: [git, privacy, pii, secrets, sanitization]
    related_skills: []
---

# Git Repository Privacy Sanitization

## Contract

Find first, explain second, remove only after approval.

This skill audits files, filenames, Git history, commit metadata, ignored artifacts, and local Git residue for information that could identify a person or expose a private environment. It uses relevant facts already known about the user, but never writes those private search terms into the repository, report, command line, commit message, or chat transcript.

A scan request is not removal approval. Even when the user says “clean” or “sanitize,” present the findings and proposed mutations, then ask for explicit permission before changing content, metadata, history, refs, ignored files, or local Git state.

## When to Use

Use this skill when the user asks to:

- remove personal or private information from a repository;
- prepare a repository, archive, branch, or release for public sharing;
- find names, handles, email addresses, usernames, hostnames, IP addresses, paths, account IDs, secrets, or infrastructure fingerprints;
- rewrite Git author or committer metadata;
- verify that a sanitized history is publication-safe.

Use a secret-rotation or incident-response procedure as well when a live credential may have been exposed. Removing a secret from Git does not revoke it.

## Non-Negotiable Rules

1. **Retrieve broadly, disclose narrowly.** Use available user context to improve recall, but report labels and redacted evidence rather than matched values.
2. **No private denylist in the repository.** Keep user-specific identifiers in memory, protected standard input, or a restricted file outside the repository.
3. **No mutation before findings approval.** Scanning, classification, and remediation planning are read-only.
4. **Approval is action-specific.** Content edits, file removal, history rewriting, ref deletion, local-object pruning, and remote force-pushes are separate decisions.
5. **Intentional public identity is not automatically private.** Ask whether public handles, noreply addresses, license attribution, and public project URLs should remain.
6. **Report publication surfaces separately.** A clean worktree does not prove clean history; a clean branch does not prove every ref is clean; local `.git` residue is not automatically published.
7. **Never print secrets or private matches.** Show category, location, source, redacted fingerprint, and proposed action.
8. **Rotation precedes cleanup for live secrets.** Stop publication, advise revocation or rotation, and avoid reproducing the value.
9. **Preserve rollback before approved destructive work.** Verify a bundle or backup outside the repository before rewriting history.
10. **A successful command is not proof of removal.** Audit the exact replacement ref and a clean clone after integration.

## Phase 1 — Establish Scope

Resolve and record:

- repository root and intended publication artifact;
- branch, tags, remotes, worktrees, dirty state, and ignored files;
- whether the user means current files, all reachable history, every local object, an archive, or a remote repository;
- whether the repository is already public;
- the effective Git privacy hooks and commit identity policy;
- actions that require later approval.

Separate these authorities:

| Surface | Publication relevance |
|---|---|
| Current tracked tree | Published by a normal commit/push |
| Untracked and ignored files | Not pushed normally, but may leak through archives or broad copies |
| Candidate index/tree | Exact proposed bytes |
| Reachable commits and refs | Clone-visible history and metadata |
| Unreachable objects and reflogs | Local residue unless later referenced or copied with `.git` |
| Local `.git/config` | Local-only unless copied or logged |
| Remote repository | External state requiring readback after change |

Completion criterion: the intended publication ref and every applicable scan surface are explicit.

## Phase 2 — Build an Ephemeral Identifier Set

Use every applicable memory plane before scanning:

1. Current conversation and explicit user instructions.
2. Injected user profile and persistent memory.
3. Raw cross-session evidence when the user refers to prior details.
4. Derived user context such as a profile card, treated as advisory.
5. Reviewed knowledge or owning documentation when it may contain environment identifiers.
6. Current system and repository metadata: OS account, Git identity, remotes, configured hosts, and repository paths.

Collect candidate values by category:

- names and aliases;
- public and private handles;
- personal and account-linked email addresses;
- usernames and user-home directory segments;
- machine, VM, container, profile, service, and private-domain names;
- private and public IP addresses tied to the environment;
- phone numbers, addresses, account IDs, and organization identifiers;
- repository, project, client, and topology labels that reveal ownership;
- credential names and exact secret values available through protected sources.

Attach provenance and confidence internally. Do not assume every known value must be removed: intentional public identity requires user classification.

Keep values in source order so the agent can map generated report ordinals back to its ephemeral context. The scanner ignores caller-provided labels and emits only generated ordinals.

### Passing identifiers to the scanner

Prefer standard input so values do not enter shell history or process arguments:

```bash
python scripts/scan_repository.py --repo '<repository>' --identifiers-stdin --output '<report-outside-repository>'
```

The scanner expects JSON on standard input:

```json
{
  "identifiers": [
    {"value": "<private-value>"}
  ]
}
```

Construct that JSON in memory or through a protected secret-execution mechanism. Runtime context enters the scanner only through standard input; the scanner does not retrieve memory itself. Never save the example with a real value, and never place the output report inside the repository.

Completion criterion: applicable known identifiers are held only in an ephemeral or protected channel, and their source order is retained outside the report for classification.

## Phase 3 — Scan Every Surface

Run `scripts/scan_repository.py` for deterministic structural and exact-identifier scanning. Also use installed secret scanners when available; record unavailable optional scanners as a coverage limitation rather than inventing a PASS.

The bundled scanner checks:

- worktree filenames and file bytes, including untracked and ignored files;
- symlink text without following the link target;
- current `HEAD` tree;
- every commit and blob reachable from local refs;
- author, committer, and commit-message metadata;
- email, IPv4, IPv6, home-path, UNC-path, private-key, credential-shape, URL, and sensitive-literal patterns;
- optional local Git configuration and all local blob objects when `--include-local-git` is selected;
- exact user-specific identifiers supplied through protected standard input.

For large or binary files, review scanner skips and limits. Do not equate partial coverage with a clean verdict.

Run normal repository-specific tests and privacy hooks separately. A hook PASS proves only that hook’s configured coverage.

Completion criterion: every applicable surface has a result, skip, or explicit blocker.

## Phase 4 — Classify and Report Before Mutation

Classify each finding as:

- **private personal information**;
- **secret or authentication material**;
- **intentional public identity**;
- **system or infrastructure fingerprint**;
- **generic placeholder or official public reference**;
- **false positive**;
- **unknown—user classification required**.

Report findings without raw matched values. Use this shape:

```text
Finding: F-<stable-id>
Surface: candidate tree | reachable history | ignored file | local-only Git state
Location: <path and line, commit prefix, or metadata field>
Category: <redacted category>
Source: known-user identifier | structural pattern | secret scanner
Publication impact: <what would expose it>
Proposed remediation: <exact mutation>
Destructive: yes | no
Approval group: A | B | C
```

Then summarize approval groups, for example:

- **A — content substitutions:** replace approved values with role-neutral placeholders;
- **B — metadata rewrite:** replace approved author/committer fields in named refs;
- **C — file or history removal:** remove approved files/blobs and rewrite named refs;
- **D — local residue cleanup:** prune approved unreachable objects, reflogs, or local generated files;
- **E — remote replacement:** push the reviewed rewritten ref with the agreed safety mechanism.

Ask the user which groups and findings they approve. Put the recommended minimal set first. Do not combine a content edit with a force-push approval.

Completion criterion: the user has seen a redacted inventory and explicitly approved exact findings and mutation classes.

## Phase 5 — Apply Only Approved Remediation

After approval:

1. Create and verify a rollback artifact outside the repository.
2. Re-read the exact target immediately before mutation.
3. Apply only approved substitutions or removals.
4. Preserve useful reproducibility evidence while neutralizing ownership and environment detail.
5. For history rewrites, produce one clean replacement ref rather than repeatedly rewriting public history.
6. Use normal Git commits so configured pre-commit and commit-message privacy hooks run.
7. Never bypass hooks or weaken identifier configuration.
8. Keep remote mutation separate until explicitly approved.

Load `references/remediation-and-verification.md` for the mutation matrix, approval boundaries, and verification sequence.

Completion criterion: every changed byte or ref maps to an approved finding, and no unapproved target changed.

## Phase 6 — Verify the Exact Result

Verification must cover:

1. sanitized worktree and filenames;
2. exact staged index/tree;
3. candidate-only diff;
4. exact rewritten branch history and commit metadata;
5. every ref intended for publication;
6. optional local-only residue, reported separately;
7. privacy hooks and available secret scanners;
8. repository tests;
9. a clean clone or single-ref bundle clone;
10. the remote target after any approved push.

Require a zero-disallowed-finding result for the intended publication artifact. Allowed official references and user-approved public identity must be listed as explicit exceptions, not silently ignored.

Completion criterion: a clean clone of the exact publication ref contains only approved exceptions, with no unexplained scanner skips.

## Common Pitfalls

1. **Scanning only the worktree.** Old commits and metadata remain clone-visible.
2. **Dumping the denylist into a report.** The audit becomes the leak.
3. **Treating memory as unquestionable truth.** Derived context generates candidates; the user classifies ambiguous identity.
4. **Auto-removing a public handle.** Public identity can be intentional and useful.
5. **Printing a secret to prove it exists.** Report category and fingerprint only, then rotate.
6. **Using `--all` without ref accounting.** Backup refs can make a clean replacement look dirty or conceal which ref would publish.
7. **Calling local `.git/config` a published finding.** Report it separately unless `.git` itself will be distributed.
8. **Cleaning content but not filenames.** Names and paths can disclose the same information as file bytes.
9. **Removing without rollback.** History rewrites and file deletion require verified recovery artifacts.
10. **Assuming force-push approval.** Rewriting locally and replacing a remote are separate actions.
11. **Claiming absolute certainty.** State scan surfaces, patterns, tools, skips, exceptions, and residual risk precisely.

## Verification Checklist

- [ ] Publication artifact and ref are explicit.
- [ ] User-specific identifier candidates came from all applicable memory planes.
- [ ] Private values never entered the repository, report, command line, or transcript.
- [ ] Worktree, filenames, ignored files, candidate tree, reachable history, and metadata were scanned.
- [ ] Unreachable objects and local Git configuration were classified separately.
- [ ] Findings are redacted and have stable IDs.
- [ ] Intentional public identity and official references are explicit exceptions.
- [ ] User approved exact findings and mutation groups before changes.
- [ ] Rollback artifact exists and verifies before destructive work.
- [ ] Only approved targets changed.
- [ ] Both Git privacy hooks passed using normal commit flow.
- [ ] Available secret scanners and repository tests passed; unavailable coverage is disclosed.
- [ ] Clean-clone verification passed for the exact publication ref.
- [ ] Any remote change was separately approved and read back.
