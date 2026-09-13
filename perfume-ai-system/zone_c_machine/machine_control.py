"""Future — machine control. When stock concentrations are fixed here, set
zone_b_chemistry.safety_engine.CONCENTRATE_FRACTION to the true concentrate-in-product fraction."""
from __future__ import annotations


def dispense(*args, **kwargs):
    raise NotImplementedError("Zone C is out of scope for v1")
