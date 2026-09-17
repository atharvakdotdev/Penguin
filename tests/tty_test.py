import pty
import os

pid, fd = pty.fork()

if pid == 0:
    os.execvp("vim", ["vim"])