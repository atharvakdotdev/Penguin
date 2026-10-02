import os
import pty
import select
import signal
import threading
from datetime import datetime, timezone


class TestRunner:
    def __init__(self):
        self.auto_allow = True
        self._pending_approvals = {}
        self._shutdown_event = threading.Event()
        self.windowobj = None

    def _record_command(self, command, success, output):
        print(f"\n[record] success={success}")

    def _remove_command_from_history(self, command):
        pass

    def _event_session_id(self):
        return "test-session"

    def sendEvent(self, *args):
        pass

    def run_command(self, command, use_sudo=False, command_id=None):
        """Execute a command through a PTY and emit its result."""
        command_id = command_id or command
        approval = None

        if not self.auto_allow:
            approval = self._pending_approvals.setdefault(
                command_id, threading.Event()
            )

            try:
                while not approval.wait(timeout=0.5):
                    if self._shutdown_event.is_set():
                        return {
                            "success": False,
                            "output": "",
                            "error": "Command approval cancelled.",
                            "return_code": -1,
                        }
            finally:
                self._pending_approvals.pop(command_id, None)

        try:
            if use_sudo:
                command = f"sudo {command}"

            pid, fd = pty.fork()

            if pid == 0:
                os.execl(
                    "/bin/bash",
                    "bash",
                    "-c",
                    command
                )

            output = b""
            process_output_received = False

            while True:
                ready, _, _ = select.select(
                    [fd],
                    [],
                    [],
                    0.1
                )

                if fd in ready:
                    try:
                        data = os.read(fd, 4096)

                        if data:
                            output += data
                            process_output_received = True

                            print(
                                data.decode(errors="replace"),
                                end="",
                                flush=True
                            )

                    except OSError:
                        break

                finished_pid, status = os.waitpid(
                    pid,
                    os.WNOHANG
                )

                if finished_pid == pid:
                    return_code = os.waitstatus_to_exitcode(status)
                    break

                # Interactive-capable command produced output
                # but has not exited.
                if process_output_received:
                    print("\n[process still running -> treating as successful launch]")

                    os.kill(
                        pid,
                        signal.SIGTERM
                    )

                    try:
                        os.waitpid(pid, 0)
                    except ChildProcessError:
                        pass

                    output_text = output.decode(
                        errors="replace"
                    )

                    self._record_command(
                        command,
                        True,
                        output_text
                    )

                    self._remove_command_from_history(
                        command
                    )

                    return {
                        "success": True,
                        "output": "Command executed successfully.",
                        "error": "",
                        "return_code": 0,
                    }

            output_text = output.decode(
                errors="replace"
            )

            success = return_code == 0

            self._record_command(
                command,
                success,
                output_text
            )

            self._remove_command_from_history(
                command
            )

            return {
                "success": success,
                "output": output_text,
                "error": "" if success else output_text,
                "return_code": return_code,
            }

        except Exception as e:
            error = str(e)

            self._record_command(
                command,
                False,
                error
            )

            self._remove_command_from_history(
                command
            )

            return {
                "success": False,
                "output": "",
                "error": error,
                "return_code": -1,
            }

        finally:
            if approval is not None:
                self._pending_approvals.pop(
                    command_id,
                    None
                )


def test(name, command):
    print("\n" + "=" * 60)
    print(f"TEST: {name}")
    print(f"COMMAND: {command}")
    print("=" * 60)

    runner = TestRunner()

    result = runner.run_command(command)

    print("\n--- RESULT ---")
    print(f"success:     {result['success']}")
    print(f"output:      {result['output']!r}")
    print(f"error:       {result['error']!r}")
    print(f"return_code: {result['return_code']}")


if __name__ == "__main__":

    # 1. Normal command
    test(
        "Normal command",
        ["echo hello"]
    )

    # 2. Command that doesn't exist
    test(
        "Non-existent command",
        ["this_command_does_not_exist"]
    )

    # 3. Interactive-capable command used only
    #    to check whether it launches
    # test("Neovim launch test", "nvim")
    # test("Python REPL", "python3")
    # test("Bash", "bash")
    # test("Nano", "nano")
    # test("Top", "top")