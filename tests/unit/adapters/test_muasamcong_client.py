
import httpx
import pytest

from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.client import (
    MuasamcongClient,
    RetryPolicy,
    SourceResponseError,
    raise_for_status_with_detail,
)


def test_raise_for_status_with_detail_success() -> None:
    request = httpx.Request("POST", "https://api.test/search")
    response = httpx.Response(200, request=request, text='{"success": true}')
    # Should not raise
    raise_for_status_with_detail(response)


def test_raise_for_status_with_detail_includes_error_body() -> None:
    request = httpx.Request("POST", "https://api.test/search")
    error_payload = '{"code": "INVALID_PARAM", "message": "Date range exceeded"}'
    response = httpx.Response(400, request=request, text=error_payload)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        raise_for_status_with_detail(response)

    error_msg = str(exc_info.value)
    assert "Muasamcong HTTP 400 Error" in error_msg
    assert "Date range exceeded" in error_msg
    assert "https://api.test/search" in error_msg
    assert exc_info.value.response.status_code == 400


def test_raise_for_status_with_detail_truncates_long_body() -> None:
    request = httpx.Request("GET", "https://api.test/detail")
    long_html = "<html><body>" + ("Very long server error message! " * 50) + "</body></html>"
    response = httpx.Response(500, request=request, text=long_html)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        raise_for_status_with_detail(response)

    error_msg = str(exc_info.value)
    assert "Muasamcong HTTP 500 Error" in error_msg
    assert "[truncated]" in error_msg
    assert len(error_msg) < 800


def test_client_post_includes_detailed_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            400,
            request=request,
            text='{"error": "Invalid token"}',
        )
    )

    client = MuasamcongClient(
        base_url="https://api.test",
        token="test-token",
        timeout=httpx.Timeout(5.0),
        retry_policy=RetryPolicy(max_attempts=1),
        transport=transport,
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client.post("services/search", body={})

    assert "Invalid token" in str(exc_info.value)
    assert "HTTP 400 Error" in str(exc_info.value)


def test_client_post_invalid_json_raises_source_response_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            request=request,
            text="Not valid JSON",
        )
    )

    client = MuasamcongClient(
        base_url="https://api.test",
        token="test-token",
        timeout=httpx.Timeout(5.0),
        retry_policy=RetryPolicy(max_attempts=1),
        transport=transport,
    )

    with pytest.raises(SourceResponseError, match="API returned invalid JSON"):
        client.post("services/search", body={})

