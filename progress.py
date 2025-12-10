"""
Progress Tracking Utilities
===========================

Functions for tracking and displaying progress of the autonomous coding agent.
Progress is tracked via Linear issues, with local state cached in .linear_project.json.
"""

import json
from pathlib import Path

from linear_config import LINEAR_PROJECT_MARKER


def load_linear_project_state(project_dir: Path) -> dict | None:
    """
    Load the Linear project state from the marker file.

    Args:
        project_dir: Directory containing .linear_project.json

    Returns:
        Project state dict or None if not initialized
    """
    marker_file = project_dir / LINEAR_PROJECT_MARKER

    if not marker_file.exists():
        return None

    try:
        with open(marker_file, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def is_linear_initialized(project_dir: Path) -> bool:
    """
    Check if Linear project has been initialized.

    Args:
        project_dir: Directory to check

    Returns:
        True if .linear_project.json exists and is valid
    """
    state = load_linear_project_state(project_dir)
    return state is not None and state.get("initialized", False)


def print_session_header(session_num: int, is_initializer: bool) -> None:
    """Print a formatted header for the session."""
    session_type = "INITIALIZER" if is_initializer else "CODING AGENT"

    print("\n" + "=" * 70)
    print(f"  SESSION {session_num}: {session_type}")
    print("=" * 70)
    print()


def print_progress_summary(project_dir: Path) -> None:
    """
    Print a summary of current progress.

    Since actual progress is tracked in Linear, this reads the local
    state file for cached information. The agent updates Linear directly
    and reports progress in session comments.
    """
    state = load_linear_project_state(project_dir)

    if state is None:
        print("\nProgress: Linear project not yet initialized")
        return

    total = state.get("total_issues", 0)
    meta_issue = state.get("meta_issue_id", "unknown")

    print(f"\nLinear Project Status:")
    print(f"  Total issues created: {total}")
    print(f"  META issue ID: {meta_issue}")
    print(f"  (Check Linear for current Done/In Progress/Todo counts)")

    # Add git status
    from git_operations import get_git_status
    git_status = get_git_status(project_dir)
    if git_status['initialized'] and git_status['last_commit_hash']:
        print(f"\nGit Status:")
        print(f"  Last commit: {git_status['last_commit_hash'][:8]}")


def print_git_guidance(project_dir: Path) -> None:
    """
    Print guidance about where to find git changes.

    Helps users understand that commits happen in the generated
    project directory, not the harness directory.

    Args:
        project_dir: Path to project directory
    """
    from git_operations import get_git_status

    print("\n" + "=" * 70)
    print("  GIT REPOSITORY LOCATION")
    print("=" * 70)
    print(f"\nYour git repository is at:")
    print(f"  📁 {project_dir.resolve()}")
    print(f"\n⚠ This is NOT the harness directory you may have open in your editor.")
    print(f"\nTo view git history in Cursor/VS Code:")
    print(f"  File → Open Folder → {project_dir.resolve()}")
    print(f"\nTo view git history in terminal:")
    print(f"  cd {project_dir.resolve()}")
    print(f"  git log --oneline -20")
    print(f"  git status")

    status = get_git_status(project_dir)
    if status['initialized']:
        print(f"\n📊 Git Status:")
        print(f"  ✓ Repository initialized")
        print(f"  Branch: {status['branch']}")
        if status['last_commit_hash']:
            print(f"  Last commit: {status['last_commit_hash'][:8]} - {status['last_commit_message'][:50]}...")
        if status['uncommitted_changes']:
            print(f"  ⚠ Uncommitted changes present")
        else:
            print(f"  ✓ Working tree clean")
    else:
        print(f"\n⚠ Git not initialized yet")
        print(f"  The agent will initialize it in the first session")

    print("=" * 70 + "\n")
