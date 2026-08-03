from __future__ import annotations

from hypothesis import given, settings, strategies as st
from hermes_bilevel.canonical import hash_canonical


jsonish = st.recursive(
    st.none() | st.booleans() | st.integers(min_value=-10**6, max_value=10**6) | st.text(max_size=20),
    lambda children: st.lists(children, max_size=5) | st.dictionaries(st.text(min_size=1, max_size=8), children, max_size=5),
    max_leaves=20,
)


@given(jsonish)
@settings(max_examples=40)
def test_hash_deterministic(x):
    assert hash_canonical(x) == hash_canonical(x)
