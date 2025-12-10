"""
Timestamped Logger with Activity Tracking
=========================================

Provides comprehensive logging with timestamps and activity indicators
for the autonomous coding agent.

Features:
- Timestamps on all output (actual time + elapsed time)
- Heartbeat messages during long silences
- Activity tracking to show what the agent is doing
- Minimal code changes via monkey-patching print()
"""

import asyncio
import builtins
from contextlib import contextmanager
from datetime import datetime
from typing import Optional


class TimestampedLogger:
    """
    Centralized logger with timestamps and activity indicators.

    Replaces built-in print() to add timestamps to all output.
    Provides heartbeat mechanism for long-running operations.
    Tracks current activity for better visibility.
    """

    def __init__(self):
        """Initialize the logger."""
        self.session_start_time = datetime.now()
        self.last_output_time = datetime.now()
        self.current_activity: Optional[str] = None
        self.current_tool_start_time: Optional[datetime] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.heartbeat_interval = 30  # seconds
        self._original_print = builtins.print
        self._lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None

    def format_timestamp(self) -> str:
        """
        Format timestamp with actual time and elapsed time.

        Returns:
            Formatted timestamp string: "14:23:45 [+00:05:23]"
        """
        now = datetime.now()

        # Actual time in HH:MM:SS format
        actual_time = now.strftime("%H:%M:%S")

        # Elapsed time since session start
        elapsed = now - self.session_start_time
        elapsed_seconds = int(elapsed.total_seconds())
        hours = elapsed_seconds // 3600
        minutes = (elapsed_seconds % 3600) // 60
        seconds = elapsed_seconds % 60
        elapsed_time = f"[+{hours:02d}:{minutes:02d}:{seconds:02d}]"

        return f"{actual_time} {elapsed_time}"

    def timestamped_print(self, *args, **kwargs):
        """
        Drop-in replacement for print() with timestamp prefix.

        Handles multiline output by timestamping each line separately.
        Preserves all print() kwargs (end, flush, file, etc.).
        """
        # Update last output time
        self.last_output_time = datetime.now()

        # Get the separator (default is space)
        sep = kwargs.get('sep', ' ')

        # Format message (handle multiple args)
        if len(args) == 0:
            message = ""
        elif len(args) == 1:
            message = str(args[0])
        else:
            message = sep.join(str(arg) for arg in args)

        # Split multiline messages and add timestamp to each line
        if message:
            lines = message.split("\n")
            timestamped_lines = []
            for line in lines:
                if line.strip():  # Non-empty lines get timestamps
                    timestamped_lines.append(f"{self.format_timestamp()} {line}")
                else:  # Empty lines stay empty (preserve formatting)
                    timestamped_lines.append("")

            # Join and print
            final_message = "\n".join(timestamped_lines)
        else:
            # Empty print() call - just print empty line with timestamp
            final_message = self.format_timestamp()

        # Use original print with all kwargs preserved
        self._original_print(final_message, **kwargs)

    def set_activity(self, activity: Optional[str]):
        """
        Set current activity for heartbeat messages.

        Args:
            activity: Description of current operation, or None to clear
        """
        self.current_activity = activity

    def start_tool(self, tool_name: str):
        """
        Mark that a tool has started.

        Sets the activity and starts tracking tool duration.

        Args:
            tool_name: Name of the tool being executed
        """
        self.current_tool_start_time = datetime.now()
        self.current_activity = f"Waiting for {tool_name}"

    def end_tool(self):
        """
        Mark that a tool has finished.

        Clears tool duration tracking.
        """
        self.current_tool_start_time = None

    @contextmanager
    def activity(self, activity_name: str):
        """
        Context manager for tracking activities.

        Usage:
            with activity("Processing response"):
                # Do work
                pass

        Args:
            activity_name: Description of the activity
        """
        old_activity = self.current_activity
        self.current_activity = activity_name
        try:
            yield
        finally:
            self.current_activity = old_activity

    async def heartbeat_loop(self):
        """
        Background task that prints heartbeat every 30s during silence.

        Only prints if there has been no output for 30+ seconds.
        Shows current activity in the heartbeat message.
        Shows tool duration if waiting for a tool.
        """
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)

                # Check if we've been silent for 30+ seconds
                silence_duration = (datetime.now() - self.last_output_time).total_seconds()

                if silence_duration >= self.heartbeat_interval:
                    # Build heartbeat message with tool duration if applicable
                    activity_msg = ""
                    if self.current_activity:
                        activity_msg = f" ({self.current_activity}"

                        # Add tool duration if we're waiting for a tool
                        if self.current_tool_start_time:
                            tool_duration = (datetime.now() - self.current_tool_start_time).total_seconds()
                            activity_msg += f" - {tool_duration:.0f}s"

                        activity_msg += ")"

                    self.timestamped_print(f"[Heartbeat] Still working...{activity_msg}")
        except asyncio.CancelledError:
            # Normal cancellation when stopping heartbeat
            pass
        except Exception as e:
            # Unexpected error in heartbeat - log but don't crash
            self._original_print(f"[Heartbeat Error] {e}")

    def start_heartbeat(self):
        """
        Start heartbeat background task.

        Safe to call multiple times - will not create duplicate tasks.
        """
        if self.heartbeat_task is None or self.heartbeat_task.done():
            try:
                loop = asyncio.get_event_loop()
                self.heartbeat_task = loop.create_task(self.heartbeat_loop())
            except RuntimeError:
                # No event loop available - heartbeat won't work
                # This is OK, just means we're not in async context
                pass

    def stop_heartbeat(self):
        """
        Stop heartbeat background task.

        Safe to call even if heartbeat is not running.
        """
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            self.heartbeat_task = None

    def install(self):
        """
        Install as global print() replacement.

        After calling this, all print() calls in all modules
        will automatically get timestamps.
        """
        builtins.print = self.timestamped_print

    def uninstall(self):
        """
        Restore original print().

        Returns print() to its original behavior.
        """
        builtins.print = self._original_print

    def reset_session_time(self):
        """
        Reset session start time (for new sessions).

        Elapsed time will be calculated from this new start time.
        """
        self.session_start_time = datetime.now()
        self.last_output_time = datetime.now()


# Global singleton instance
_logger = TimestampedLogger()


# Public API
def install_logger():
    """Install timestamped logger globally."""
    _logger.install()


def uninstall_logger():
    """Uninstall timestamped logger."""
    _logger.uninstall()


def start_heartbeat():
    """Start heartbeat background task."""
    _logger.start_heartbeat()


def stop_heartbeat():
    """Stop heartbeat background task."""
    _logger.stop_heartbeat()


def set_activity(activity: str):
    """Set current activity for heartbeat."""
    _logger.set_activity(activity)


def start_tool(tool_name: str):
    """Mark that a tool has started."""
    _logger.start_tool(tool_name)


def end_tool():
    """Mark that a tool has finished."""
    _logger.end_tool()


def activity(activity_name: str):
    """Context manager for activity tracking."""
    return _logger.activity(activity_name)


def reset_session_time():
    """Reset session start time."""
    _logger.reset_session_time()
