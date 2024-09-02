import re

_firefox_quote_escape = re.compile(r'\\"(?!; |\s*$)')
_token = r"([\w!#$%&'*+\-.^_`|~]+)"
_quoted = r'"([^"]*)"'
_param = re.compile(rf";\s*{_token}=(?:{_token}|{_quoted})", re.ASCII)


def parse_content_header(value: str) -> tuple[str, dict[str, str]]:
    """ Parse content-type and content-disposition header values. """
    value = _firefox_quote_escape.sub('%22', value)
    position = value.find(';')
    options = {}
    if position != -1:
        for val in _param.finditer(value[position:]):
            options[val.group(1).lower()] = val.group(2) or val.group(3).replace("%22", '"')
        value = value[:position]
    return value.strip().lower(), options
