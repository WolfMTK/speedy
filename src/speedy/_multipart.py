import re
from collections import defaultdict
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


class MultiPartFormParser(_Parser):
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
        fields = defaultdict(list)

        for form_part in self.parse_body():
            file_name = None
            content_charset = "utf-8"
            field_name = None
            line_index = 2
            line_end_index = 0
            headers: list[tuple[str, str]] = []

            while line_end_index != -1:
                line_end_index = form_part.find(b"\r\n", line_index)
                form_line = form_part[line_index:line_end_index].decode("utf-8")

                if not form_line:
                    break

                line_index = line_end_index + 2
                colon_index = form_line.index(":")
                current_idx = colon_index + 2
                form_header_field = form_line[:colon_index].lower()
                form_header_value, form_parameters = parse_content_header(form_line[current_idx:])
                if form_header_field == "content-disposition":
                    field_name = form_parameters.get("name")
                    file_name = form_parameters.get("filename")

                    if file_name is None and (filename_with_asterisk := form_parameters.get("filename*")):
                        encoding, _, value = decode_rfc2231(filename_with_asterisk)
                        file_name = unquote(value, encoding=encoding or content_charset)

                elif form_header_field == "content-type":
                    content_charset = form_parameters.get("charset", "utf-8")
                headers.append((form_header_field, form_header_value))

            if field_name:
                post_data = form_part[line_index:].rstrip(b'\r\n--').lstrip(b'\r\n')

                if file_name:
                    form_file = UploadFile(filename=file_name,
                                           file_data=post_data,
                                           headers=dict(headers))
                    fields[field_name].append(form_file)
                elif post_data:
                    fields[field_name].append(post_data.decode(content_charset))
                else:
                    fields[field_name].append(None)
        return {k: v if len(v) > 1 else v[0] for k, v in fields.items()}
