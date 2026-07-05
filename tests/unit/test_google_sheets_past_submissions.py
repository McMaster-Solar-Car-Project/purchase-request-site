from typing import Any

from src.google_sheets import _parse_past_submissions_from_grid


def _color(hex_color: str) -> dict[str, float]:
    clean_color = hex_color.removeprefix("#")
    return {
        "red": int(clean_color[0:2], 16) / 255,
        "green": int(clean_color[2:4], 16) / 255,
        "blue": int(clean_color[4:6], 16) / 255,
    }


def _cell(value: str = "", fill: str | None = None) -> dict[str, Any]:
    cell: dict[str, Any] = {"formattedValue": value}
    if fill is not None:
        cell["effectiveFormat"] = {"backgroundColor": _color(fill)}
    return cell


def _row(*cells: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {"values": list(cells)}


def _sheet(title: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "properties": {"title": title},
        "data": [{"rowData": rows}],
    }


def _grid_response(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sheets": [
            _sheet("Website Responses", rows),
            _sheet(
                "Color Legend",
                [
                    _row(_cell("LEGEND (by color code)", "#EDEDED")),
                    _row(_cell("Paid", "#B6D7A8")),
                    _row(_cell("In Review", "#F4CCCC")),
                    _row(_cell("Pending", "#00FFFF")),
                ],
            ),
        ]
    }


def _submission_row(
    timestamp: str,
    email: str,
    amount: str,
    fill: str | None = None,
    drive_link: str = "https://drive.google.com/folders/example",
) -> dict[str, Any]:
    values = [
        timestamp,
        "Requester Name",
        email,
        "123 Main St",
        "transfer@example.com",
        "Software",
        amount,
        drive_link,
        "Internal comment",
    ]
    return _row(*[_cell(value, fill) for value in values])


def test_parse_past_submissions_filters_maps_statuses_and_sorts() -> None:
    grid_response = _grid_response(
        [
            _row(
                _cell("Timestamp"),
                _cell("Name"),
                _cell("Mac Email"),
                _cell("Address"),
                _cell("E-transfer Email"),
                _cell("Team"),
                _cell("Total Reimbursed"),
                _cell("Google Drive Link"),
                _cell("Comments"),
            ),
            _submission_row(
                "2026-01-01 10:00:00",
                "User@Example.com",
                "$100.00",
                "#F4CCCC",
            ),
            _submission_row(
                "2026-03-01 09:30:00",
                "other@example.com",
                "$999.00",
                "#B6D7A8",
            ),
            _submission_row(
                "2026-02-01 09:30:00",
                "user@example.com",
                "$125.50",
                "#B6D7A8",
            ),
            _submission_row(
                "2026-02-15 08:00:00",
                "user@example.com",
                "$175.00",
                "#00FFFF",
            ),
            _submission_row(
                "not a timestamp",
                "user@example.com",
                "$150.00",
                None,
                "",
            ),
        ]
    )

    submissions = _parse_past_submissions_from_grid(grid_response, "user@example.com")

    assert [submission.submitted_at_display for submission in submissions] == [
        "2026-02-15 08:00:00",
        "2026-02-01 09:30:00",
        "2026-01-01 10:00:00",
        "not a timestamp",
    ]
    assert [submission.status for submission in submissions] == [
        "Pending",
        "Paid",
        "In Review",
        "Submitted",
    ]
    assert submissions[0].status_color == "#00FFFF"
    assert submissions[1].status_color == "#B6D7A8"
    assert submissions[1].total_reimbursed == "$125.50"
    assert submissions[3].drive_link == ""


def test_parse_past_submissions_defaults_unmapped_colors_to_submitted() -> None:
    grid_response = _grid_response(
        [
            _row(
                _cell("Timestamp"),
                _cell("Name"),
                _cell("Mac Email"),
                _cell("Address"),
                _cell("E-transfer Email"),
                _cell("Team"),
                _cell("Total Reimbursed"),
                _cell("Google Drive Link"),
                _cell("Comments"),
            ),
            _submission_row(
                "2026-01-01",
                "user@example.com",
                "$100.00",
                "#ABCDEF",
            ),
        ]
    )

    submissions = _parse_past_submissions_from_grid(grid_response, "user@example.com")

    assert len(submissions) == 1
    assert submissions[0].status == "Submitted"
    assert submissions[0].status_color is None


def test_parse_past_submissions_supports_legacy_legend_labels() -> None:
    grid_response = {
        "sheets": [
            _sheet(
                "Website Responses",
                [
                    _row(
                        _cell("Timestamp"),
                        _cell("Name"),
                        _cell("Mac Email"),
                        _cell("Address"),
                        _cell("E-transfer Email"),
                        _cell("Team"),
                        _cell("Total Reimbursed"),
                        _cell("Google Drive Link"),
                        _cell("Comments"),
                    ),
                    _submission_row(
                        "2026-01-01",
                        "user@example.com",
                        "$100.00",
                        "#B6D7A8",
                    ),
                ],
            ),
            _sheet(
                "Color Legend",
                [
                    _row(_cell("LEGEND (by color code)", "#EDEDED")),
                    _row(_cell("Approved by Sonya", "#B6D7A8")),
                ],
            ),
        ]
    }

    submissions = _parse_past_submissions_from_grid(grid_response, "user@example.com")

    assert len(submissions) == 1
    assert submissions[0].status == "Paid"
