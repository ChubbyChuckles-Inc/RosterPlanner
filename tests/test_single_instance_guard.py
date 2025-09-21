import importlib
import os
import tempfile

from gui.app import bootstrap


def test_acquire_release_single_instance(tmp_path):
    # Use a unique lock name in temp directory by monkeypatching _default_lock_path indirectly
    lock_name = f"test_lock_{os.getpid()}.lock"

    acquired_first = bootstrap.acquire_single_instance(lock_name)
    assert acquired_first is True

    # Second acquire in same process returns True (idempotent)
    acquired_again = bootstrap.acquire_single_instance(lock_name)
    assert acquired_again is True

    # Release and re-acquire
    bootstrap.release_single_instance()
    reacquired = bootstrap.acquire_single_instance(lock_name)
    assert reacquired is True
    bootstrap.release_single_instance()


def test_single_instance_contention(monkeypatch):
    lock_name = f"contention_{os.getpid()}.lock"
    assert bootstrap.acquire_single_instance(lock_name) is True
    # Simulate another process by importing module fresh - but we can simulate by directly calling again after not releasing.
    # A second acquire in same process is idempotent and returns True, so to test contention we mimic existing file.
    bootstrap.release_single_instance()
    # Manually create file to simulate existing instance.
    path = os.path.join(tempfile.gettempdir(), lock_name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("999999")
    try:
        # Now acquisition should fail because file exists
        assert bootstrap.acquire_single_instance(lock_name) is False
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_single_instance_context_manager():
    lock_name = f"ctx_{os.getpid()}.lock"
    with bootstrap.single_instance(lock_name) as acquired:
        assert acquired is True
    # After exiting context, we can acquire again
    assert bootstrap.acquire_single_instance(lock_name) is True
    bootstrap.release_single_instance()
