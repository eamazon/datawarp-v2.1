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
        
    def _spin(self):
        """Spin the cursor."""
        while self.running:
            sys.stdout.write(f'\r{self.message} {self.chars[self.idx]}')
            sys.stdout.flush()
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
        sys.stdout.write('\r')  # Clear the line
        sys.stdout.flush()
