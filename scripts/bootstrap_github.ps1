# STAR's one-time repository bootstrap. Requires Git, GitHub CLI, and your sign-in.
# It never stores your GitHub password or a personal access token in the repository.
param([string]$RepositoryName = 'star-core')
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Install Git for Windows first: https://git-scm.com/download/win' }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Install GitHub CLI first: winget install --id GitHub.cli -e' }
$auth = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host 'GitHub requires a one-time login. Browser authentication will open now.'
    gh auth login
    if ($LASTEXITCODE -ne 0) { throw 'GitHub authentication was not completed' }
}
if (-not (Test-Path '.git')) {
    git init
    if ($LASTEXITCODE -ne 0) { throw 'Failed to initialize git repository' }
}
# Check identity before a commit rather than silently invent one.
$name = git config user.name
$email = git config user.email
if (-not $name -or -not $email) {
    throw 'Configure Git commit identity first with: git config --global user.name "Your Name" and git config --global user.email "you@example.com"'
}
git add .
if ($LASTEXITCODE -ne 0) { throw 'git add failed' }
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m 'STAR Genesis initial local AI'
    if ($LASTEXITCODE -ne 0) { throw 'git commit failed' }
}
git branch -M main
if ($LASTEXITCODE -ne 0) { throw 'git branch failed' }
Write-Host "Creating a private GitHub repository named $RepositoryName under the authenticated account."
# Do NOT add force push or merge flags. Existing repo names will produce an error.
gh repo create $RepositoryName --private --source . --remote origin --push
if ($LASTEXITCODE -ne 0) { throw 'GitHub repository creation failed; no force push was attempted' }
Write-Host 'Repository created. Register/install your separate STAR GitHub App using docs/GITHUB_APP_SETUP.md.'
