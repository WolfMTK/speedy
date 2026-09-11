import hashlib
import json
from typing import Any

from speedy._speedy import (
    dump_json,
    compute_etag,
    multipart_closing_boundary,
    multipart_range_header,
    multipart_content_length,
    MalformedRangeHeader,
    parse_range_header,
    RangeNotSatisfiable,
)

import pytest


def _py_dumps(content: Any) -> bytes:
    return json.dumps(content, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":")).encode()


def _py_etag(mtime: float, size: int) -> str:
    return f'"{hashlib.md5(f"{mtime}-{size}".encode(), usedforsecurity=False).hexdigest()}"'


class TestDumpJson:
    @pytest.mark.parametrize(
        "content",
        [
            {"a": 1, "b": [1, 2.5, None, True, False, "héllo"]},
            "héllo",
            1,
            1.0,
            -0.0,
            1e100,
            [],
            {},
            (1, 2, 3),
            [{"x": 1}, {"y": 2}],
            'with"quote',
            "with\\backslash",
            "with\nnewline",
            "\x01\x1f control",
            {"nested": {"deep": [1, [2, 3], {"x": None}]}},
        ],
    )
    def test_roundtrip(self, content: Any) -> None:
        assert dump_json(content) == _py_dumps(content)

    def test_key_order(self) -> None:
        assert dump_json({"z": 1, "a": 2, "m": 3}) == b'{"z":1,"a":2,"m":3}'

    def test_big_ints(self) -> None:
        n = int("9" * 33)
        assert dump_json(n) == str(n).encode()
        assert dump_json(-n) == str(-n).encode()

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ({True: "a", False: "b"}, b'{"true":"a","false":"b"}'),
            ({1: "a", None: "b"}, b'{"1":"a","null":"b"}'),
            ({2.5: "a"}, b'{"2.5":"a"}'),
            ({2: 3.0, 4.0: 5, False: 1, 6: True}, b'{"2":3.0,"4.0":5,"false":1,"6":true}'),
        ],
    )
    def test_keys(self, content: dict[Any, Any], expected: bytes) -> None:
        assert dump_json(content) == expected

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite(self, value: float) -> None:
        with pytest.raises(ValueError, match="not JSON compliant"):
            dump_json(value)

    @pytest.mark.parametrize(
        ("key", "type_name"),
        [((1, 2), "tuple"), (b"invalid_key", "bytes")],
    )
    def test_bad_key(self, key: Any, type_name: str) -> None:
        with pytest.raises(TypeError, match=f"keys must be str, int, float, bool or None, not {type_name}"):
            dump_json({key: "x"})

    @pytest.mark.parametrize("content", [object(), {"a": [1, object()]}])
    def test_not_serializable(self, content: Any) -> None:
        with pytest.raises(TypeError, match="not JSON serializable"):
            dump_json(content)

    def test_returns_bytes(self) -> None:
        assert isinstance(dump_json({"a": 1}), bytes)

    def test_evil_dict(self) -> None:
        class EvilDict(dict):
            def keys(self) -> list[str]:
                return ["fake_key"]

        d = EvilDict()
        d["real_key"] = "real_value"
        assert dump_json(d) == b'{"real_key":"real_value"}'

    def test_str_subclass(self) -> None:
        class S(str):
            def __str__(self) -> str:
                return "WRONG"

        assert dump_json(S("ascii")) == b'"ascii"'
        assert dump_json([S("ascii")]) == b'["ascii"]'
        assert dump_json({"key": S("ascii")}) == b'{"key":"ascii"}'
        assert dump_json(S("escape\n")) == b'"escape\\n"'
        assert dump_json(S("nonascii:é")) == '"nonascii:é"'.encode()

    def test_large_list(self) -> None:
        n = 50_000
        assert dump_json([1] * n) == b"[" + b",".join([b"1"] * n) + b"]"


class TestComputeEtag:
    @pytest.mark.parametrize(
        ("mtime", "size"),
        [
            (12345.678, 0),
            (12345.678, 1),
            (12345.678, 1024),
            (12345.678, 99999999999),
            (0.0, 0),
            (-0.0, 0),
            (1.0, 1024),
            (100.0, 1024),
            (1e10, 1024),
            (1e-10, 1024),
            (1700000000.123456, 1024),
            (1699999999.999999, 1024),
            (1234567890.0, 1024),
        ],
    )
    def test_matches_hashlib_md5(self, mtime: float, size: int) -> None:
        assert compute_etag(mtime, size) == _py_etag(mtime, size)

    def test_is_quoted(self) -> None:
        etag = compute_etag(12345.678, 1024)
        assert etag.startswith('"')
        assert etag.endswith('"')

    def test_is_32_char_lowercase_hex_digest(self) -> None:
        etag = compute_etag(12345.678, 1024)
        digest = etag.strip('"')
        assert len(digest) == 32
        assert digest == digest.lower()
        assert all(c in "0123456789abcdef" for c in digest)

    def test_deterministic_for_same_inputs(self) -> None:
        assert compute_etag(12345.678, 1024) == compute_etag(12345.678, 1024)

    @pytest.mark.parametrize(
        ("mtime_a", "size_a", "mtime_b", "size_b"),
        [
            (12345.678, 1024, 12345.679, 1024),
            (12345.678, 1024, 12345.678, 1025),
        ],
    )
    def test_different_inputs_give_different_etags(
            self,
            mtime_a: float,
            size_a: int,
            mtime_b: float,
            size_b: int
    ) -> None:
        assert compute_etag(mtime_a, size_a) != compute_etag(mtime_b, size_b)


class TestMultipartClosingBoundary:
    def test_returns_str(self) -> None:
        assert isinstance(compute_etag(12345.678, 1024), str)

    def test_basic_format(self) -> None:
        assert multipart_closing_boundary("BOUND") == b"--BOUND--"

    def test_empty_boundary(self) -> None:
        assert multipart_closing_boundary("") == b"----"

    def test_multipart_returns_bytes(self) -> None:
        assert isinstance(multipart_closing_boundary("x"), bytes)

    def test_multipart_matches_length(self) -> None:
        boundary = "a1b2c3"
        assert len(multipart_closing_boundary(boundary)) == 4 + len(boundary)

class TestMultipartRangeHeader:
    def test_basic_format(self) -> None:
        header = multipart_range_header("BOUND", "text/plain", 0, 100, 1000)
        assert header == b"--BOUND\r\nContent-Type: text/plain\r\nContent-Range: bytes 0-99/1000\r\n\r\n"

    def test_end_is_exclusive_content_range_is_inclusive(self) -> None:
        header = multipart_range_header("b", "text/plain", 10, 20, 1000)
        assert b"Content-Range: bytes 10-19/1000" in header

    def test_single_byte_range(self) -> None:
        header = multipart_range_header("b", "text/plain", 5, 6, 1000)
        assert b"Content-Range: bytes 5-5/1000" in header

    def test_ends_with_blank_line_before_content(self) -> None:
        header = multipart_range_header("b", "text/plain", 0, 1, 10)
        assert header.endswith(b"\r\n\r\n")

    def test_returns_bytes(self) -> None:
        assert isinstance(multipart_range_header("b", "text/plain", 0, 1, 10), bytes)


class TestMultipartContentLength:
    def _real_total_length(
            self,
            ranges: list[tuple[int, int]],
            boundary: str,
            max_size: int,
            content_type: str
    ) -> int:
        total = 0
        for start, end in ranges:
            header = multipart_range_header(boundary, content_type, start, end, max_size)
            total += len(header) + (end - start) + len(b"\r\n")
        total += len(multipart_closing_boundary(boundary))
        return total

    @pytest.mark.parametrize(
        ("ranges", "boundary", "max_size", "content_type"),
        [
            ([(0, 100), (200, 300)], "BOUND", 1000, "text/plain"),
            ([(0, 1)], "x", 10, "a"),
            ([(0, 100), (200, 300), (500, 999)], "a1b2c3d4e5f6g7", 1000, "application/octet-stream"),
            ([(0, 1000000)], "b", 1000000, "text/plain"),
        ],
    )
    def test_matches_actual_assembled_body_length(
            self, ranges: list[tuple[int, int]], boundary: str, max_size: int, content_type: str
    ) -> None:
        assert multipart_content_length(ranges, boundary, max_size, content_type) == self._real_total_length(
            ranges, boundary, max_size, content_type
        )

    def test_returns_int(self) -> None:
        assert isinstance(multipart_content_length([(0, 1)], "b", 10, "text/plain"), int)

    def test_longer_boundary_increases_total(self) -> None:
        short = multipart_content_length([(0, 10)], "b", 100, "text/plain")
        long = multipart_content_length([(0, 10)], "much-longer-boundary", 100, "text/plain")
        assert long > short

class TestParseRangeHeader:
    @pytest.mark.parametrize(
        ("header", "file_size", "expected"),
        [
            ("bytes=0-499", 1000, [(0, 500)]),
            ("bytes=500-", 1000, [(500, 1000)]),
            ("bytes=-500", 1000, [(500, 1000)]),
            ("bytes=0-0", 1000, [(0, 1)]),
            ("bytes=0-0,100-200", 1000, [(0, 1), (100, 201)]),
            ("bytes=0-99999999", 1000, [(0, 1000)]),
            ("bytes=0-499, 500-999", 1000, [(0, 1000)]),
        ],
    )
    def test_valid_single_and_multi_ranges(
            self, header: str, file_size: int, expected: list[tuple[int, int]]
    ) -> None:
        assert parse_range_header(header, file_size, 100) == expected

    @pytest.mark.parametrize(
        ("header", "expected"),
        [
            ("bytes=0-100,50-150", [(0, 151)]),
            ("bytes=0-100,200-300,250-400", [(0, 101), (200, 401)]),
        ],
    )
    def test_overlapping_ranges_are_merged(self, header: str, expected: list[tuple[int, int]]) -> None:
        assert parse_range_header(header, 1000, 100) == expected

    @pytest.mark.parametrize(
        "header",
        [
            "items=0-499",
            "bytes",
            "bytes=",
            "bytes=abc-def",
            "bytes=100-50",
        ],
    )
    def test_malformed_header_raises(self, header: str) -> None:
        with pytest.raises(MalformedRangeHeader):
            parse_range_header(header, 1000, 100)

    def test_start_beyond_file_size_raises_not_satisfiable(self) -> None:
        with pytest.raises(RangeNotSatisfiable) as exc_info:
            parse_range_header("bytes=1000-2000", 1000, 100)
        assert exc_info.value.max_size == 1000

    def test_too_many_ranges_returns_empty_list(self) -> None:
        header = "bytes=" + ",".join(f"{i}-{i}" for i in range(150))
        assert parse_range_header(header, 1000, 100) == []

    def test_malformed_range_error_has_content_attribute(self) -> None:
        with pytest.raises(MalformedRangeHeader) as exc_info:
            parse_range_header("bytes=abc-def", 1000, 100)
        assert isinstance(exc_info.value.content, str)

    def test_returns_list_of_tuples(self) -> None:
        result = parse_range_header("bytes=0-99", 1000, 100)
        assert isinstance(result, list)
        assert result == [(0, 100)]
