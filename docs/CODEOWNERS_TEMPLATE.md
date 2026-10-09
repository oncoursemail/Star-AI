# GitHub CODEOWNERS template

If your GitHub plan supports protected branches in **private repositories**, replace `YOUR_GITHUB_USERNAME` with the actual repository owner, then copy this into `.github/CODEOWNERS`:

```text
* @YOUR_GITHUB_USERNAME
/.github/ @YOUR_GITHUB_USERNAME
/star/policy.py @YOUR_GITHUB_USERNAME
/star/github_app.py @YOUR_GITHUB_USERNAME
/star/selfbuild.py @YOUR_GITHUB_USERNAME
```

Never give STAR's GitHub App review-bypass rights. On GitHub Free with a **private** repository, branch protection enforcement may not be available. Local source-policy checks are helpful but cannot replace server-enforced repository protections. Consider GitHub Pro/Team when you need private-branch enforcement. Docs: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
