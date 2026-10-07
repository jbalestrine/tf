import zipfile
import pytest
from managers.data_backup import DataBackupManager, DataBackupError


def test_backup_create_list_and_exclusion(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.json").write_text("{}", encoding="utf-8")
    m = DataBackupManager(tmp_path)
    first = m.create_backup()
    second = m.create_backup()
    assert first and second
    listing = m.list_backups()
    assert len(listing) >= 1
    name = listing[0]["name"]
    with zipfile.ZipFile(m.backup_path(name)) as z:
        names = z.namelist()
    assert any(n.endswith("a.json") for n in names)
    assert not any("backups/" in n for n in names)


def test_backup_rejects_bad_names(tmp_path):
    (tmp_path / "data").mkdir()
    m = DataBackupManager(tmp_path)
    with pytest.raises((DataBackupError, ValueError)):
        m.backup_path("../evil.zip")
