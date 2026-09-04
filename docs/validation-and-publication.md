# Validation and publication

Use this guide to validate a repository candidate before commit or distribution. Run commands from the repository root.

## 1. Create an isolated Python environment

The EVE-NG and privacy scanners use the Python standard library. The Nornir and NAPALM checks require their packages.

```bash
python -m venv .venv
```

Activate the environment on Linux or macOS:

```bash
. .venv/bin/activate
```

Activate it in Git Bash on Windows:

```bash
. .venv/Scripts/activate
```

Install the tested network-automation baseline:

```bash
python -m pip install \
  'nornir==3.6.0' \
  'nornir-napalm==0.6.0' \
  'napalm==5.1.0'
```

The NAPALM skill also documents behavior researched against NAPALM 5.2.0. Check its current Python requirement and driver support before changing the baseline.

## 2. Run deterministic validation

Prevent Python from writing bytecode into the candidate:

```bash
export PYTHONDONTWRITEBYTECODE=1
```

Run all four deterministic validators or scanner tests:

```bash
python skills/devops/eve-ng-api-operations/scripts/validate_skill.py
python skills/devops/nornir-network-automation/scripts/validate_skill.py
python skills/devops/napalm-network-automation/scripts/validate_skill.py
python -m unittest discover \
  -s skills/software-development/git-repository-privacy-sanitization/tests \
  -p 'test_*.py' -v
```

A validator checks the reusable skill contract. It does not replace package, transport, driver, appliance, or device acceptance.

## 3. Run the explicit test suites

Use explicit test directories. Do not rely on repository-root discovery.

```bash
python -m unittest discover \
  -s skills/devops/eve-ng-api-operations/tests \
  -p 'test_*.py' -v

python -m unittest discover \
  -s skills/devops/nornir-network-automation/tests \
  -p 'test_*.py' -v

python -m unittest discover \
  -s skills/devops/napalm-network-automation/tests \
  -p 'test_*.py' -v

python -m unittest discover \
  -s skills/software-development/git-repository-privacy-sanitization/tests \
  -p 'test_*.py' -v
```

Reconcile the reported test totals with the enumerated tests. A command that finds zero tests is a failure, not a clean run.

## 4. Run offline canaries

```bash
python skills/devops/nornir-network-automation/scripts/offline_canary.py
python skills/devops/napalm-network-automation/scripts/mock_canary.py
```

The Nornir canary checks inventory filtering, bounded execution, result inspection, and cleanup without a network connection. The NAPALM canary checks a deterministic mock transaction and rollback path.

Mock and offline results do not prove live transport, authentication, platform support, or operational convergence.

## 5. Gate live acceptance separately

Use live acceptance only against an explicitly authorized target.

For EVE-NG, start with read-only mode:

```bash
python skills/devops/eve-ng-api-operations/scripts/eve_api_acceptance.py \
  --mode read-only
```

Supply appliance details and credentials through a protected runtime channel. Do not place secret values in command arguments, source files, inventory, logs, or evidence.

Before any live change:

1. Resolve the exact appliance, lab, node, or device.
2. Confirm the requested side effect and target are explicit.
3. Preserve strict SSH and TLS verification.
4. Capture a bounded rollback or recovery path.
5. Apply one representative canary.
6. Inspect transaction output for semantic errors.
7. Read configuration and operational state back.
8. Test forwarding when the intended result depends on forwarding.
9. Remove temporary sessions and files.

A normal return from a configuration library is not sufficient. Device output can contain a rejected command even when the library call does not raise an exception.

## 6. Scan for private data

The bundled scanner accepts private identifiers through standard input and writes its report outside the repository:

```bash
python \
  skills/software-development/git-repository-privacy-sanitization/scripts/scan_repository.py \
  --repo . \
  --identifiers-stdin \
  --output '<path-outside-repository>'
```

Build the JSON input in memory. Do not save real identifier or credential values in a helper, fixture, report, or shell command.

Classify these surfaces separately:

- tracked, modified, untracked, ignored, and generated files.
- the exact staged candidate.
- reachable commit content and metadata.
- local Git configuration and unreachable objects.
- the remote publication ref.

A machine privacy hook proves only its configured coverage. Reconcile public URLs, documentation-reserved addresses, inert fixtures, and approved public identity separately from private findings.

If a live credential appears anywhere, stop publication and rotate it. Removing text from Git does not revoke the credential.

## 7. Build the commit candidate

1. Run `git status --short`.
2. Classify every modified and untracked path.
3. Stage explicit publishable paths. Do not use a blanket add when local plans or evidence exist.
4. Run `git diff --cached --check`.
5. Run the configured staged-content privacy gate.
6. Run the configured commit-message privacy gate against the proposed message.
7. Bind review to the parent commit, ordered path set, staged tree, and binary-safe diff digest.
8. Verify line endings in the staged blobs. Git normalization can change the exact bytes after worktree review.
9. Test a clean checkout of the exact index when checkout behavior matters.

The candidate is ready only when tests, privacy checks, review, and QA refer to the same bytes.

## 8. Commit and publish

Commit and push are separate authorization boundaries.

Use normal Git commands so configured hooks run:

```bash
git commit -m '<reviewed-message>'
git push origin <branch>
```

Do not use `--no-verify`. Do not force-push unless the exact history replacement and rollback plan have separate approval.

After a push, read the remote branch back and require its full commit SHA to equal local `HEAD`. Report expected untracked local files separately from the published tree.

## Completion checklist

- [ ] Explicit validators and test suites pass.
- [ ] Offline and live evidence are labeled separately.
- [ ] Live changes have target, approval, rollback, and readback evidence.
- [ ] Private values never enter repository content or command arguments.
- [ ] Exact staged content and commit message pass the configured privacy gates.
- [ ] Review and QA bind to the final candidate bytes.
- [ ] Generated files and temporary reports are absent from the candidate.
- [ ] The commit uses normal hooks.
- [ ] The push is separately approved and non-force.
- [ ] Remote readback matches local `HEAD`.
