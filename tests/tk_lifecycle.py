"""Release cyclic Tk test fixtures before worker-thread tests can run GC."""

import gc
import threading


def collect_tk_variables() -> None:
    """unittest module teardown runs on the Tk/main thread, after roots close."""
    if threading.current_thread() is not threading.main_thread():
        raise AssertionError("Tk variables must be released on the main thread")
    gc.collect()
