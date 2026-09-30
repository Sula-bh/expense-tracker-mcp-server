import json
import os
import sqlite3
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import aiosqlite
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

DB_TIMEOUT = 10

# Use temporary directory which should be writable
DB_PATH = Path(os.getenv("DB_PATH", Path(tempfile.gettempdir()) / "expense.db"))
CATEGORIES_PATH = Path(__file__).resolve().parent / "categories.json"

print(f"Database path: {DB_PATH}")

mcp = FastMCP("ExpenseTracker")


def init_db() -> None:  # Keep as sync for initialization
    try:
        # Use synchronous sqlite3 just for initialization

        with sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT) as c:
            c.execute("PRAGMA journal_mode=WAL")  # Better for concurrent access
            c.execute("""
                CREATE TABLE IF NOT EXISTS expenses(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)
    except Exception as e:
        print(f"Database initialization error: {e}")
        raise


init_db()


@mcp.tool()
async def add_expense(
    expense_date: date,
    amount: Decimal,
    category: str,
    subcategory: str = "",
    note: str = "",
) -> dict[str, str | int | None]:
    """Add a new expense entry to the database."""
    try:
        user_id: str | None = get_http_headers().get("horizon-actor")
        if user_id is None:
            return {"status": "error", "message": "User is not authenticated"}
        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as c:
            cur = await c.execute(
                "INSERT INTO expenses(user_id, date, amount, category, subcategory, note) VALUES (?,?,?,?,?,?)",
                (
                    user_id,
                    expense_date.isoformat(),
                    float(amount),
                    category,
                    subcategory,
                    note,
                ),
            )
            await c.commit()
            return {
                "status": "success",
                "id": cur.lastrowid,
                "message": "Expense added successfully",
            }
    except Exception as e:
        if "readonly" in str(e).lower():
            return {
                "status": "error",
                "message": "Database is in read-only mode. Check file permissions.",
            }
        return {"status": "error", "message": f"Database error: {e!s}"}


@mcp.tool()
async def list_expenses(
    start_date: date, end_date: date
) -> list[dict[str, Any]] | dict[str, str]:
    """List expense entries within an inclusive date range."""
    try:
        user_id: str | None = get_http_headers().get("horizon-actor")
        if user_id is None:
            return {"status": "error", "message": "User is not authenticated"}
        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as c:
            cur = await c.execute(
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                AND user_id = ?
                ORDER BY date DESC, id DESC
                """,
                (start_date.isoformat(), end_date.isoformat(), user_id),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in await cur.fetchall()]
    except Exception as e:
        return {"status": "error", "message": f"Error listing expenses: {e!s}"}


@mcp.tool()
async def update_expense(
    id: int,
    expense_date: date | None = None,
    amount: Decimal | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    note: str | None = None,
) -> dict[str, str]:
    """Edit an expense based on a provided expense id."""
    try:
        user_id: str | None = get_http_headers().get("horizon-actor")
        if user_id is None:
            return {"status": "error", "message": "User is not authenticated"}

        updates: dict[str, str | float] = {}
        if expense_date is not None:
            updates["date"] = expense_date.isoformat()
        if amount is not None:
            updates["amount"] = float(amount)
        if category is not None:
            updates["category"] = category
        if subcategory is not None:
            updates["subcategory"] = subcategory
        if note is not None:
            updates["note"] = note

        if not updates:
            return {"status": "error", "message": "No fields provided to update."}

        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as c:
            columns = ", ".join(f"{key} = ?" for key in updates)
            params: list[str | float] = list(updates.values())
            params.extend([id, user_id])

            cur = await c.execute(
                f"""
                UPDATE expenses
                SET {columns}
                WHERE id = ? AND user_id = ?
                """,
                params,
            )
            await c.commit()
            if cur.rowcount == 1:
                return {
                    "status": "success",
                    "message": f"Updated expense with id {id} successfully",
                }

        return {"status": "error", "message": "Expense id not found or update failed."}

    except Exception as e:
        return {"status": "error", "message": f"Error updating expense: {e!s}"}


@mcp.tool()
async def delete_expense(id: int) -> dict[str, str]:
    """Delete an expense based on a provided expense id."""
    try:
        user_id: str | None = get_http_headers().get("horizon-actor")
        if user_id is None:
            return {"status": "error", "message": "User is not authenticated"}

        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as c:
            cur = await c.execute(
                """
                DELETE FROM expenses
                WHERE id = ? AND user_id = ?
                """,
                (id, user_id),
            )
            await c.commit()
            if cur.rowcount == 1:
                return {
                    "status": "success",
                    "message": f"Deleted expense with id {id} successfully",
                }

        return {
            "status": "error",
            "message": "Expense id not found or deletion failed.",
        }

    except Exception as e:
        return {"status": "error", "message": f"Error deleting expense: {e!s}"}


@mcp.tool()
async def summarize(
    start_date: date, end_date: date, category: str | None = None
) -> list[dict[str, Any]] | dict[str, str]:
    """Summarize expenses by category within an inclusive date range."""
    try:
        user_id: str | None = get_http_headers().get("horizon-actor")
        if user_id is None:
            return {"status": "error", "message": "User is not authenticated"}
        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as c:
            query = """
                SELECT category, SUM(amount) AS total_amount, COUNT(*) as count
                FROM expenses
                WHERE date BETWEEN ? AND ?
                AND user_id = ?
            """
            params: list[str] = [
                start_date.isoformat(),
                end_date.isoformat(),
                user_id,
            ]

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " GROUP BY category ORDER BY total_amount DESC"

            cur = await c.execute(query, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in await cur.fetchall()]
    except Exception as e:
        return {"status": "error", "message": f"Error summarizing expenses: {e!s}"}


@mcp.resource("expense://categories", mime_type="application/json")
def categories() -> str:
    try:
        # Provide default categories if file doesn't exist
        default_categories = {
            "categories": [
                "Food & Dining",
                "Transportation",
                "Shopping",
                "Entertainment",
                "Bills & Utilities",
                "Healthcare",
                "Travel",
                "Education",
                "Business",
                "Other",
            ]
        }

        try:
            with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return json.dumps(default_categories, indent=2)
    except Exception as e:
        return f'{{"error": "Could not load categories: {e!s}"}}'


# Start the server
if __name__ == "__main__":
    # mcp.run()  # local mcp server transport: stdio
    port = int(os.getenv("PORT", "8000"))
    mcp.run(transport="http", host="0.0.0.0", port=port)
