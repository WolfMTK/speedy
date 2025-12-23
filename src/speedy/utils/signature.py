import os
import warnings
from typing import Any, Sequence

from speedy.exceptions.base import SpeedyWarning


def add_types_to_signature_namespace(
        signature_types: Sequence[Any],
        signature_namespace: dict[str, Any],
) -> dict[str, Any]:
    """ Add types to the signature namespace mapping. """
    show_warnings = os.getenv("SPEEDY_WARN_SIGNATURE_NAMESPACE") != "0"

    for type_obj in signature_types:
        type_name = type_obj.__name__
        if show_warnings and type_name in signature_namespace and signature_namespace.get(type_name) != type_obj:
            warnings.warn(
                f"Type `{type_name}` is already defined as a different type in the signature namespace. "
                "If this is intentional, you can disable this warning by setting "
                "SPEEDY_WARN_SIGNATURE_NAMESPACE=0",
                category=SpeedyWarning
            )
    signature_namespace.update({val.__name__: val for val in signature_types})
    return signature_namespace
