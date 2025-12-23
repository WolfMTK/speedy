import warnings

import pytest

from speedy.exceptions import SpeedyWarning
from speedy.utils.signature import add_types_to_signature_namespace


def test_add_types_to_signature_namespace() -> None:
    ns = add_types_to_signature_namespace([int, str], {})
    assert ns == {"int": int, "str": str}


def test_add_types_to_signature_namespace_no_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPEEDY_WARN_SIGNATURE_NAMESPACE", raising=False)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        add_types_to_signature_namespace([int], {"int": int})


def test_add_types_to_signature_namespace_with_existing_types_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPEEDY_WARN_SIGNATURE_NAMESPACE", raising=False)
    with pytest.warns(SpeedyWarning):
        add_types_to_signature_namespace([int], {"int": str})


def test_add_types_to_signature_namespace_warn_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEEDY_WARN_SIGNATURE_NAMESPACE", "0")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        add_types_to_signature_namespace([int], {"int": str})
