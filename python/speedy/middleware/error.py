import inspect
import sys
import traceback
from typing import cast

from speedy._speedy import html_escape
from speedy.concurrency import is_async_callable, run_in_threadpool
from speedy.requests import Request, empty_receive, empty_send
from speedy.responses import HTMLResponse, PlainTextResponse, Response
from speedy.status import HTTP_500_INTERNAL_SERVER_ERROR
from speedy.types import ASGIApplication, ExceptionHandler, HTTPScope, Message, Receive, Scope, Send

__all__ = ["ServerErrorMiddleware"]

STYLES = """
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background-color: #f4f6fb;
    margin: 0;
    padding: 24px;
}
p {
    color: #1f2430;
}
.traceback-container {
    border: 1px solid #4c51bf;
    border-radius: 10px;
    overflow: hidden;
    background-color: #ffffff;
}
.traceback-title {
    background-color: #4c51bf;
    color: #f5f3ff;
    padding: 14px 16px;
    font-size: 20px;
    margin-top: 0px;
}
.frame-line {
    padding-left: 10px;
    font-family: ui-monospace, "SF Mono", "Cascadia Code", Consolas, monospace;
}
.frame-filename {
    font-family: ui-monospace, "SF Mono", "Cascadia Code", Consolas, monospace;
}
.center-line {
    background-color: #4c51bf;
    color: #f5f3ff;
    padding: 5px 0px 5px 5px;
}
.lineno {
    margin-right: 5px;
    color: #6b7280;
}
.frame-title {
    font-weight: unset;
    padding: 10px 12px;
    background-color: #eef0fb;
    margin: 10px;
    color: #1f2430;
    font-size: 16px;
    border: 1px solid #cdd3ee;
    border-radius: 6px;
}
.collapse-btn {
    float: right;
    padding: 0px 6px 1px 6px;
    border-radius: 4px;
    border: solid 1px #9aa3c7;
    cursor: pointer;
}
.collapsed {
  display: none;
}
.source-code {
  font-family: ui-monospace, "SF Mono", "Cascadia Code", Consolas, monospace;
  font-size: 13px;
  padding-bottom: 10px;
}
"""

JS = """
<script type="text/javascript">
    function collapse(element){
        const frameId = element.getAttribute("data-frame-id");
        const frame = document.getElementById(frameId);

        if (frame.classList.contains("collapsed")){
            element.innerHTML = "&#8210;";
            frame.classList.remove("collapsed");
        } else {
            element.innerHTML = "+";
            frame.classList.add("collapsed");
        }
    }
</script>
"""

TEMPLATE = """
<html>
    <head>
        <style type='text/css'>
            {styles}
        </style>
        <title>Speedy Debugger</title>
    </head>
    <body>
        <h1>500 Server Error</h1>
        <h2>{error}</h2>
        <div class="traceback-container">
            <p class="traceback-title">Traceback</p>
            <div>{exc_html}</div>
        </div>
        {js}
    </body>
</html>
"""

FRAME_TEMPLATE = """
<div>
    <p class="frame-title">File <span class="frame-filename">{frame_filename}</span>,
    line <i>{frame_lineno}</i>,
    in <b>{frame_name}</b>
    <span class="collapse-btn" data-frame-id="{frame_filename}-{frame_lineno}" onclick="collapse(this)">{collapse_button}</span>
    </p>
    <div id="{frame_filename}-{frame_lineno}" class="source-code {collapsed}">{code_context}</div>
</div>
"""  # noqa: E501

LINE = """
<p><span class="frame-line">
<span class="lineno">{lineno}.</span> {line}</span></p>
"""

CENTER_LINE = """
<p class="center-line"><span class="frame-line center-line">
<span class="lineno">{lineno}.</span> {line}</span></p>
"""


class ServerErrorMiddleware:
    """Handles returning 500 responses when a server error occurs."""

    def __init__(
        self,
        app: ASGIApplication,
        handler: ExceptionHandler | None = None,
        debug: bool = False,
    ) -> None:
        self.app = app
        self.handler = handler
        self.debug = debug

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def _send(message: Message) -> None:
            nonlocal response_started

            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception as exc:
            request = Request(cast(HTTPScope, scope), empty_receive, empty_send)
            if self.debug:
                response = await run_in_threadpool(self.debug_response, request, exc)
            elif self.handler is None:
                response = self.error_response(request, exc)
            elif is_async_callable(self.handler):
                response = await self.handler(request, exc)
            else:
                response = await run_in_threadpool(self.handler, request, exc)

            if not response_started:
                await response(scope, receive, send)

            raise exc

    def format_line(self, index: int, line: str, frame_lineno: int, frame_index: int) -> str:
        values = {
            "line": html_escape(line).replace(" ", "&nbsp"),
            "lineno": (frame_lineno - frame_index) + index,
        }

        if index != frame_index:
            return LINE.format(**values)
        return CENTER_LINE.format(**values)

    def generate_frame_html(self, frame: inspect.FrameInfo, is_collapsed: bool) -> str:
        frame_index = frame.index if frame.index is not None else 0
        code_context = "".join(
            self.format_line(index, line, frame.lineno, frame_index)
            for index, line in enumerate(frame.code_context or [])
        )

        values = {
            "frame_filename": html_escape(frame.filename),
            "frame_lineno": frame.lineno,
            "frame_name": html_escape(frame.function),
            "code_context": code_context,
            "collapsed": "collapsed" if is_collapsed else "",
            "collapse_button": "+" if is_collapsed else "&#8210;",
        }
        return FRAME_TEMPLATE.format(**values)

    def generate_html(self, exc: Exception, limit: int = 7) -> str:
        traceback_obj = traceback.TracebackException.from_exception(exc, capture_locals=True)

        exc_html_parts: list[str] = []
        is_collapsed = False
        exc_traceback = exc.__traceback__
        if exc_traceback is not None:
            frames = inspect.getinnerframes(exc_traceback, limit)
            for frame in reversed(frames):
                exc_html_parts.append(self.generate_frame_html(frame, is_collapsed))
                is_collapsed = True
        exc_html = "".join(exc_html_parts)

        if sys.version_info >= (3, 13):
            exc_type_str = traceback_obj.exc_type_str
        else:
            exc_type_str = traceback_obj.exc_type.__name__

        error = f"{html_escape(exc_type_str)}: {html_escape(str(traceback_obj))}"

        return TEMPLATE.format(styles=STYLES, js=JS, error=error, exc_html=exc_html)

    def generate_plain_text(self, exc: Exception) -> str:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    def debug_response(self, request: Request, exc: Exception) -> Response:
        accept = request.headers.get("accept", "")

        if "text/html" in accept:
            content = self.generate_html(exc)
            return HTMLResponse(content, status_code=HTTP_500_INTERNAL_SERVER_ERROR)
        content = self.generate_plain_text(exc)
        return PlainTextResponse(content, status_code=HTTP_500_INTERNAL_SERVER_ERROR)

    def error_response(self, request: Request, exc: Exception) -> Response:
        return PlainTextResponse("Internal Server Error", status_code=HTTP_500_INTERNAL_SERVER_ERROR)
