"""Tests for `swarm_core.streams.StreamDescriptor` + URL allowlist."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from swarm_core.streams import (
    ALLOWED_STREAM_SCHEMES,
    SIM_FEED_PREFIX,
    InvalidStreamURL,
    StreamDescriptor,
    validate_sim_feed_path,
    validate_stream_url,
)

# Pydantic wraps `InvalidStreamURL` (a `ValueError`) raised inside a model
# validator with `ValidationError`. Tests that exercise the model constructor
# accept either, while tests calling `validate_stream_url` directly assert
# the precise `InvalidStreamURL`.
_BAD_URL_EXC: tuple[type[Exception], ...] = (InvalidStreamURL, ValidationError)


class TestValidateStreamURL:
    """Phase 5 roadmap §Security additions — only `rtsps://` / `https://`."""

    def test_accepts_rtsps(self) -> None:
        url = "rtsps://camera.example.com:8554/unit-001"
        assert validate_stream_url(url) == url

    def test_accepts_https(self) -> None:
        url = "https://stream.example.com/hls/unit-001.m3u8"
        assert validate_stream_url(url) == url

    def test_rejects_plaintext_rtsp(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_stream_url("rtsp://camera.example.com:8554/x")

    def test_rejects_plaintext_http(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_stream_url("http://stream.example.com/x")

    def test_rejects_rtmp(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_stream_url("rtmp://stream.example.com/live")

    def test_rejects_file_scheme(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_stream_url("file:///etc/passwd")

    def test_rejects_javascript_scheme(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_stream_url("javascript:alert(1)")

    def test_rejects_data_scheme(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_stream_url("data:video/mp4;base64,AAAA")

    def test_rejects_empty(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_stream_url("")

    def test_rejects_missing_host(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_stream_url("https:///path-only")

    def test_rejects_crlf_injection(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_stream_url("https://stream.example.com/\r\nX-Inject: 1")

    def test_rejects_nul_byte(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_stream_url("https://stream.example.com/\x00x")

    def test_allowlist_is_closed(self) -> None:
        # Defense against a future contributor relaxing the allowlist by
        # accident — pin the membership in a test.
        assert frozenset({"rtsps", "https"}) == ALLOWED_STREAM_SCHEMES


class TestStreamDescriptor:
    def test_offline_factory(self) -> None:
        s = StreamDescriptor.offline("unit-001")
        assert not s.available
        assert s.url is None
        assert s.protocol is None
        assert s.agent_id == "unit-001"

    def test_available_with_https_url(self) -> None:
        s = StreamDescriptor(
            agent_id="unit-001",
            available=True,
            url="https://stream.example.com/hls/u1.m3u8",
            protocol="https",
            codec="h264",
        )
        assert s.url is not None
        assert s.protocol == "https"

    def test_available_with_rtsps_url(self) -> None:
        s = StreamDescriptor(
            agent_id="unit-001",
            available=True,
            url="rtsps://stream.example.com/u1",
            protocol="rtsps",
        )
        assert s.url is not None

    def test_available_true_requires_url(self) -> None:
        with pytest.raises(_BAD_URL_EXC):
            StreamDescriptor(agent_id="unit-001", available=True)

    def test_available_false_forbids_url(self) -> None:
        with pytest.raises(_BAD_URL_EXC):
            StreamDescriptor(
                agent_id="unit-001",
                available=False,
                url="https://x.example.com/u1",
            )

    def test_available_false_forbids_protocol(self) -> None:
        with pytest.raises(_BAD_URL_EXC):
            StreamDescriptor(
                agent_id="unit-001",
                available=False,
                protocol="https",
            )

    def test_protocol_must_match_scheme(self) -> None:
        with pytest.raises(_BAD_URL_EXC):
            StreamDescriptor(
                agent_id="unit-001",
                available=True,
                url="https://stream.example.com/u1",
                protocol="rtsps",
            )

    def test_rejects_unknown_codec(self) -> None:
        with pytest.raises(_BAD_URL_EXC):
            StreamDescriptor(
                agent_id="unit-001",
                available=True,
                url="https://stream.example.com/u1",
                codec="vp99-experimental",
            )

    def test_strict_extra_fields_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StreamDescriptor(
                agent_id="unit-001",
                available=False,
                sneaky_extra="boo",  # type: ignore[call-arg]
            )

    def test_rejects_url_with_disallowed_scheme(self) -> None:
        with pytest.raises(_BAD_URL_EXC):
            StreamDescriptor(
                agent_id="unit-001",
                available=True,
                url="http://stream.example.com/u1",
            )

    def test_round_trip_json(self) -> None:
        s = StreamDescriptor(
            agent_id="unit-007",
            available=True,
            url="https://stream.example.com/hls/u7.m3u8",
            protocol="https",
            codec="h264",
        )
        roundtripped = StreamDescriptor.model_validate_json(s.model_dump_json())
        assert roundtripped == s

    def test_external_feed_is_not_simulated_by_default(self) -> None:
        s = StreamDescriptor(
            agent_id="unit-001",
            available=True,
            url="https://stream.example.com/u1",
        )
        assert s.simulated is False


class TestValidateSimFeedPath:
    """CV-live video sub-step — a simulated feed is a same-origin bundled clip."""

    def test_accepts_sim_feed_path(self) -> None:
        path = "/sim-feed/unit-003-pov.mp4"
        assert validate_sim_feed_path(path) == path

    def test_rejects_empty(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_sim_feed_path("")

    def test_rejects_https_url(self) -> None:
        # An absolute URL (even allowlisted-scheme) is not a same-origin path.
        with pytest.raises(InvalidStreamURL):
            validate_sim_feed_path("https://evil.example.com/sim-feed/x.mp4")

    def test_rejects_protocol_relative(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_sim_feed_path("//evil.example.com/sim-feed/x.mp4")

    def test_rejects_path_outside_prefix(self) -> None:
        # A same-origin path that is not under /sim-feed/ — e.g. an attempt to
        # point the <video> at an arbitrary Console route.
        with pytest.raises(InvalidStreamURL):
            validate_sim_feed_path("/api/secret")

    def test_rejects_traversal(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_sim_feed_path("/sim-feed/../../etc/passwd")

    def test_rejects_backslash(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_sim_feed_path("/sim-feed/..\\x.mp4")

    def test_rejects_crlf(self) -> None:
        with pytest.raises(InvalidStreamURL):
            validate_sim_feed_path("/sim-feed/x.mp4\r\nX-Inject: 1")

    def test_prefix_is_sim_feed(self) -> None:
        assert SIM_FEED_PREFIX == "/sim-feed/"


class TestSimulatedDescriptor:
    """The third honest state: a synthetic SIM-labeled clip."""

    def test_simulated_factory(self) -> None:
        s = StreamDescriptor.simulated_feed("unit-003", "/sim-feed/u3.mp4", codec="h264")
        assert s.available is True
        assert s.simulated is True
        assert s.url == "/sim-feed/u3.mp4"
        assert s.protocol is None
        assert s.codec == "h264"

    def test_simulated_requires_available(self) -> None:
        with pytest.raises(_BAD_URL_EXC):
            StreamDescriptor(
                agent_id="unit-003",
                available=False,
                simulated=True,
                url="/sim-feed/u3.mp4",
            )

    def test_simulated_requires_url(self) -> None:
        with pytest.raises(_BAD_URL_EXC):
            StreamDescriptor(agent_id="unit-003", available=True, simulated=True)

    def test_simulated_rejects_external_url(self) -> None:
        with pytest.raises(_BAD_URL_EXC):
            StreamDescriptor(
                agent_id="unit-003",
                available=True,
                simulated=True,
                url="https://stream.example.com/u3",
            )

    def test_simulated_forbids_protocol(self) -> None:
        with pytest.raises(_BAD_URL_EXC):
            StreamDescriptor(
                agent_id="unit-003",
                available=True,
                simulated=True,
                url="/sim-feed/u3.mp4",
                protocol="https",
            )

    def test_simulated_rejects_traversal_url(self) -> None:
        with pytest.raises(_BAD_URL_EXC):
            StreamDescriptor(
                agent_id="unit-003",
                available=True,
                simulated=True,
                url="/sim-feed/../secret.mp4",
            )

    def test_simulated_round_trip_json(self) -> None:
        s = StreamDescriptor.simulated_feed("unit-003", "/sim-feed/u3.mp4", codec="h264")
        roundtripped = StreamDescriptor.model_validate_json(s.model_dump_json())
        assert roundtripped == s
        assert roundtripped.simulated is True
