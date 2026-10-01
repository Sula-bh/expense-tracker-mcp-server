# Expense Tracker MCP Server

An MCP (Model Context Protocol) server for managing personal expenses using **FastMCP**, **SQLite**, and **aiosqlite**.

The server provides tools for creating, retrieving, searching, updating, deleting, and summarizing expenses, with per-user data isolation through the authenticated Horizon actor.

## Features

- Add expenses with date, amount, category, subcategory, and note
- Retrieve an individual expense by ID
- Search expenses using multiple optional filters
- Update existing expenses
- Delete individual expenses
- Bulk-delete expenses using date/category/subcategory filters
- Summarize spending by category for a date range
- Expose expense categories through an MCP resource
- Per-user data isolation using the authenticated `horizon-actor`
- SQLite WAL mode for improved read/write concurrency
- Configurable database path and server port
- Supports HTTP transport for remote deployment and stdio transport for local use

## MCP Tools

### `add_expense`

Adds a new expense.

Parameters:

- `expense_date` — expense date
- `amount` — expense amount
- `category` — expense category
- `subcategory` — optional subcategory
- `note` — optional note

### `get_expense`

Fetches a single expense by its ID.

The query is restricted to the authenticated user.

### `list_expenses`

Searches expenses using optional filters:

- `start_date`
- `end_date`
- `category`
- `subcategory`
- `note`
- `min_amount`
- `max_amount`

Multiple filters can be combined.

### `update_expense`

Updates an existing expense by ID.

Only the fields supplied to the tool are changed.

### `delete_expense`

Deletes one expense by ID.

The deletion is restricted to the authenticated user.

### `delete_expenses`

Permanently deletes multiple expenses matching the supplied filters.

Supported filters:

- `start_date` + `end_date`
- `category`
- `subcategory`

At least one filter is required, and both dates must be provided when using a date filter.

### `summarize`

Summarizes expenses by category for an inclusive date range.

Optional category filtering is supported.

## MCP Resource

### `expense://categories`

Provides the available expense categories as JSON.

The server loads categories from `categories.json` when available and falls back to a built-in set of categories.

## Data Storage

The server uses SQLite with the following expense fields:

- `id`
- `user_id`
- `date`
- `amount`
- `category`
- `subcategory`
- `note`

The database path can be configured with the `DB_PATH` environment variable.

If `DB_PATH` is not provided, the server uses a database named `expense.db` in the system temporary directory.

> **Deployment note:** the default temporary-directory database is suitable for demonstrations and testing, but it is not appropriate for durable production storage because temporary storage may be ephemeral.

## Authentication and Data Isolation

Each tool obtains the authenticated user's identity from the `horizon-actor` HTTP header.

Database operations include the authenticated `user_id` in their queries, so users only access their own expenses.

The server does not accept `user_id` as a tool argument.

## Running Locally

Install dependencies with your preferred Python environment/package manager.

For local stdio transport, set:

```text
ENV=local
```

Then run the server:

```bash
python main.py
```

For HTTP transport:

```text
ENV=remote
```

The server uses port `8000` by default.

You can override it with:

```text
PORT=8000
```

Example:

```bash
ENV=remote PORT=8000 python main.py
```

## Installing in Claude Desktop

To install the MCP server locally in Claude Desktop:

```bash
uv run fastmcp install claude-desktop main.py
```

## Remote Deployment

The server is currently hosted on **FastMCP Cloud** on the free tier:

**MCP endpoint:**  
https://sulabh-expense-tracker.fastmcp.app/mcp

The deployment is intended primarily as a demonstration of the MCP server.

### Authentication limitation

The hosted deployment uses the authentication provided by the FastMCP Cloud free tier. The free tier does not provide the option to remove authentication or add organization members.

As a result, other users cannot simply connect to the hosted endpoint and use the expense tracker as a shared public MCP server.

To make the hosted server usable by other users, a deployment/configuration that supports the required authentication and organization-member settings would be needed.

## Technology Stack

- Python
- FastMCP
- Model Context Protocol (MCP)
- SQLite
- aiosqlite
- HTTP / stdio MCP transports

## Project Structure

```text
expense-tracker-mcp-server/
├── main.py
├── categories.json
├── expense.db          # created at runtime when using a local/persistent DB path
└── README.md
```

