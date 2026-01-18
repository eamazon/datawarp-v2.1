"""Simple spinner for inline progress display."""

import threading
import time
import sys

class Spinner:
    """Rotating cursor spinner for progress indication."""

    def __init__(self, message="Processing"):
        self.message = message
        self.chars = "|/-\\"
        self.idx = 0
        self.running = False
        self.thread = None
        self.last_len = 0

    def update_message(self, message):
        """Update the spinner message while running."""
        self.message = message

    def _spin(self):
        """Spin the cursor."""
        while self.running:
            # Build message with spinner
            msg = f'{self.message} {self.chars[self.idx]}'

            # Clear entire previous line, then write new message
            clear_line = '\r' + ' ' * max(self.last_len, len(msg)) + '\r'
            sys.stdout.write(clear_line + msg)
            sys.stdout.flush()

            self.last_len = len(msg)
            self.idx = (self.idx + 1) % len(self.chars)
            time.sleep(0.1)
    
    def start(self):
        """Start the spinner."""
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """Stop the spinner."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
        # Clear the line completely using tracked length
        sys.stdout.write('\r' + ' ' * self.last_len + '\r')
        sys.stdout.flush()
