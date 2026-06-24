"""
Read-only Trello MCP server.

Exposes a handful of read-only tools over the MCP "streamable HTTP" transport
so that claude.ai (web) can add it as a custom connector and read your Trello
boards, lists, and cards.

Credentials are read from the environment and never leave this server:
  TRELLO_API_KEY   - your Trello API key (https://trello.com/app-key)
  TRELLO_TOKEN     - a read-only Trello token (see README.md)

Transport / hosting config:
  PORT             - port to listen on (most hosts inject this; default 8000)
  MCP_PATH         - URL path the MCP endpoint is mounted at (default "/mcp").
                     Set this to something unguessable, e.g. "/mcp-7f3a9c2e",
                     and treat the full URL as a secret. This is the only access
                     control in the simple setup, so do not share the URL.

This server only ever issues HTTP GET requests to the Trello API. There are no
tools that create, edit, move, or delete anything in Trello.
"""

import os
from typing import Any, Optional

import httpx
from fastmcp import FastMCP

TRELLO_API_BASE = "https://api.trello.com/1"

API_KEY = os.environ.get("TRELLO_API_KEY", "").strip()
TOKEN = os.environ.get("TRELLO_TOKEN", "").strip()

mcp = FastMCP(
    name="Trello (read-only)",
    instructions=(
        "Read-only access to the user's Trello account. Use list_boards to "
        "discover boards, then list_lists / list_cards to drill in, get_card "
        "for full detail, and search_cards to find cards by keyword. This "
        "connector cannot modify Trello in any way."
    ),
)


def _auth_params(extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    if not API_KEY or not TOKEN:
        raise RuntimeError(
            "Trello credentials are not configured. Set TRELLO_API_KEY and "
            "TRELLO_TOKEN environment variables on the server."
        )
    params: dict[str, Any] = {"key": API_KEY, "token": TOKEN}
    if extra:
        params.update(extra)
    return params


def _get(path: str, extra: Optional[dict[str, Any]] = None) -> Any:
    """Issue a GET against the Trello API and return parsed JSON."""
    url = f"{TRELLO_API_BASE}{path}"
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(url, params=_auth_params(extra))
    if resp.status_code == 401:
        raise RuntimeError(
            "Trello rejected the credentials (401). Check TRELLO_API_KEY / "
            "TRELLO_TOKEN and that the token has not expired."
        )
    resp.raise_for_status()
    return resp.json()


def _card_summary(card: dict[str, Any]) -> dict[str, Any]:
    """Trim a Trello card object down to the fields worth showing."""
    return {
        "id": card.get("id"),
        "name": card.get("name"),
        "url": card.get("shortUrl") or card.get("url"),
        "due": card.get("due"),
        "dueComplete": card.get("dueComplete"),
        "closed": card.get("closed"),
        "idList": card.get("idList"),
        "labels": [
            {"name": lbl.get("name"), "color": lbl.get("color")}
            for lbl in card.get("labels", [])
        ],
        "desc": (card.get("desc") or "")[:500],
    }


@mcp.tool
def list_boards() -> list[dict[str, Any]]:
    """List the open Trello boards the connected account can see.

    Returns each board's id, name, and URL. Use the id with the other tools.
    """
    boards = _get(
        "/members/me/boards",
        {"filter": "open", "fields": "name,url,closed,dateLastActivity"},
    )
    return [
        {
            "id": b.get("id"),
            "name": b.get("name"),
            "url": b.get("url"),
            "lastActivity": b.get("dateLastActivity"),
        }
        for b in boards
    ]


@mcp.tool
def list_lists(board_id: str) -> list[dict[str, Any]]:
    """List the (open) lists/columns on a board.

    Args:
        board_id: The board id, as returned by list_boards.
    """
    lists = _get(f"/boards/{board_id}/lists", {"filter": "open", "fields": "name,pos"})
    return [{"id": l.get("id"), "name": l.get("name")} for l in lists]


@mcp.tool
def list_cards(
    board_id: Optional[str] = None,
    list_id: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List cards on a board or within a single list.

    Provide exactly one of board_id or list_id.

    Args:
        board_id: Return all open cards on this board.
        list_id: Return open cards in this single list/column.
        limit: Maximum number of cards to return (default 100).
    """
    if bool(board_id) == bool(list_id):
        raise ValueError("Provide exactly one of board_id or list_id.")
    fields = "name,shortUrl,url,due,dueComplete,closed,idList,labels,desc"
    if board_id:
        cards = _get(f"/boards/{board_id}/cards", {"filter": "open", "fields": fields})
    else:
        cards = _get(f"/lists/{list_id}/cards", {"filter": "open", "fields": fields})
    return [_card_summary(c) for c in cards[: max(0, limit)]]


@mcp.tool
def get_card(card_id: str) -> dict[str, Any]:
    """Get full detail for one card: description, labels, due date, members,
    checklists, comments, and attachment links.

    Args:
        card_id: The card id (or short id) as returned by the other tools.
    """
    card = _get(
        f"/cards/{card_id}",
        {
            "fields": "name,desc,shortUrl,url,due,dueComplete,closed,idList,idBoard,labels",
            "members": "true",
            "member_fields": "fullName,username",
            "checklists": "all",
            "checkItemStates": "true",
            "attachments": "true",
            "attachment_fields": "name,url",
            "actions": "commentCard",
            "actions_limit": 20,
        },
    )
    summary = _card_summary(card)
    summary.update(
        {
            "idBoard": card.get("idBoard"),
            "members": [
                {"name": m.get("fullName"), "username": m.get("username")}
                for m in card.get("members", [])
            ],
            "checklists": [
                {
                    "name": cl.get("name"),
                    "items": [
                        {"name": it.get("name"), "state": it.get("state")}
                        for it in cl.get("checkItems", [])
                    ],
                }
                for cl in card.get("checklists", [])
            ],
            "attachments": [
                {"name": a.get("name"), "url": a.get("url")}
                for a in card.get("attachments", [])
            ],
            "comments": [
                {
                    "by": (a.get("memberCreator") or {}).get("fullName"),
                    "date": a.get("date"),
                    "text": (a.get("data") or {}).get("text"),
                }
                for a in card.get("actions", [])
                if a.get("type") == "commentCard"
            ],
        }
    )
    # Full description, not the truncated summary version.
    summary["desc"] = card.get("desc") or ""
    return summary


@mcp.tool
def search_cards(query: str, board_id: Optional[str] = None, limit: int = 25) -> list[dict[str, Any]]:
    """Search for cards by keyword across the account, or within one board.

    Args:
        query: Free-text search (matches card name and description).
        board_id: Optional - restrict the search to a single board.
        limit: Maximum number of cards to return (default 25).
    """
    extra: dict[str, Any] = {
        "query": query,
        "modelTypes": "cards",
        "card_fields": "name,shortUrl,url,due,dueComplete,closed,idList,labels,desc",
        "cards_limit": max(1, min(limit, 100)),
    }
    if board_id:
        extra["idBoards"] = board_id
    result = _get("/search", extra)
    return [_card_summary(c) for c in result.get("cards", [])]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    path = os.environ.get("MCP_PATH", "/mcp")
    if not path.startswith("/"):
        path = "/" + path
    mcp.run(transport="http", host="0.0.0.0", port=port, path=path)
