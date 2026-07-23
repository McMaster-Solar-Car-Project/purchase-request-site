from typing import Any

from src.google_sheets import SHEETS_WRITE_RETRIES, GoogleSheetsClient


def test_append_row_uses_google_rate_limit_retries() -> None:
    execute_calls: list[int] = []

    class FakeRequest:
        def execute(self, *, num_retries: int) -> dict[str, Any]:
            execute_calls.append(num_retries)
            return {"updates": {"updatedRows": 1}}

    class FakeValues:
        def append(self, **_kwargs: Any) -> FakeRequest:
            return FakeRequest()

    class FakeSpreadsheets:
        def values(self) -> FakeValues:
            return FakeValues()

    class FakeService:
        def spreadsheets(self) -> FakeSpreadsheets:
            return FakeSpreadsheets()

    client = object.__new__(GoogleSheetsClient)
    client.service = FakeService()
    client.sheet_id = "sheet-id"

    result = client._append_row_with_retries("Responses!A:H", {"values": [[]]})

    assert result == {"updates": {"updatedRows": 1}}
    assert execute_calls == [SHEETS_WRITE_RETRIES]
