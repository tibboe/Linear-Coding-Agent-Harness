# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an autonomous coding agent harness that demonstrates long-running autonomous development using the Claude Agent SDK. The system implements a **two-agent pattern** with **Linear as the core project management system** for tracking all work.

**Key Architecture:**
- **Initializer Agent (Session 1):** Creates Linear project, generates 50+ feature issues, sets up project structure
- **Coding Agent (Sessions 2+):** Queries Linear for tasks, implements features, tests with Puppeteer, updates Linear
- **Session Handoff:** Agents communicate through Linear issues (status, comments) instead of local files

## Essential Commands

### Running the Agent

```bash
# Install dependencies (first time only)
pip install -r requirements.txt

# Set required environment variables
export CLAUDE_CODE_OAUTH_TOKEN='your-token'  # Run: claude setup-token
export LINEAR_API_KEY='lin_api_xxxxx'        # From: https://linear.app/YOUR-TEAM/settings/api

# Start autonomous agent
python autonomous_agent_demo.py --project-dir ./my_project

# Test run with limited iterations
python autonomous_agent_demo.py --project-dir ./my_project --max-iterations 3

# Use specific model
python autonomous_agent_demo.py --project-dir ./my_project --model claude-sonnet-4-5-20250929
```

### Testing Security Hooks

```bash
# Run security tests
python test_security.py

# Test specific scenarios
python -m pytest test_security.py::test_allowed_commands
python -m pytest test_security.py::test_blocked_commands
```

## Architecture & Code Structure

### Entry Point Flow

1. **autonomous_agent_demo.py** - Main entry point
   - Validates environment variables (CLAUDE_CODE_OAUTH_TOKEN, LINEAR_API_KEY)
   - Automatically places projects in `generations/` directory
   - Calls `run_autonomous_agent()` in agent.py

2. **agent.py** - Core agent loop
   - `run_autonomous_agent()` - Main loop that creates sessions
   - `run_agent_session()` - Runs single session with Claude SDK
   - Determines session type (initializer vs coding) based on `.linear_project.json` existence
   - AUTO_CONTINUE_DELAY_SECONDS (default: 3s) between sessions

3. **client.py** - Claude SDK client configuration
   - Creates ClaudeSDKClient with multi-layered security
   - Configures MCP servers: Puppeteer (stdio) and Linear (HTTP)
   - Sets up security hooks, sandboxing, and permissions
   - Security layers: OS-level sandbox → filesystem restrictions → bash allowlist

### Security Architecture (Defense in Depth)

**Three Security Layers:**

1. **OS-level Sandbox** (`client.py:103`)
   - Bash commands run in isolated environment
   - Prevents filesystem escape
   - Configured via: `"sandbox": {"enabled": True}`

2. **Filesystem Restrictions** (`client.py:104-112`)
   - All file operations restricted to project directory
   - Uses relative paths (`./**`) with cwd set to project_dir
   - Permissions: `allow: ["Read(./**)", "Write(./**)", ...]`

3. **Bash Command Allowlist** (`security.py:15-41`)
   - Only explicitly permitted commands can run
   - ALLOWED_COMMANDS: npm, node, git, ls, cat, grep, etc.
   - Additional validation for sensitive commands: pkill, chmod, init.sh
   - Pre-tool-use hook: `bash_security_hook()`

**Modifying Security:**
- Add/remove commands: Edit `ALLOWED_COMMANDS` in `security.py`
- Add validation logic: Extend `bash_security_hook()` or create new validators
- Update MCP permissions: Modify `security_settings["permissions"]["allow"]` in `client.py`

### MCP Server Configuration

**Puppeteer (Browser Automation):**
- Transport: stdio
- Command: `npx puppeteer-mcp-server`
- Tools: navigate, screenshot, click, fill, select, hover, evaluate
- Used for: UI testing and verification

**Linear (Project Management):**
- Transport: HTTP (Streamable HTTP - recommended over SSE)
- URL: `https://mcp.linear.app/mcp`
- Authorization: Bearer token via LINEAR_API_KEY
- Tools: list_teams, create_project, create_issue, update_issue, create_comment, etc.
- Used for: Issue tracking, session handoff, progress management

### Prompt System

**Prompts directory structure:**
- `prompts/app_spec.txt` - Application specification (copied to project dir)
- `prompts/initializer_prompt.md` - First session prompt (creates Linear issues)
- `prompts/coding_prompt.md` - Continuation session prompt (works issues)

**Prompt loading:**
- `prompts.py` - Utilities for loading prompts
- `get_initializer_prompt()` - Returns initializer prompt
- `get_coding_prompt()` - Returns coding agent prompt
- `copy_spec_to_project()` - Copies app spec to project directory

### Linear Integration

**State Management:**
- `.linear_project.json` - Local marker file for initialization state
- Contains: initialized flag, total_issues, meta_issue_id, project_id
- Created by initializer agent during first run

**Configuration:**
- `linear_config.py` - Constants for Linear integration
- Status workflow: Todo → In Progress → Done
- Priority mapping: 1=Urgent, 2=High, 3=Medium, 4=Low
- Label categories: functional, style, infrastructure
- META_ISSUE_TITLE: "[META] Project Progress Tracker"

**Progress Tracking:**
- `progress.py` - Utilities for tracking progress
- `is_linear_initialized()` - Checks if Linear project exists
- `print_progress_summary()` - Displays cached Linear state
- Actual progress tracked in Linear (issues, comments, status)

### Session Lifecycle

**First Run (Initializer):**
1. Creates project directory
2. Copies app_spec.txt to project
3. Creates ClaudeSDKClient with security settings
4. Loads initializer_prompt.md
5. Agent creates Linear project + 50 issues + META issue
6. Writes `.linear_project.json` marker file

**Subsequent Runs (Coding Agent):**
1. Detects `.linear_project.json` exists
2. Loads coding_prompt.md
3. Agent queries Linear for highest-priority Todo issue
4. Runs verification tests on previous work
5. Claims issue (status → In Progress)
6. Implements feature, tests with Puppeteer
7. Adds implementation comment to issue
8. Marks complete (status → Done)
9. Updates META issue with session summary
10. Auto-continues after 3 seconds

## Important Implementation Details

### Client Configuration

The `create_client()` function in `client.py` is the central configuration point:

```python
# Key parameters:
- model: Claude model (default: claude-opus-4-5-20251101)
- system_prompt: Agent's role and context
- allowed_tools: List of all permitted tools
- mcp_servers: Puppeteer and Linear configuration
- hooks: Pre-tool-use security hooks
- max_turns: 1000 (prevents infinite loops)
- cwd: Project directory (for relative path resolution)
- settings: Path to .claude_settings.json
```

### Security Hook Implementation

`bash_security_hook()` in `security.py` validates commands before execution:

1. Extracts all commands using `extract_commands()` (handles pipes, &&, ||, ;)
2. Checks each command against ALLOWED_COMMANDS
3. Runs additional validation for sensitive commands
4. Returns `{}` to allow or `{"decision": "block", "reason": "..."}` to block

**Command Parsing:**
- Uses `shlex.split()` for safe parsing (not regex)
- Handles compound commands (&&, ||, ;)
- Extracts base command names (handles paths like /usr/bin/python)
- Fail-safe: blocks if parsing fails

**Special Validators:**
- `validate_pkill_command()`: Only allows killing dev processes (node, npm, vite)
- `validate_chmod_command()`: Only allows +x mode (make executable)
- `validate_init_script()`: Only allows ./init.sh execution

## Customization Guide

### Change the Application Being Built

Edit `prompts/app_spec.txt` to specify a different application.

### Adjust Number of Issues

Edit `prompts/initializer_prompt.md` and change "50 issues" to desired count.

### Add New Allowed Commands

Edit `security.py`:

```python
ALLOWED_COMMANDS = {
    # ... existing commands ...
    "new_command",  # Add here
}

# If command needs validation:
COMMANDS_NEEDING_EXTRA_VALIDATION = {"pkill", "chmod", "init.sh", "new_command"}

# Then add validator function:
def validate_new_command(command_string: str) -> tuple[bool, str]:
    # Validation logic
    return True, ""  # or False, "reason"
```

### Add New MCP Tools

Edit `client.py`:

```python
# 1. Add tool names to list
NEW_MCP_TOOLS = [
    "mcp__service__tool_name",
]

# 2. Add to allowed_tools
allowed_tools=[
    *BUILTIN_TOOLS,
    *PUPPETEER_TOOLS,
    *LINEAR_TOOLS,
    *NEW_MCP_TOOLS,
]

# 3. Add to security settings
"permissions": {
    "allow": [
        # ... existing ...
        *NEW_MCP_TOOLS,
    ]
}

# 4. Configure MCP server
mcp_servers={
    # ... existing ...
    "service_name": {
        "command": "npx",
        "args": ["mcp-server-package"]
    }
}
```

## Dependencies

**Required:**
- `claude-code-sdk>=0.0.25` - Claude Agent SDK (Python)
- `CLAUDE_CODE_OAUTH_TOKEN` - OAuth token from `claude setup-token`
- `LINEAR_API_KEY` - Linear API key from workspace settings

**Optional (for development):**
- pytest - For running security tests
- Node.js/npm - For Puppeteer MCP server

## Troubleshooting

**Linear Integration Issues:**
- Check LINEAR_API_KEY is valid: verify at https://linear.app/YOUR-TEAM/settings/api
- Linear MCP uses HTTP transport (not SSE): ensure URL is `https://mcp.linear.app/mcp`
- First run creates 50+ issues: takes 10-20 minutes, watch for `[Tool: mcp__linear__create_issue]` output

**Security Hook Blocks:**
- Check `security.py:ALLOWED_COMMANDS` for command allowlist
- View blocked commands in output: `[BLOCKED] Command 'xxx' is not in the allowed commands list`
- Add to allowlist if safe, or investigate why agent is trying to run it

**Session Continuation:**
- Verify `.linear_project.json` exists in project directory
- Check file is valid JSON with `initialized: true`
- First run uses initializer prompt, subsequent runs use coding prompt

**Generated Project Not Running:**
- Check if `init.sh` exists and is executable
- Run manually: `cd project_dir && ./init.sh`
- Or: `npm install && npm run dev`
- Default URL typically: http://localhost:3000 (check init.sh for actual port)
