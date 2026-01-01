import datetime
import decimal
import pathlib
import re
import uuid

from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.types import PathParameterDefinition
from speedy.utils import normalize_path, join_paths


def _parse_datetime(value: str) -> datetime.datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.datetime.fromisoformat(value)


def _parse_date(value: str) -> datetime.date:
    return datetime.date.fromisoformat(value)


def _parse_time(value: str) -> datetime.time:
    return datetime.time.fromisoformat(value)


def _parse_timedelta(value: str) -> datetime.timedelta:
    try:
        return datetime.timedelta(seconds=float(value))
    except ValueError:
        pass

    try:
        val = datetime.time.fromisoformat(value)
        return datetime.timedelta(
            hours=val.hour,
            minutes=val.minute,
            seconds=val.second,
            microseconds=val.microsecond,
        )
    except ValueError:
        pass

    raise ValueError(f"Invalid timedelta format: `{value}`")


TYPE_CONFIGS = {
    "str": (str, None),
    "int": (int, int),
    "float": (float, float),
    "uuid": (uuid.UUID, uuid.UUID),
    "decimal": (decimal.Decimal, decimal.Decimal),
    "date": (datetime.date, _parse_date),
    "datetime": (datetime.datetime, _parse_datetime),
    "time": (datetime.time, _parse_time),
    "timedelta": (datetime.timedelta, _parse_timedelta),
    "path": (pathlib.Path, None),
}


def _validate_path_parameter(param: str, path: str) -> tuple[str, str]:
    name, sep, ptype = param.partition(":")
    name = name.strip()
    ptype = ptype.strip()

    if not sep:
        raise ImproperlyConfiguredException(
            "Path parameters should be declared with a type "
            f"using the following pattern: '{{parameter_name:type}}', "
            f"e.g. '/my-path/{{my_param:int}}' in path: '{path}'",
        )
    if not name:
        raise ImproperlyConfiguredException(
            "Path parameter names "
            "should be of length greater than zero",
        )
    if ptype not in TYPE_CONFIGS:
        raise ImproperlyConfiguredException(
            "Path parameters should be declared with an allowed type, "
            f"i.e. one of {', '.join(TYPE_CONFIGS.keys())} in path: '{path}'",
        )
    return name, ptype


param_match_regex = re.compile(r"{(.*?)}")


def _parse_path(
        path: str,
) -> tuple[str, str, list[str | PathParameterDefinition], dict[str, PathParameterDefinition]]:
    path = normalize_path(path)

    parsed_components: list[str | PathParameterDefinition] = []
    path_format_components: list[str] = []
    path_parameters: dict[str, PathParameterDefinition] = {}

    components = [component for component in path.split("/") if component]

    for component in components:
        if param_match := param_match_regex.fullmatch(component):
            param = param_match.group(1)
            param_name, type_str = _validate_path_parameter(param, path)
            type_class, parser = TYPE_CONFIGS[type_str]
            if param_name in path_parameters:
                raise ImproperlyConfiguredException(
                    f"Duplicate parameter `{param_name}` detected in `{path}`.",
                )
            param_definition = PathParameterDefinition(
                name=param_name,
                type=type_class,
                full=param,
                parser=parser,
            )
            parsed_components.append(param_definition)
            path_parameters[param_name] = param_definition
            path_format_components.append("{" + param_name + "}")
        else:
            parsed_components.append(component)
            path_format_components.append(component)

    path_format = join_paths(path_format_components)

    return path, path_format, parsed_components, path_parameters
