#!/usr/bin/env python3
"""
Set up GitHub remote for generated project.

This helper script configures a GitHub remote for a project generated
by the autonomous coding agent.

Usage:
    python setup_git_remote.py --project-dir ./generations/my_project \\
        --remote-url https://github.com/user/repo.git

Then push:
    cd generations/my_project
    git push -u origin main
"""

import argparse
import sys
from pathlib import Path

from git_operations import setup_remote, get_git_status


def main() -> int:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Set up GitHub remote for autonomous agent project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Set up remote for a generated project
  python setup_git_remote.py \\
      --project-dir ./generations/my_project \\
      --remote-url https://github.com/username/my-project.git

  # Then push to GitHub
  cd generations/my_project
  git push -u origin main

Notes:
  - Create the GitHub repository manually first
  - The project directory must already have git initialized
  - Use HTTPS or SSH URLs depending on your authentication setup
        """,
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        required=True,
        help="Path to generated project (e.g., ./generations/my_project)",
    )

    parser.add_argument(
        "--remote-url",
        type=str,
        required=True,
        help="GitHub remote URL (e.g., https://github.com/user/repo.git or git@github.com:user/repo.git)",
    )

    args = parser.parse_args()

    # Verify project directory exists
    if not args.project_dir.exists():
        print(f"❌ Error: Project directory does not exist: {args.project_dir}")
        print(f"   Make sure you're using the correct path")
        return 1

    # Verify project has git initialized
    status = get_git_status(args.project_dir)
    if not status["initialized"]:
        print(f"❌ Error: {args.project_dir} is not a git repository")
        print(f"   Make sure the agent has initialized git first")
        print(f"   Or run: cd {args.project_dir} && git init")
        return 1

    print(f"Setting up remote for: {args.project_dir.resolve()}")
    print(f"Remote URL: {args.remote_url}")
    print()

    # Set up the remote
    success, msg = setup_remote(args.project_dir, args.remote_url)

    if success:
        print(f"✅ {msg}")
        print()
        print(f"📤 To push to GitHub:")
        print(f"   cd {args.project_dir.resolve()}")

        # Suggest appropriate branch name
        branch = status.get("branch", "main")
        if branch:
            print(f"   git push -u origin {branch}")
        else:
            print(f"   git push -u origin main  # or master, depending on your default branch")

        print()
        print(f"💡 Tips:")
        print(f"   - The agent's commits will accumulate locally")
        print(f"   - Push manually whenever you want to sync with GitHub")
        print(f"   - You can configure automatic push by modifying the agent code")
        return 0
    else:
        print(f"❌ {msg}")
        print()
        print(f"💡 Troubleshooting:")
        print(f"   - Check that the remote URL is correct")
        print(f"   - Ensure you have access to the GitHub repository")
        print(f"   - If remote already exists, you may need to remove it first:")
        print(f"     cd {args.project_dir.resolve()}")
        print(f"     git remote remove origin")
        print(f"     # Then run this script again")
        return 1


if __name__ == "__main__":
    sys.exit(main())
