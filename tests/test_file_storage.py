"""Tests for file storage abstraction."""

from app.file_storage import LocalFileStorage


class TestLocalFileStorage:
    def test_save_and_load(self, tmp_path):
        fs = LocalFileStorage(tmp_path / "files")
        fs.save("test.txt", b"hello world")
        assert fs.load("test.txt") == b"hello world"

    def test_load_nonexistent(self, tmp_path):
        fs = LocalFileStorage(tmp_path / "files")
        assert fs.load("nope.txt") is None

    def test_exists(self, tmp_path):
        fs = LocalFileStorage(tmp_path / "files")
        assert not fs.exists("test.txt")
        fs.save("test.txt", b"data")
        assert fs.exists("test.txt")

    def test_delete(self, tmp_path):
        fs = LocalFileStorage(tmp_path / "files")
        fs.save("test.txt", b"data")
        fs.delete("test.txt")
        assert not fs.exists("test.txt")

    def test_delete_nonexistent(self, tmp_path):
        fs = LocalFileStorage(tmp_path / "files")
        fs.delete("nope.txt")  # should not raise

    def test_list_keys(self, tmp_path):
        fs = LocalFileStorage(tmp_path / "files")
        fs.save("a.txt", b"1")
        fs.save("b.txt", b"2")
        fs.save("sub/c.txt", b"3")
        keys = fs.list_keys()
        assert len(keys) == 3
        assert "a.txt" in keys
        assert "b.txt" in keys

    def test_list_keys_with_prefix(self, tmp_path):
        fs = LocalFileStorage(tmp_path / "files")
        fs.save("docs/a.txt", b"1")
        fs.save("docs/b.txt", b"2")
        fs.save("other/c.txt", b"3")
        keys = fs.list_keys("docs")
        assert len(keys) == 2

    def test_full_path(self, tmp_path):
        fs = LocalFileStorage(tmp_path / "files")
        fs.save("test.docx", b"content")
        path = fs.full_path("test.docx")
        assert "test.docx" in path

    def test_nested_directories_created(self, tmp_path):
        fs = LocalFileStorage(tmp_path / "files")
        fs.save("deep/nested/dir/file.txt", b"data")
        assert fs.load("deep/nested/dir/file.txt") == b"data"
