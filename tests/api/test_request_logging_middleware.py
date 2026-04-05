from src.request_logging import request_logger


def test_post_request_is_logged(client, monkeypatch) -> None:
    captured_messages: list[str] = []

    monkeypatch.setattr(
        request_logger, "info", lambda msg: captured_messages.append(msg)
    )

    response = client.post("/submit")
    assert response.status_code == 200
    assert any("POST /submit" in message for message in captured_messages)


def test_static_path_is_not_logged(client, monkeypatch) -> None:
    captured_messages: list[str] = []

    monkeypatch.setattr(
        request_logger, "info", lambda msg: captured_messages.append(msg)
    )

    response = client.get("/static/app.js")
    assert response.status_code == 404
    assert captured_messages == []


def test_health_path_is_not_logged(client, monkeypatch) -> None:
    captured_messages: list[str] = []

    monkeypatch.setattr(
        request_logger, "info", lambda msg: captured_messages.append(msg)
    )

    response = client.get("/health")
    assert response.status_code == 200
    assert captured_messages == []


def test_exception_path_logs_exception(client, monkeypatch) -> None:
    captured_messages: list[str] = []

    monkeypatch.setattr(
        request_logger, "exception", lambda msg: captured_messages.append(msg)
    )

    response = client.get("/boom")
    assert response.status_code == 500
    assert any("GET /boom" in message for message in captured_messages)


def test_request_metrics_are_emitted(client, monkeypatch) -> None:
    captured_counts: list[tuple[str, int, dict[str, str]]] = []
    captured_distributions: list[tuple[str, float, dict[str, str]]] = []

    def fake_count(
        name: str,
        value: float,
        unit: str | None = None,
        attributes: dict[str, str] | None = None,
    ) -> None:
        del unit
        captured_counts.append((name, int(value), attributes or {}))

    def fake_distribution(
        name: str,
        value: float,
        unit: str | None = None,
        attributes: dict[str, str] | None = None,
    ) -> None:
        del unit
        captured_distributions.append((name, value, attributes or {}))

    monkeypatch.setattr("src.request_logging.metrics.count", fake_count)
    monkeypatch.setattr("src.request_logging.metrics.distribution", fake_distribution)

    response = client.post("/submit")
    assert response.status_code == 200

    assert any(
        name == "http.server.requests"
        and value == 1
        and attrs["method"] == "POST"
        and attrs["status_code"] == "200"
        and attrs["path"] == "/submit"
        for name, value, attrs in captured_counts
    )
    assert any(
        name == "http.server.duration_ms"
        and value >= 0.0
        and attrs["method"] == "POST"
        and attrs["status_code"] == "200"
        and attrs["path"] == "/submit"
        for name, value, attrs in captured_distributions
    )


def test_health_path_does_not_emit_request_metrics(client, monkeypatch) -> None:
    captured_counts: list[tuple[str, int, dict[str, str]]] = []
    captured_distributions: list[tuple[str, float, dict[str, str]]] = []

    def fake_count(
        name: str,
        value: float,
        unit: str | None = None,
        attributes: dict[str, str] | None = None,
    ) -> None:
        del unit
        captured_counts.append((name, int(value), attributes or {}))

    def fake_distribution(
        name: str,
        value: float,
        unit: str | None = None,
        attributes: dict[str, str] | None = None,
    ) -> None:
        del unit
        captured_distributions.append((name, value, attributes or {}))

    monkeypatch.setattr("src.request_logging.metrics.count", fake_count)
    monkeypatch.setattr("src.request_logging.metrics.distribution", fake_distribution)

    response = client.get("/health")
    assert response.status_code == 200
    assert captured_counts == []
    assert captured_distributions == []
