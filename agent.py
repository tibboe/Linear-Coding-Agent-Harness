"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions.
"""

import asyncio
import time
from pathlib import Path
from typing import Optional

from claude_code_sdk import ClaudeSDKClient

from client import create_client
from logger import activity, start_heartbeat, stop_heartbeat, start_tool, end_tool
from mcp_diagnostics import diagnose_stuck_tool
from progress import print_session_header, print_progress_summary, is_linear_initialized
from prompts import get_initializer_prompt, get_coding_prompt, copy_spec_to_project


# Configuration
AUTO_CONTINUE_DELAY_SECONDS = 3
TOOL_WARNING_THRESHOLD = 300  # 5 minutes
TOOL_TIMEOUT_SECONDS = 600  # 10 minutes


async def tool_watchdog(tool_name: str, timeout_seconds: int = TOOL_TIMEOUT_SECONDS):
    """
    Watchdog that warns if a tool takes too long.

    Args:
        tool_name: Name of the tool being monitored
        timeout_seconds: Timeout threshold in seconds
    """
    await asyncio.sleep(timeout_seconds)

    # Tool has exceeded timeout - print warning and diagnostics
    print(f"\n⚠ WARNING: Tool '{tool_name}' has been running for >{timeout_seconds}s", flush=True)
    print(f"   This may indicate a hung MCP server or API timeout", flush=True)
    print(f"   Consider interrupting (Ctrl+C) and checking:", flush=True)
    print(f"   - Linear API status: https://status.linear.app", flush=True)
    print(f"   - MCP server logs", flush=True)
    print(f"   - Network connectivity", flush=True)

    # Print tool-specific diagnostics
    suggestions = diagnose_stuck_tool(tool_name, timeout_seconds)
    for suggestion in suggestions:
        print(f"   {suggestion}", flush=True)


async def run_agent_session(
    client: ClaudeSDKClient,
    message: str,
    project_dir: Path,
) -> tuple[str, str]:
    """
    Run a single agent session using Claude Agent SDK.

    Args:
        client: Claude SDK client
        message: The prompt to send
        project_dir: Project directory path

    Returns:
        (status, response_text) where status is:
        - "continue" if agent should continue working
        - "error" if an error occurred
    """
    try:
        # Send the query with activity tracking
        with activity("Sending prompt to Claude"):
            print("Sending prompt to Claude Agent SDK...\n")
            await client.query(message)

        # Collect response text and show tool use
        response_text = ""
        current_tool = None
        tool_start_time = None
        watchdog_task = None

        with activity("Processing agent response"):
            async for msg in client.receive_response():
                msg_type = type(msg).__name__

                # Handle AssistantMessage (text and tool use)
                if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                    for block in msg.content:
                        block_type = type(block).__name__

                        if block_type == "TextBlock" and hasattr(block, "text"):
                            response_text += block.text
                            print(block.text, end="", flush=True)
                        elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                            # Record tool start
                            current_tool = block.name
                            tool_start_time = time.time()

                            # Start activity tracking and watchdog
                            start_tool(current_tool)
                            watchdog_task = asyncio.create_task(tool_watchdog(current_tool, TOOL_TIMEOUT_SECONDS))

                            print(f"\n[Tool: {block.name}]", flush=True)
                            if hasattr(block, "input"):
                                input_str = str(block.input)
                                if len(input_str) > 200:
                                    print(f"   Input: {input_str[:200]}...", flush=True)
                                else:
                                    print(f"   Input: {input_str}", flush=True)

                # Handle UserMessage (tool results)
                elif msg_type == "UserMessage" and hasattr(msg, "content"):
                    for block in msg.content:
                        block_type = type(block).__name__

                        if block_type == "ToolResultBlock":
                            # Cancel watchdog when tool completes
                            if watchdog_task and not watchdog_task.done():
                                watchdog_task.cancel()

                            # Calculate tool duration and show result
                            duration = None
                            if tool_start_time:
                                duration = time.time() - tool_start_time
                                tool_start_time = None
                                current_tool = None

                            result_content = getattr(block, "content", "")
                            is_error = getattr(block, "is_error", False)

                            # Check if command was blocked by security hook
                            if "blocked" in str(result_content).lower():
                                print(f"   [BLOCKED] {result_content}", flush=True)
                            elif is_error:
                                # Show errors (truncated)
                                error_str = str(result_content)[:500]
                                print(f"   [Error] {error_str}", flush=True)
                            else:
                                # Tool succeeded - show duration
                                if duration and duration > TOOL_WARNING_THRESHOLD:
                                    print(f"   ⚠ Tool took {duration:.1f}s (>{TOOL_WARNING_THRESHOLD}s threshold)", flush=True)
                                elif duration:
                                    print(f"   [Done in {duration:.1f}s]", flush=True)
                                else:
                                    print("   [Done]", flush=True)

                            # End tool tracking
                            end_tool()

            print("\n" + "-" * 70 + "\n")
            return "continue", response_text

    except Exception as e:
        print(f"Error during agent session: {e}")
        return "error", str(e)


async def run_autonomous_agent(
    project_dir: Path,
    model: str,
    max_iterations: Optional[int] = None,
) -> None:
    """
    Run the autonomous agent loop.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        max_iterations: Maximum number of iterations (None for unlimited)
    """
    print("\n" + "=" * 70)
    print("  AUTONOMOUS CODING AGENT DEMO")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print(f"Model: {model}")
    if max_iterations:
        print(f"Max iterations: {max_iterations}")
    else:
        print("Max iterations: Unlimited (will run until completion)")
    print()

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Check if this is a fresh start or continuation
    # We use .linear_project.json as the marker for initialization
    is_first_run = not is_linear_initialized(project_dir)

    if is_first_run:
        print("Fresh start - will use initializer agent")
        print()

        # Ensure git is initialized before first session
        from git_operations import ensure_git_initialized
        git_success, git_msg = ensure_git_initialized(project_dir)
        if git_success:
            print(f"✓ Git initialized: {git_msg}")
        else:
            print(f"⚠ Git initialization warning: {git_msg}")
            print("  Agent will attempt to initialize via prompts")
        print()

        print("=" * 70)
        print("  NOTE: First session takes 10-20+ minutes!")
        print("  The agent is creating 50 Linear issues and setting up the project.")
        print("  This may appear to hang - it's working. Watch for [Tool: ...] output.")
        print("=" * 70)
        print()
        # Copy the app spec into the project directory for the agent to read
        copy_spec_to_project(project_dir)
    else:
        print("Continuing existing project (Linear initialized)")
        print_progress_summary(project_dir)

    # Start heartbeat for long-running operations
    start_heartbeat()

    # Main loop
    iteration = 0

    try:
        while True:
            iteration += 1

            # Check max iterations
            if max_iterations and iteration > max_iterations:
                print(f"\nReached max iterations ({max_iterations})")
                print("To continue, run the script again without --max-iterations")
                break

            # Print session header
            print_session_header(iteration, is_first_run)

            # Create client (fresh context)
            client = create_client(project_dir, model)

            # Choose prompt based on session type
            if is_first_run:
                prompt = get_initializer_prompt()
                is_first_run = False  # Only use initializer once
            else:
                prompt = get_coding_prompt()

            # Run session with async context manager
            async with client:
                status, response = await run_agent_session(client, prompt, project_dir)

            # Verify git state after session
            print("\n[Verifying git state...]")
            from git_operations import get_git_status
            git_status = get_git_status(project_dir)
            if git_status['initialized']:
                if git_status['uncommitted_changes']:
                    print("⚠ Uncommitted changes detected")
                    print("  The agent should commit these changes.")
                    print(f"  To commit manually: cd {project_dir.resolve()} && git add . && git commit")
                else:
                    print("✓ All changes committed")
                    if git_status['last_commit_hash']:
                        print(f"  Latest: {git_status['last_commit_hash'][:8]} - {git_status['last_commit_message'][:60]}")
            else:
                print("⚠ Git not initialized")

            # Handle status
            if status == "continue":
                print(f"\nAgent will auto-continue in {AUTO_CONTINUE_DELAY_SECONDS}s...")
                print_progress_summary(project_dir)
                await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

            elif status == "error":
                print("\nSession encountered an error")
                print("Will retry with a fresh session...")
                await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

            # Small delay between sessions
            if max_iterations is None or iteration < max_iterations:
                print("\nPreparing next session...\n")
                await asyncio.sleep(1)
    finally:
        # Cleanup heartbeat on exit
        stop_heartbeat()

    # Final summary
    print("\n" + "=" * 70)
    print("  SESSION COMPLETE")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print_progress_summary(project_dir)

    # Print instructions for running the generated application
    print("\n" + "-" * 70)
    print("  TO RUN THE GENERATED APPLICATION:")
    print("-" * 70)
    print(f"\n  cd {project_dir.resolve()}")
    print("  ./init.sh           # Run the setup script")
    print("  # Or manually:")
    print("  npm install && npm run dev")
    print("\n  Then open http://localhost:3000 (or check init.sh for the URL)")
    print("-" * 70)

    print("\nDone!")
