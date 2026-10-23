"""
core/state.py — Parámetros compartidos entre páginas (modelo de ciclo).
"""
from __future__ import annotations

import streamlit as st

from .physics import COMPRESSION_MODES, CycleParams

DEFAULTS = CycleParams().as_dict()


def cp() -> dict:
    if "cp" not in st.session_state:
        st.session_state["cp"] = dict(DEFAULTS)
    return st.session_state["cp"]


def _sync(field: str, key: str):
    st.session_state["cp"][field] = st.session_state[key]


def slider(label: str, field: str, page: str, min_value, max_value, step, fmt=None, help=None):
    params = cp()
    key = f"{page}__{field}"
    return st.slider(label, min_value=min_value, max_value=max_value, value=params[field], step=step,
                     format=fmt, key=key, help=help, on_change=_sync, args=(field, key))


def compression(page: str, label: str = "Proceso de inserción/compresión (ABIS)"):
    params = cp()
    key = f"{page}__compression"
    opts = list(COMPRESSION_MODES)
    return st.selectbox(label, opts, index=opts.index(params["compression"]), key=key,
                        on_change=_sync, args=("compression", key))


def reset():
    st.session_state["cp"] = dict(DEFAULTS)
    for k in list(st.session_state.keys()):
        if "__" in str(k):
            del st.session_state[k]


def params() -> CycleParams:
    return CycleParams(**cp())
