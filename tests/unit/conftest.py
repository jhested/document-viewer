"""Unit-test fixtures, including aiobotocore+moto compatibility patch."""
from __future__ import annotations

import inspect
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# aiobotocore + moto compatibility
# ---------------------------------------------------------------------------
# aiobotocore wraps botocore to make S3 calls async, but moto patches the
# underlying HTTP transport with *synchronous* objects:
#
#   • AWSResponse.content  →  plain bytes, not a coroutine
#   • The streaming body's raw stream  →  MockRawResponse (BytesIO), not an
#     aiohttp.ClientResponse, so `self.__wrapped__.content.read()` raises.
#
# We fix both with minimal, targeted patches that are applied for every unit
# test via the autouse fixture below.


async def _safe_convert_to_response_dict(
    http_response: object, operation_model: object
) -> dict:  # type: ignore[type-arg]
    """Drop-in for ``aiobotocore.endpoint.convert_to_response_dict``.

    Handles both real aiohttp responses (coroutine .content) and moto's sync
    AWSResponse (plain bytes .content).
    """
    response_dict = {
        "headers": http_response.headers,  # type: ignore[attr-defined]
        "status_code": http_response.status_code,  # type: ignore[attr-defined]
        "context": {"operation_name": operation_model.name},  # type: ignore[attr-defined]
    }

    async def _content() -> bytes:
        val = http_response.content  # type: ignore[attr-defined]
        if inspect.isawaitable(val):
            return await val  # type: ignore[no-any-return]
        return val  # type: ignore[return-value]

    if response_dict["status_code"] >= 300:
        response_dict["body"] = await _content()
    elif operation_model.has_event_stream_output:  # type: ignore[attr-defined]
        response_dict["body"] = http_response.raw  # type: ignore[attr-defined]
    elif operation_model.has_streaming_output:  # type: ignore[attr-defined]
        raw = http_response.raw  # type: ignore[attr-defined]
        try:
            import httpx  # type: ignore[import-untyped]
            from aiobotocore.endpoint import HttpxStreamingBody  # type: ignore[import-untyped]

            if isinstance(raw, httpx.Response):
                response_dict["body"] = HttpxStreamingBody(raw)
                return response_dict
        except ImportError:
            pass
        length = response_dict["headers"].get("content-length")
        from botocore.response import StreamingBody  # type: ignore[import-untyped]

        response_dict["body"] = StreamingBody(raw, length)
    else:
        response_dict["body"] = await _content()

    return response_dict


async def _streaming_body_read(self: object, amt: int | None = None) -> bytes:  # type: ignore[misc]
    """Replacement for ``aiobotocore.response.StreamingBody.read``.

    When moto is active ``self.__wrapped__`` is a ``MockRawResponse``
    (a subclass of ``BytesIO``).  It has no ``.content`` attribute, so we
    call ``.read()`` directly.  For real aiohttp responses we fall through to
    the original awaitable path.
    """
    import io

    raw = self.__wrapped__  # type: ignore[attr-defined]
    # Sync path: moto provides BytesIO-like objects
    if isinstance(raw, (io.RawIOBase, io.BufferedIOBase)):
        chunk = raw.read(amt) if amt is not None else raw.read()
        self._self_amount_read += len(chunk)  # type: ignore[attr-defined]
        if amt is None or (not chunk and amt and amt > 0):
            self._verify_content_length()  # type: ignore[attr-defined]
        return chunk  # type: ignore[return-value]

    # Async path: real aiohttp.ClientResponse

    import aiohttp  # type: ignore[import-untyped]

    try:
        chunk = await raw.content.read(amt if amt is not None else -1)
    except TimeoutError as e:
        from aiobotocore.response import AioReadTimeoutError  # type: ignore[import-untyped]

        raise AioReadTimeoutError(endpoint_url=raw.url, error=e) from e
    except aiohttp.client_exceptions.ClientConnectionError as e:
        from botocore.exceptions import ResponseStreamingError  # type: ignore[import-untyped]

        raise ResponseStreamingError(error=e) from e

    self._self_amount_read += len(chunk)  # type: ignore[attr-defined]
    if amt is None or (not chunk and amt and amt > 0):
        self._verify_content_length()  # type: ignore[attr-defined]
    return chunk  # type: ignore[return-value]


@pytest.fixture(autouse=True)
def _patch_aiobotocore_for_moto() -> None:  # type: ignore[misc]
    """Apply the aiobotocore+moto compatibility patches for every unit test."""
    import aiobotocore.response  # type: ignore[import-untyped]

    with (
        mock.patch(
            "aiobotocore.endpoint.convert_to_response_dict",
            _safe_convert_to_response_dict,
        ),
        mock.patch.object(
            aiobotocore.response.StreamingBody,
            "read",
            _streaming_body_read,
        ),
    ):
        yield  # type: ignore[misc]
