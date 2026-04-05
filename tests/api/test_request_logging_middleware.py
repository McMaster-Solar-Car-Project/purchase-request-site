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
