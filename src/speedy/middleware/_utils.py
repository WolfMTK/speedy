import re
from typing import Iterable

from speedy.exceptions.http_exceptions import ImproperlyConfiguredException


def build_exclude_path_pattern(
        *,
        exclude: str | Iterable[str] | None = None,
) -> re.Pattern | None:
    """ Build single path pattern from list of patterns to opt-out from middleware processing. """
    if exclude is None:
        return None

    pattern_str = exclude if isinstance(exclude, str) else "|".join(exclude)
    try:
        return re.compile(pattern_str)
    except re.error as e:
        raise ImproperlyConfiguredException(
            "Unable to compile exclude patterns for middleware. Please make "
            "sure you passed a valid regular expression."
        ) from e
