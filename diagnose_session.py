#!/usr/bin/env python3
"""
Diagnose stuck or hung agent sessions.

Usage:
    python diagnose_session.py --project-dir ./generations/my_project
"""

import argparse
from pathlib import Path
from git_operations import get_git_status
from progress import load_linear_project_state


def main():
    """Diagnose agent session issues."""
    parser = argparse.ArgumentParser(description="Diagnose agent session issues")
    parser.add_argument("--project-dir", type=Path, required=True, help="Project directory to diagnose")
    args = parser.parse_args()

    print("=" * 70)
    print("  SESSION DIAGNOSTICS")
    print("=" * 70)

    # Check project state
    state = load_linear_project_state(args.project_dir)
    if state:
        print(f"\n✓ Linear project initialized")
        print(f"  Project ID: {state.get('project_id')}")
        print(f"  Total issues: {state.get('total_issues')}")
    else:
        print(f"\n✗ Linear project not initialized")

    # Check git state
    git_status = get_git_status(args.project_dir)
    if git_status['initialized']:
        print(f"\n✓ Git repository initialized")
        if git_status['last_commit_hash']:
            print(f"  Last commit: {git_status['last_commit_hash'][:8]}")
        if git_status['uncommitted_changes']:
            print(f"  ⚠ Uncommitted changes present")
    else:
        print(f"\n✗ Git not initialized")

    # Check for common issues
    print(f"\n📋 Common Issues to Check:")
    print(f"  1. Linear API status: https://status.linear.app")
    print(f"  2. Check if LINEAR_API_KEY is still valid")
    print(f"  3. Look for [Tool: ...] in log that never completed")
    print(f"  4. Check if MCP servers are running")
    print(f"  5. Try with --max-iterations 1 for testing")

    print("=" * 70)


if __name__ == "__main__":
    main()
