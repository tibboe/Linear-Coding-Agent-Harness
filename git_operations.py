"""
Git Operations for Autonomous Agent
===================================

Wrapper functions for git operations with verification and error handling.
All git commands execute via subprocess and pass through bash security hooks.

This module provides:
- Git repository initialization with verification
- Standardized commits with Linear issue tracking
- Status checking for session verification
- Remote repository setup for GitHub integration
"""

import subprocess
from pathlib import Path
from typing import Optional


def ensure_git_initialized(project_dir: Path) -> tuple[bool, str]:
    """
    Ensure git repository is initialized in the project directory.

    Checks if .git directory exists. If not, runs `git init`.
    Verifies initialization succeeded.

    Args:
        project_dir: Path to project directory

    Returns:
        (success: bool, message: str)
        success=True if .git exists or was created successfully
        message describes what happened or any error

    Example:
        success, msg = ensure_git_initialized(Path("./my_project"))
        if success:
            print(f"Git ready: {msg}")
    """
    git_dir = project_dir / ".git"

    # Check if already initialized
    if git_dir.exists() and git_dir.is_dir():
        return True, "Repository already initialized"

    # Try to initialize
    try:
        result = subprocess.run(
            ["git", "init"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            # Verify .git was created
            if git_dir.exists():
                return True, "Repository initialized successfully"
            else:
                return False, "git init succeeded but .git directory not found"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            return False, f"git init failed: {error_msg}"

    except FileNotFoundError:
        return False, "git command not found - please install git"
    except subprocess.TimeoutExpired:
        return False, "git init timed out"
    except Exception as e:
        return False, f"Unexpected error during git init: {str(e)}"


def get_git_status(project_dir: Path) -> dict:
    """
    Get current git repository status.

    Args:
        project_dir: Path to project directory

    Returns:
        Dictionary with status information:
        {
            'initialized': bool - True if .git exists
            'uncommitted_changes': bool - True if working tree is dirty
            'last_commit_hash': str - Latest commit hash (empty if no commits)
            'last_commit_message': str - Latest commit message (empty if no commits)
            'branch': str - Current branch name (empty if error)
        }

    Example:
        status = get_git_status(Path("./my_project"))
        if status['uncommitted_changes']:
            print("Please commit your changes")
    """
    status = {
        'initialized': False,
        'uncommitted_changes': False,
        'last_commit_hash': '',
        'last_commit_message': '',
        'branch': ''
    }

    # Check if git is initialized
    git_dir = project_dir / ".git"
    if not (git_dir.exists() and git_dir.is_dir()):
        return status

    status['initialized'] = True

    try:
        # Get current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            status['branch'] = result.stdout.strip()

        # Check for uncommitted changes
        # git diff-index returns 0 if clean, 1 if dirty
        result = subprocess.run(
            ["git", "diff-index", "--quiet", "HEAD", "--"],
            cwd=str(project_dir),
            capture_output=True,
            timeout=5
        )
        # returncode 1 means changes exist
        status['uncommitted_changes'] = (result.returncode != 0)

        # Get last commit info
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            status['last_commit_hash'] = result.stdout.strip()

            # Get commit message
            result = subprocess.run(
                ["git", "log", "-1", "--format=%s"],
                cwd=str(project_dir),
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                status['last_commit_message'] = result.stdout.strip()

    except subprocess.TimeoutExpired:
        # Return partial status on timeout
        pass
    except Exception:
        # Return partial status on error
        pass

    return status


def commit_format_with_issue(
    message: str,
    issue_id: Optional[str] = None,
    issue_title: Optional[str] = None,
    details: str = ""
) -> str:
    """
    Format commit message with Linear issue information.

    Args:
        message: Main commit message (first line)
        issue_id: Linear issue ID (e.g., "TIB-57")
        issue_title: Linear issue title
        details: Optional additional details

    Returns:
        Formatted commit message string

    Example:
        msg = commit_format_with_issue(
            "Implement user authentication",
            issue_id="TIB-57",
            issue_title="Add login flow",
            details="Added OAuth2 support"
        )
    """
    lines = [message]

    if details:
        lines.append("")
        lines.append(details)

    if issue_id:
        lines.append("")
        lines.append(f"Linear issue: {issue_id}")

        # Add issue URL if we have both ID and title
        if issue_title:
            # Extract team identifier from issue ID (e.g., "TIB" from "TIB-57")
            team = issue_id.split("-")[0].lower() if "-" in issue_id else "team"
            issue_slug = issue_id.lower()
            lines.append(f"Issue: https://linear.app/{team}/issue/{issue_slug}")

    return "\n".join(lines)


def create_commit(
    project_dir: Path,
    message: str,
    issue_id: Optional[str] = None,
    issue_title: Optional[str] = None,
    details: str = ""
) -> tuple[bool, str, str]:
    """
    Create a git commit with standardized format.

    Stages all changes and creates a commit. If issue information is provided,
    formats the commit message to include Linear issue details.

    Args:
        project_dir: Path to project directory
        message: Main commit message
        issue_id: Optional Linear issue ID (e.g., "TIB-57")
        issue_title: Optional Linear issue title
        details: Optional additional details for commit body

    Returns:
        (success: bool, commit_hash: str, error_message: str)
        success=True if commit created successfully
        commit_hash=short hash of the new commit (empty if failed)
        error_message=error details (empty if successful)

    Example:
        success, hash, error = create_commit(
            Path("./my_project"),
            "Implement feature",
            issue_id="TIB-57",
            issue_title="Add authentication"
        )
        if success:
            print(f"Committed: {hash}")
    """
    try:
        # Stage all changes
        result = subprocess.run(
            ["git", "add", "."],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            return False, "", f"git add failed: {error}"

        # Check if there's anything to commit
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(project_dir),
            capture_output=True,
            timeout=10
        )

        # returncode 0 means no changes staged
        if result.returncode == 0:
            return True, "", "No changes to commit"

        # Format commit message
        commit_msg = commit_format_with_issue(message, issue_id, issue_title, details)

        # Create commit
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            return False, "", f"git commit failed: {error}"

        # Get the commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            commit_hash = result.stdout.strip()
            return True, commit_hash, ""
        else:
            # Commit succeeded but couldn't get hash
            return True, "", ""

    except subprocess.TimeoutExpired:
        return False, "", "git command timed out"
    except FileNotFoundError:
        return False, "", "git command not found - please install git"
    except Exception as e:
        return False, "", f"Unexpected error: {str(e)}"


def setup_remote(project_dir: Path, remote_url: str) -> tuple[bool, str]:
    """
    Set up git remote (origin) for the repository.

    Args:
        project_dir: Path to project directory
        remote_url: GitHub remote URL (e.g., https://github.com/user/repo.git)

    Returns:
        (success: bool, message: str)
        success=True if remote was added successfully
        message=success confirmation or error details

    Example:
        success, msg = setup_remote(
            Path("./my_project"),
            "https://github.com/user/repo.git"
        )
        if success:
            print(msg)
            # Now you can: git push -u origin main
    """
    try:
        # Check if remote already exists
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            existing_url = result.stdout.strip()
            if existing_url == remote_url:
                return True, f"Remote 'origin' already set to {remote_url}"
            else:
                return False, f"Remote 'origin' already exists with different URL: {existing_url}"

        # Add the remote
        result = subprocess.run(
            ["git", "remote", "add", "origin", remote_url],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            return False, f"Failed to add remote: {error}"

        # Verify it was added
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            verified_url = result.stdout.strip()
            if verified_url == remote_url:
                return True, f"Remote 'origin' configured successfully: {remote_url}"
            else:
                return False, f"Remote added but URL mismatch: {verified_url}"
        else:
            return False, "Remote added but verification failed"

    except subprocess.TimeoutExpired:
        return False, "git command timed out"
    except FileNotFoundError:
        return False, "git command not found - please install git"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"
