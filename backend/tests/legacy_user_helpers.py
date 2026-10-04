"""Seed historical roles through SQL without reopening account creation APIs."""


def create_legacy_user(repository, **fields):
    role = fields.pop("role", "student")
    user = repository.create_user(role="student", **fields)
    if role != "student":
        assert role in ("teacher", "admin")
        # Intentional fixture-only access to persisted, pre-migration records.
        with repository._db.transaction() as conn:
            conn.execute("UPDATE users SET role=? WHERE id=?", (role, user.id))
    return repository.get_user_by_id(user.id)
