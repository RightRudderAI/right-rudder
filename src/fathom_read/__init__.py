"""fathom-read: catch the step where an AI agent contradicts a decision it already made."""
from .ops import Op, Finding, Verdict  # noqa: F401
from .client import read, expiry, ReadError  # noqa: F401

__version__ = "0.4.1"
__all__ = ["Op", "Finding", "Verdict", "read", "expiry", "ReadError", "read_file", "expiry_file", "load_ops"]


def load_ops(path: str, fmt: str = "auto", mapping_path: str = None):
    """Turn a trace file in any supported format into the op stream."""
    from .cli import load_ops as _load
    return _load(path, fmt, mapping_path)


def read_file(path: str, fmt: str = "auto", supersede=None, mapping_path: str = None, **kw) -> Verdict:
    """Read a trace file and return the hosted read's verdict."""
    return read(load_ops(path, fmt, mapping_path), supersede=supersede, **kw)


def expiry_file(path: str, fmt: str = "auto", supersede=None, mapping_path: str = None, **kw) -> dict:
    """Read a trace file and return the hosted expiry read's report."""
    return expiry(load_ops(path, fmt, mapping_path), supersede=supersede, **kw)
