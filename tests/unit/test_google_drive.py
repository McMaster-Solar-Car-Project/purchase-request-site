from src.google_drive import GoogleDriveClient


class FakeListRequest:
    def execute(self) -> dict[str, list[dict[str, str]]]:
        return {"files": [{"id": "file-id", "name": "receipt.xlsx"}]}


class FakeFilesResource:
    def __init__(self) -> None:
        self.query = ""

    def list(self, *, q: str, fields: str) -> FakeListRequest:
        self.query = q
        assert fields == "files(id, name)"
        return FakeListRequest()


class FakeDriveService:
    def __init__(self) -> None:
        self.files_resource = FakeFilesResource()

    def files(self) -> FakeFilesResource:
        return self.files_resource


def test_find_file_escapes_apostrophes_and_backslashes_in_query() -> None:
    service = FakeDriveService()
    client = GoogleDriveClient()
    client.service = service

    file_id = client.find_file_in_folder("folder'id\\archive", "O'Brian\\receipt.xlsx")

    assert file_id == "file-id"
    assert service.files_resource.query == (
        "name='O\\'Brian\\\\receipt.xlsx' and "
        "'folder\\'id\\\\archive' in parents and trashed=false"
    )
