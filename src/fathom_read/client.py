"""The hosted read. The client sends an op stream and gets a verdict back."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Iterable, List, Optional, Tuple

from .ops import Op, RegroundVerdict, Verdict

DEFAULT_ENDPOINT = "https://read.embeddedriskanalytics.com/v1/read"
EXPIRY_ENDPOINT = "https://read.embeddedriskanalytics.com/v1/expiry"
REGROUND_ENDPOINT = "https://read.embeddedriskanalytics.com/v1/reground"
KEYS_ENDPOINT = "https://read.embeddedriskanalytics.com/v1/keys"
DEMO_KEY = "demo"  # rate-limited; a free key comes from `fathom key you@example.com` (POST /v1/keys)


class ReadError(RuntimeError):
    pass


def read(ops: Iterable[Op], supersede: Optional[List[Tuple[str, str]]] = None,
         key: Optional[str] = None, endpoint: Optional[str] = None, timeout: float = 30.0) -> Verdict:
    """Send the ops to the hosted read and return its verdict."""
    key = key or os.environ.get("FATHOM_API_KEY") or DEMO_KEY
    endpoint = endpoint or os.environ.get("FATHOM_ENDPOINT") or DEFAULT_ENDPOINT
    body = json.dumps({"ops": [o.as_dict() for o in ops], "supersede": [list(p) for p in (supersede or [])]}).encode()
    req = urllib.request.Request(endpoint, data=body, method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
        "User-Agent": "fathom-read/" + __import__("fathom_read").__version__})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Verdict.from_dict(json.loads(r.read().decode()))
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")
        if e.code == 401:
            raise ReadError("the read rejected the key; set FATHOM_API_KEY or get a free one with `fathom key you@example.com`") from None
        if e.code == 429:
            raise ReadError("the daily limit for this key is reached; a free key with a higher limit comes from `fathom key you@example.com`") from None
        raise ReadError(f"the read returned {e.code}: {msg[:200]}") from None
    except urllib.error.URLError as e:
        raise ReadError(f"could not reach the read at {endpoint}: {e.reason}") from None


def expiry(ops: Iterable[Op], supersede: Optional[List[Tuple[str, str]]] = None, calibration: Optional[str] = None,
           horizon: Optional[int] = None, alarm_multiple: Optional[float] = None,
           key: Optional[str] = None, endpoint: Optional[str] = None, timeout: float = 30.0) -> dict:
    """Send the ops to the hosted expiry read. Returns {"read": verdict dict, "expiry": {...}}.

    The expiry read reports, per step, the hazard that the agent's committed state spoils, the survival curve, the functional
    life remaining in steps, and two alarms, one that fires while a rejected action stands in the record and one that fires on
    committed load alone. Name a calibration for your workload (the service lists them at GET /v1/calibrations); with none named
    the read scores under a pooled default and labels the result a shape rather than a number."""
    key = key or os.environ.get("FATHOM_API_KEY") or DEMO_KEY
    endpoint = endpoint or os.environ.get("FATHOM_EXPIRY_ENDPOINT") or EXPIRY_ENDPOINT
    payload = {"ops": [o.as_dict() for o in ops], "supersede": [list(p) for p in (supersede or [])]}
    if calibration: payload["calibration"] = calibration
    if horizon: payload["horizon_k"] = int(horizon)
    if alarm_multiple: payload["alarm_mult"] = float(alarm_multiple)
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}", "User-Agent": "fathom-read/" + __import__("fathom_read").__version__})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")
        if e.code == 401:
            raise ReadError("the read rejected the key; set FATHOM_API_KEY or get a free one with `fathom key you@example.com`") from None
        if e.code == 429:
            raise ReadError("the daily limit for this key is reached; a free key with a higher limit comes from `fathom key you@example.com`") from None
        raise ReadError(f"the read returned {e.code}: {msg[:200]}") from None
    except urllib.error.URLError as e:
        raise ReadError(f"could not reach the read at {endpoint}: {e.reason}") from None


def reground(ops: Iterable[Op], proposals: Iterable[dict], supersede: Optional[List[Tuple[str, str]]] = None,
             key: Optional[str] = None, endpoint: Optional[str] = None, timeout: float = 30.0) -> RegroundVerdict:
    """The repair in front of one step. Send the ops so far and the actions the agent proposes next; get back a decision.

    proposals are op-shaped dicts in the agent's own order ({"op": "add", "kind": "research", "key": "queries",
    "value": "..."} for a query the agent wants to run, a set for a value it wants to write, an answer with refs for a
    report it wants to cite from). The service evaluates each one against the committed state the ops build and returns
    proceed, filter (take the first of `keep`), or reground (put `facts` back in front of the agent, see
    RegroundVerdict.prompt_note, and ask again). Needs a key; the demo key covers the reads only."""
    key = key or os.environ.get("FATHOM_API_KEY") or DEMO_KEY
    endpoint = endpoint or os.environ.get("FATHOM_REGROUND_ENDPOINT") or REGROUND_ENDPOINT
    payload = {"ops": [o.as_dict() for o in ops], "supersede": [list(p) for p in (supersede or [])],
               "proposals": [dict(p) for p in proposals]}
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}", "User-Agent": "fathom-read/" + __import__("fathom_read").__version__})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return RegroundVerdict.from_dict(json.loads(r.read().decode()))
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")
        if e.code == 401:
            raise ReadError("the repair needs a key; get a free one with `fathom key you@example.com` and set FATHOM_API_KEY") from None
        if e.code == 429:
            raise ReadError("the daily limit for this key is reached; it resets at midnight UTC") from None
        raise ReadError(f"the repair returned {e.code}: {msg[:200]}") from None
    except urllib.error.URLError as e:
        raise ReadError(f"could not reach the repair at {endpoint}: {e.reason}") from None


def request_key(email: str, endpoint: Optional[str] = None, timeout: float = 30.0) -> dict:
    """Ask the service for a free key. Returns {"key", "tier", "daily_limit", "note"}; the key is shown once."""
    endpoint = endpoint or os.environ.get("FATHOM_KEYS_ENDPOINT") or KEYS_ENDPOINT
    req = urllib.request.Request(endpoint, data=json.dumps({"email": email}).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "fathom-read/" + __import__("fathom_read").__version__})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")
        raise ReadError(f"key request returned {e.code}: {msg[:200]}") from None
    except urllib.error.URLError as e:
        raise ReadError(f"could not reach the service at {endpoint}: {e.reason}") from None
