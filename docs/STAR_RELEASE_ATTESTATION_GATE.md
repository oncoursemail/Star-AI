# STAR Windows Release Provenance Gate

**Candidate only, October 11, 2026.** This PR changes the canonical
GitHub Actions workflow for the public oncoursemail/Star-AI repository.
It is not merged and has not yet demonstrated a real published release
with verified provenance.

## Why this exists

STAR's existing main-only workflow builds a Windows installer and portable
ZIP, performs packaged smoke tests, creates SHA256SUMS and automatically
publishes a new GitHub Release when the version tag has not been used.
Hashes show file integrity but do not independently certify where files
were built. Releasing from a repository whose main branch lacks active
rulesets remains a separate governance risk.

## What the change enforces

1. PR Windows builds keep contents: read only. They never receive attestation
   identity credentials or the main publisher's contents: write privilege.
2. After successful main Windows build only, a separate attest-release job
   downloads exactly one tested Setup and one portable ZIP from the workflow
   artifact and issues SLSA-style signed provenance using actions/attest@v4.
3. The publish-release job now depends on both Windows build and attestation.
4. Immediately before publishing, it runs gh attestation verify on BOTH
   exact release binaries, restricting verification to the STAR repository,
   the canonical Windows workflow, refs/heads/main and the current commit.
5. A missing/invalid attestation aborts the publisher. A previously published
   version remains untouched. A superseded main commit is still skipped.

The signed attestation is stored through GitHub's attestations API; this is
not Authenticode executable signing. It does not by itself prove native
Windows installation, Roblox Studio acceptance or repository branch rules.

## Required owner configuration before greater autonomy

- GitHub repository Settings -> Rules -> Rulesets: protect main, require PRs
  and known-source offline/React/Windows CI, prevent force-push and deletion,
  and independently review security/workflow changes. Consider a second
  maintainer or independent reviewer if approvals are required.
- GitHub Settings -> Environments: create a production-release environment
  with required reviewers. An environment name alone does not impose a
  protection rule; it must be configured. Integrating it into the publisher
  is follow-up work, not included here.
- Move dependency installs to lockfile-backed deterministic builds and
  pin external action commit SHAs with update review.
- Obtain appropriate code-signing credentials and incorporate verified
  Authenticode signatures into the binary build job without making
  signing secrets available to PR code.
- Run clean Windows installation, in-place upgrade, Roblox Studio and
  model/GPU acceptance on a real disposable Windows host. Record evidence.

## Independent validation

Offline regression tests: tests/test_release_provenance.py.

    python -m pytest -q tests/test_release_provenance.py
    python -m pytest -q

This PR's main-only signing/provenance stages are skipped on pull_request,
by design. Their successful execution still requires a trusted main build
after review and should never be claimed solely from a passing PR preview.

## Primary references

GitHub artifact attestations:
https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations

Current actions/attest action:
https://github.com/actions/attest

GitHub CLI provenance verification:
https://cli.github.com/manual/gh_attestation_verify

GitHub Actions security guidance:
https://docs.github.com/en/actions/reference/security/secure-use

GitHub repository rulesets:
https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
