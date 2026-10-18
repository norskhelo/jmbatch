import tempfile
import tkinter as tk
import unittest
from library_state_checks import check_library_state


class LibraryStateTest(unittest.TestCase):
    def test_read_return_refresh_and_favorites_retain_library_state(self):
        root = tk.Tk()
        try:
            with tempfile.TemporaryDirectory() as directory:
                check_library_state(root, directory)
        finally:
            root.destroy()
