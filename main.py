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
        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as c:
            cur = await c.execute(
                "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
                (expense_date.isoformat(), float(amount), category, subcategory, note),
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
        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as c:
            cur = await c.execute(
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date.isoformat(), end_date.isoformat()),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in await cur.fetchall()]
    except Exception as e:
        return {"status": "error", "message": f"Error listing expenses: {e!s}"}


@mcp.tool()
async def summarize(
    start_date: date, end_date: date, category: str | None = None
) -> list[dict[str, Any]] | dict[str, str]:
    """Summarize expenses by category within an inclusive date range."""
    try:
        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as c:
            query = """
                SELECT category, SUM(amount) AS total_amount, COUNT(*) as count
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """
            params: list[date | str] = [start_date.isoformat(), end_date.isoformat()]

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
