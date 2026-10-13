from src.core.assets import asset_version


def test_changing_an_imported_module_changes_the_asset_version(tmp_path):
    entry = tmp_path / "dashboard.js"
    entry.write_text('import "./dashboard/forms.js";')
    modules = tmp_path / "dashboard"
    modules.mkdir()
    imported = modules / "forms.js"
    imported.write_text("export const version = 1;")
    before = asset_version(tmp_path)
    assert asset_version(tmp_path) == before

    imported.write_text("export const version = 2;")

    assert asset_version(tmp_path) != before
    assert entry.read_text() == 'import "./dashboard/forms.js";'
