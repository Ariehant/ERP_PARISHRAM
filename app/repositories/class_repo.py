"""Class + Subject repository.

Subjects belong to a class (FK with ``ON DELETE CASCADE``); we keep both in
the same module because they're always edited together via the class form.
Returns ``Class`` and ``Subject`` dataclasses.
"""

from __future__ import annotations

import sqlite3

from app.models.structure import Class, Subject


# ---------------------------------------------------------------------------
# Class
# ---------------------------------------------------------------------------
def _row_to_class(row: sqlite3.Row) -> Class:
    return Class(
        id=row["id"],
        name=row["name"],
        section=row["section"],
        academic_year_id=row["academic_year_id"],
        class_teacher_id=row["class_teacher_id"],
    )


def create_class(conn: sqlite3.Connection, cls: Class) -> int:
    cur = conn.execute(
        """
        INSERT INTO classes (name, section, academic_year_id, class_teacher_id)
        VALUES (?, ?, ?, ?)
        """,
        (cls.name, cls.section, cls.academic_year_id, cls.class_teacher_id),
    )
    return int(cur.lastrowid)


def update_class(conn: sqlite3.Connection, cls: Class) -> None:
    if cls.id is None:
        raise ValueError("update_class requires class.id")
    conn.execute(
        """
        UPDATE classes SET
            name = ?, section = ?, academic_year_id = ?, class_teacher_id = ?
        WHERE id = ?
        """,
        (cls.name, cls.section, cls.academic_year_id, cls.class_teacher_id, cls.id),
    )


def delete_class(conn: sqlite3.Connection, class_id: int) -> None:
    """Hard delete. ON DELETE CASCADE removes subjects."""
    conn.execute("DELETE FROM classes WHERE id = ?", (class_id,))


def get_class(conn: sqlite3.Connection, class_id: int) -> Class | None:
    cur = conn.execute(
        "SELECT id, name, section, academic_year_id, class_teacher_id FROM classes WHERE id = ?",
        (class_id,),
    )
    row = cur.fetchone()
    return _row_to_class(row) if row else None


def list_for_year(conn: sqlite3.Connection, academic_year_id: int) -> list[Class]:
    cur = conn.execute(
        "SELECT id, name, section, academic_year_id, class_teacher_id "
        "FROM classes WHERE academic_year_id = ? "
        "ORDER BY name COLLATE NOCASE, section COLLATE NOCASE, id",
        (academic_year_id,),
    )
    return [_row_to_class(r) for r in cur.fetchall()]


def count_for_year(conn: sqlite3.Connection, academic_year_id: int) -> int:
    cur = conn.execute(
        "SELECT COUNT(*) FROM classes WHERE academic_year_id = ?",
        (academic_year_id,),
    )
    return int(cur.fetchone()[0])


def class_exists_for_year(
    conn: sqlite3.Connection,
    *,
    name: str,
    section: str,
    academic_year_id: int,
    exclude_id: int | None = None,
) -> bool:
    if exclude_id is None:
        cur = conn.execute(
            "SELECT 1 FROM classes WHERE name = ? AND section = ? AND academic_year_id = ? LIMIT 1",
            (name, section, academic_year_id),
        )
    else:
        cur = conn.execute(
            "SELECT 1 FROM classes "
            "WHERE name = ? AND section = ? AND academic_year_id = ? AND id != ? "
            "LIMIT 1",
            (name, section, academic_year_id, exclude_id),
        )
    return cur.fetchone() is not None


def count_students_in_class(conn: sqlite3.Connection, class_id: int) -> int:
    cur = conn.execute("SELECT COUNT(*) FROM students WHERE class_id = ?", (class_id,))
    return int(cur.fetchone()[0])


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------
def _row_to_subject(row: sqlite3.Row) -> Subject:
    return Subject(
        id=row["id"],
        name=row["name"],
        class_id=row["class_id"],
        code=row["code"],
        max_marks=row["max_marks"],
        is_optional=bool(row["is_optional"]),
    )


def list_subjects_for_class(conn: sqlite3.Connection, class_id: int) -> list[Subject]:
    cur = conn.execute(
        "SELECT id, name, code, class_id, max_marks, is_optional "
        "FROM subjects WHERE class_id = ? ORDER BY name COLLATE NOCASE, id",
        (class_id,),
    )
    return [_row_to_subject(r) for r in cur.fetchall()]


def create_subject(conn: sqlite3.Connection, subject: Subject) -> int:
    cur = conn.execute(
        """
        INSERT INTO subjects (name, code, class_id, max_marks, is_optional)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            subject.name,
            subject.code,
            subject.class_id,
            subject.max_marks,
            1 if subject.is_optional else 0,
        ),
    )
    return int(cur.lastrowid)


def update_subject(conn: sqlite3.Connection, subject: Subject) -> None:
    if subject.id is None:
        raise ValueError("update_subject requires subject.id")
    conn.execute(
        """
        UPDATE subjects SET name = ?, code = ?, max_marks = ?, is_optional = ?
        WHERE id = ?
        """,
        (
            subject.name,
            subject.code,
            subject.max_marks,
            1 if subject.is_optional else 0,
            subject.id,
        ),
    )


def delete_subject(conn: sqlite3.Connection, subject_id: int) -> None:
    conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))


def replace_subjects_for_class(
    conn: sqlite3.Connection, class_id: int, subjects: list[Subject]
) -> None:
    """Diff-and-apply: insert new, update existing, delete missing.

    ``subjects`` may carry ``id=None`` for new rows. Subjects whose id is set
    are updated in place; subjects in the DB that are *not* in ``subjects``
    are deleted (cascading any marks once Phase 5 lands).

    Caller is expected to wrap this in a transaction.
    """
    existing = {s.id: s for s in list_subjects_for_class(conn, class_id) if s.id is not None}
    keep_ids: set[int] = set()
    for s in subjects:
        bound = Subject(
            id=s.id,
            name=s.name,
            class_id=class_id,
            code=s.code,
            max_marks=s.max_marks,
            is_optional=s.is_optional,
        )
        if bound.id is None:
            create_subject(conn, bound)
        else:
            keep_ids.add(bound.id)
            if bound.id in existing:
                update_subject(conn, bound)
            else:
                # ID came from a different class — treat as a fresh insert.
                create_subject(
                    conn,
                    Subject(
                        id=None,
                        name=bound.name,
                        class_id=class_id,
                        code=bound.code,
                        max_marks=bound.max_marks,
                        is_optional=bound.is_optional,
                    ),
                )
    for old_id in existing.keys() - keep_ids:
        delete_subject(conn, old_id)
