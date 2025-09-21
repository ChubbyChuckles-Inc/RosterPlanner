# scripts/merge-all-branches.ps1
# Merges all branches into master, including those with unrelated histories, on Windows.
# Ensures compliance with CONTRIBUTING.md (pre-commit hooks, 85% test coverage).

# Switch to master branch and pull latest changes
Write-Output "Switching to master and pulling latest changes..."
git checkout master
if ($LASTEXITCODE -ne 0) {
    Write-Output "Failed to switch to master. Please check your repository state."
    exit 1
}
git pull origin master
if ($LASTEXITCODE -ne 0) {
    Write-Output "Failed to pull master. Please resolve any issues (e.g., authentication, network)."
    exit 1
}

# Get list of all local branches except master
$branches = git branch | Where-Object { $_ -notmatch 'master' } | ForEach-Object { $_.Trim() }

foreach ($branch in $branches) {
    Write-Output "Merging $branch into master with --allow-unrelated-histories..."
    git merge --no-ff --allow-unrelated-histories $branch
    if ($LASTEXITCODE -ne 0) {
        Write-Output "Merge conflict or error in $branch. Please resolve conflicts manually, then run 'git commit' and re-run this script."
        exit 1
    }

    # Run pre-commit hooks to enforce code quality standards
    Write-Output "Running pre-commit hooks for $branch..."
    pre-commit run --all-files
    if ($LASTEXITCODE -ne 0) {
        Write-Output "Pre-commit hooks failed for $branch. Check pre-commit.log and fix issues."
        exit 1
    }


    # Commit changes using commit-push.ps1 (per CONTRIBUTING.md)
    Write-Output "Committing changes for $branch..."
    .\scripts\commit-push.ps1
    if ($LASTEXITCODE -ne 0) {
        Write-Output "commit-push.ps1 failed for $branch. Please check script output and fix issues."
        exit 1
    }
}

Write-Output "All branches merged into master successfully."
Write-Output "Pushing changes to remote..."
git push origin master
if ($LASTEXITCODE -ne 0) {
    Write-Output "Failed to push to master. Please resolve any issues (e.g., authentication, conflicts)."
    exit 1
}

Write-Output "Merge complete. Verify changes at https://github.com/ChubbyChuckles/project-template."
