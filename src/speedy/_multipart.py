import re
from collections import defaultdict
from dataclasses import dataclass, field
from email.utils import decode_rfc2231
from typing import Any
from urllib.parse import unquote

from speedy.datastructures import UploadFile
from speedy.exceptions import ValidationException

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


class _Parser:
    def parse_body(self) -> list[bytes]:
        """ Split the body using the boundary and validate the number of form parts is within the allowed limit. """
        form_parts = self.body.split(self.boundary, self.multipart_limit + 3)[1:-1]

        if len(form_parts) > self.multipart_limit:
            raise ValidationException(
                f'number of form parts exceeds allowed limit of {self.multipart_limit}'
            )
        return form_parts


@dataclass
class _FormPart:
    file_name: None | str = field(default=None)
    charset: str = 'utf-8'
    field_name: None | str = field(default=None)
    headers: list[tuple[str, str]] = field(default_factory=list)


class MultiPartFormParser(_Parser):
    """ The parser multipart form data. """

    def __init__(
            self,
            body: bytes,
            boundary: bytes,
            multipart_limit: int = 1000
    ) -> None:
        self.body = body
        self.boundary = boundary
        self.multipart_limit = multipart_limit

    def parser(self) -> dict[str, Any,]:
        """ Parse multipart form data. """
        fields = defaultdict(list)

        for value in self.parse_body():
            form_part = _FormPart()
            line_index = 2
            line_end_index = 0

            while line_end_index != -1:
                line_end_index = value.find(b"\r\n", line_index)
                form_line = value[line_index:line_end_index].decode("utf-8")
                if not form_line:
                    break
                line_index = line_end_index + 2
                colon_index = form_line.index(":")
                current_idx = colon_index + 2
                form_header_field = form_line[:colon_index].lower()
                form_header_value, form_parameters = parse_content_header(form_line[current_idx:])
                if form_header_field == "content-disposition":
                    self._encode_content_disposition(form_part, form_parameters)
                elif form_header_field == "content-type":
                    form_part.charset = form_parameters.get("charset", "utf-8")
                form_part.headers.append((form_header_field, form_header_value))
            if form_part.field_name:
                self._set_fields(form_part, fields, value, line_index)
        return {key: value if len(value) > 1 else value[0] for key, value in fields.items()}

    def _set_fields(
            self,
            form_part: _FormPart,
            fields: defaultdict[str, list[Any]],
            form: bytes,
            line_index: int
    ) -> None:
        post_data = form[line_index:].rstrip(b'\r\n--').lstrip(b'\r\n')
        if form_part.file_name:
            form_file = UploadFile(filename=form_part.file_name,
                                   file_data=post_data,
                                   headers=dict(form_part.headers))
            fields[form_part.field_name].append(form_file)
        elif post_data:
            fields[form_part.field_name].append(post_data.decode(form_part.charset))
        else:
            fields[form_part.field_name].append(None)

    def _encode_content_disposition(
            self,
            form_part: _FormPart,
            form_parameters: dict[str, str]
    ) -> None:
        form_part.field_name = form_parameters.get("name")
        form_part.file_name = form_parameters.get("filename")
        if form_part.file_name is None and (filename_with_asterisk := form_parameters.get("filename*")):
            encoding, _, value = decode_rfc2231(filename_with_asterisk)
            form_part.file_name = unquote(value, encoding=encoding or form_part.charset)
