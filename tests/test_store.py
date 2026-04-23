"""Tests for the SQLite credential store."""

from pathlib import Path

import pytest

from authsome.store.sqlite_store import SQLiteStore


class TestSQLiteStore:
    """SQLite store tests."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> SQLiteStore:
        """Create a store in a temp directory."""
        profile_dir = tmp_path / "profiles" / "test"
        profile_dir.mkdir(parents=True)
        s = SQLiteStore(profile_dir)
        yield s
        s.close()

    def test_set_and_get(self, store: SQLiteStore) -> None:
        store.set("key1", '{"value": 1}')
        assert store.get("key1") == '{"value": 1}'

    def test_get_nonexistent(self, store: SQLiteStore) -> None:
        assert store.get("nonexistent") is None

    def test_overwrite(self, store: SQLiteStore) -> None:
        store.set("key1", "v1")
        store.set("key1", "v2")
        assert store.get("key1") == "v2"

    def test_delete_existing(self, store: SQLiteStore) -> None:
        store.set("key1", "v1")
        assert store.delete("key1") is True
        assert store.get("key1") is None

    def test_delete_nonexistent(self, store: SQLiteStore) -> None:
        assert store.delete("nonexistent") is False

    def test_list_keys_all(self, store: SQLiteStore) -> None:
        store.set("a:1", "v")
        store.set("b:2", "v")
        store.set("a:3", "v")
        keys = store.list_keys()
        assert sorted(keys) == ["a:1", "a:3", "b:2"]

    def test_list_keys_prefix(self, store: SQLiteStore) -> None:
        store.set("profile:default:github:connection:personal", "v1")
        store.set("profile:default:github:connection:work", "v2")
        store.set("profile:default:openai:connection:default", "v3")
        store.set("profile:work:github:connection:main", "v4")

        github_keys = store.list_keys("profile:default:github:")
        assert len(github_keys) == 2
        assert "profile:default:github:connection:personal" in github_keys
        assert "profile:default:github:connection:work" in github_keys

    def test_list_keys_empty_store(self, store: SQLiteStore) -> None:
        assert store.list_keys() == []

    def test_context_manager(self, tmp_path: Path) -> None:
        profile_dir = tmp_path / "profiles" / "ctx"
        profile_dir.mkdir(parents=True)
        with SQLiteStore(profile_dir) as s:
            s.set("k", "v")
            assert s.get("k") == "v"

    def test_store_creates_db_file(self, tmp_path: Path) -> None:
        profile_dir = tmp_path / "profiles" / "dbcheck"
        profile_dir.mkdir(parents=True)
        s = SQLiteStore(profile_dir)
        assert (profile_dir / "store.db").exists()
        s.close()

    def test_large_value(self, store: SQLiteStore) -> None:
        big_value = "x" * 100_000
        store.set("big", big_value)
        assert store.get("big") == big_value

    def test_special_characters_in_key(self, store: SQLiteStore) -> None:
        key = "profile:default:my-provider:connection:test_conn-1"
        store.set(key, '{"ok": true}')
        assert store.get(key) == '{"ok": true}'

    def test_connect_error(self, tmp_path: Path) -> None:
        profile_dir = tmp_path / "profiles" / "bad"
        profile_dir.mkdir(parents=True)
        # Create a directory where the db file should be to trigger an error
        (profile_dir / "store.db").mkdir()
        from authsome.errors import StoreUnavailableError

        with pytest.raises(StoreUnavailableError):
            SQLiteStore(profile_dir)

    def test_ensure_connection_error(self, store: SQLiteStore) -> None:
        from authsome.errors import StoreUnavailableError

        store.close()
        with pytest.raises(StoreUnavailableError, match="Store connection is closed"):
            store.get("key1")

    def test_lock_acquire_release_errors(
        self, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mock fcntl to raise OSError
        import fcntl

        def mock_flock(fd, operation):
            raise OSError("Mock error")

        monkeypatch.setattr(fcntl, "flock", mock_flock)

        # lock acquire should catch OSError and just log warning
        store._acquire_lock()
        assert store._lock_fd is not None

        # lock release should catch OSError
        store._release_lock()
        assert store._lock_fd is None

    def test_double_acquire(self, store: SQLiteStore) -> None:
        store._acquire_lock()
        fd1 = store._lock_fd
        store._acquire_lock()  # should early return
        assert store._lock_fd is fd1
        store._release_lock()

    def test_close_sqlite_error(self, store: SQLiteStore) -> None:
        import sqlite3

        class MockConn:
            def close(self):
                raise sqlite3.Error("Mock error")

        store._conn = MockConn()
        store.close()  # should suppress error
        assert store._conn is None
