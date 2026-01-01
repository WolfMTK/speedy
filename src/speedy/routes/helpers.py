import datetime
import decimal
import pathlib
import uuid

from speedy.exceptions.http_exceptions import ImproperlyConfiguredException

param_type_map = {
    "str": str,
    "int": int,
    "float": float,
    "uuid": uuid.UUID,
    "decimal": decimal.Decimal,
    "date": datetime.date,
    "datetime": datetime.datetime,
    "time": datetime.time,
    "timedelta": datetime.timedelta,
    "path": pathlib.Path,
}


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


def _validate_path_parameter(param: str, path: str) -> None:
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
    if ptype not in param_type_map:
        raise ImproperlyConfiguredException(
            "Path parameters should be declared with an allowed type, "
            f"i.e. one of {', '.join(param_type_map.keys())} in path: '{path}'",
        )
