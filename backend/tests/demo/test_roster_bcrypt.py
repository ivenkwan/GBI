"""Demo roster + bcrypt contract test (uses the backend's app deps)."""

from demo import dataset

from app.core.security import hash_password, verify_password

from . import _SCRIPTS  # noqa: F401 — ensures scripts/ is on sys.path


def test_demo_password_hashes_and_verifies():
    hashed = hash_password(dataset.DEMO_PASSWORD)
    assert hashed != dataset.DEMO_PASSWORD
    assert verify_password(dataset.DEMO_PASSWORD, hashed)
    assert not verify_password("wrong-password", hashed)


def test_roster_emails_are_valid_login_identifiers():
    # Login looks up by lowercased email — the roster must pre-lowercase.
    for entry in dataset.build_roster(3):
        for user in entry["users"]:
            assert user["email"] == user["email"].strip().lower()
            assert "@" in user["email"] and user["email"].endswith(".test")
