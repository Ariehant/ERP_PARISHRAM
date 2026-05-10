"""Fee structure repository (per class + year + head)."""

from __future__ import annotations

import sqlite3

from app.models.fee import FeeStructure


def _row_to_structure(row: sqlite3.Row) -> FeeStructure:
    return FeeStructure(
        id=row["id"],
        class_id=row["class_id"],
        academic_year_id=row["academic_year_id"],
        head=row["head"],
        amount_paise=row["amount_paise"],
        frequency=row["frequency"],
        due_month=row["due_month"],
    )


_COLS = "id, class_id, academic_year_id, head, amount_paise, frequency, due_month"


def create(conn: sqlite3.Connection, fs: FeeStructure) -> int:
    cur = conn.execute(
        """
        INSERT INTO fee_structure
            (class_id, academic_year_id, head, amount_paise, frequency, due_month)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            fs.class_id,
            fs.academic_year_id,
            fs.head,
            fs.amount_paise,
            fs.frequency,
            fs.due_month,
        ),
    )
    return int(cur.lastrowid)


def update(conn: sqlite3.Connection, fs: FeeStructure) -> None:
    if fs.id is None:
        raise ValueError("update requires fs.id")
    conn.execute(
        """
        UPDATE fee_structure SET
            class_id = ?, academic_year_id = ?, head = ?,
            amount_paise = ?, frequency = ?, due_month = ?
        WHERE id = ?
        """,
        (
            fs.class_id,
            fs.academic_year_id,
            fs.head,
            fs.amount_paise,
            fs.frequency,
            fs.due_month,
            fs.id,
        ),
    )


def delete(conn: sqlite3.Connection, fs_id: int) -> None:
    conn.execute("DELETE FROM fee_structure WHERE id = ?", (fs_id,))


def get(conn: sqlite3.Connection, fs_id: int) -> FeeStructure | None:
    cur = conn.execute(f"SELECT {_COLS} FROM fee_structure WHERE id = ?", (fs_id,))
    row = cur.fetchone()
    return _row_to_structure(row) if row else None


def list_for_class(
    conn: sqlite3.Connection, class_id: int, academic_year_id: int
) -> list[FeeStructure]:
    cur = conn.execute(
        f"SELECT {_COLS} FROM fee_structure "
        "WHERE class_id = ? AND academic_year_id = ? "
        "ORDER BY head COLLATE NOCASE, id",
        (class_id, academic_year_id),
    )
    return [_row_to_structure(r) for r in cur.fetchall()]


def replace_for_class(
    conn: sqlite3.Connection,
    class_id: int,
    academic_year_id: int,
    rows: list[FeeStructure],
) -> None:
    """Diff-and-apply: insert new, update existing, delete missing.

    Caller wraps in a transaction.
    """
    existing = {
        fs.id: fs for fs in list_for_class(conn, class_id, academic_year_id) if fs.id is not None
    }
    keep_ids: set[int] = set()
    for fs in rows:
        bound = FeeStructure(
            id=fs.id,
            class_id=class_id,
            academic_year_id=academic_year_id,
            head=fs.head,
            amount_paise=fs.amount_paise,
            frequency=fs.frequency,
            due_month=fs.due_month,
        )
        if bound.id is None or bound.id not in existing:
            create(
                conn,
                FeeStructure(
                    id=None,
                    class_id=class_id,
                    academic_year_id=academic_year_id,
                    head=bound.head,
                    amount_paise=bound.amount_paise,
                    frequency=bound.frequency,
                    due_month=bound.due_month,
                ),
            )
        else:
            keep_ids.add(bound.id)
            update(conn, bound)
    for old_id in existing.keys() - keep_ids:
        delete(conn, old_id)
