# Read-only Trello connector for Claude (claude.ai/design)

A tiny **remote MCP server** that lets Claude on the web read your Trello
boards, lists, and cards. There is no official Trello connector, so this fills
the gap. It is **read-only** — it cannot change anything in Trello.

Once deployed you add it under **Settings → Connectors → Add custom connector**
in Claude, and then Claude (including claude.ai/design) can pull your cards.

### Tools it exposes
| Tool | What it does |
|------|--------------|
| `list_boards` | Your open boards (id, name, URL) |
| `list_lists` | Lists/columns on a board |
| `list_cards` | Cards on a board, or in one list |
| `get_card` | Full card detail: description, labels, due, members, checklists, comments, attachment links |
| `search_cards` | Find cards by keyword (whole account or one board) |

---

## Step 1 — Get your Trello credentials (read-only)

1. **API key:** go to <https://trello.com/app-key> while logged in and copy the
   **Key**. (You may be asked to create a Power-Up first — name it anything,
   e.g. "Claude reader"; that's just how Trello issues a key now.)
2. **Read-only token:** open this URL in your browser, replacing `YOUR_KEY`,
   then click **Allow**:

   ```
   https://trello.com/1/authorize?expiration=never&name=ClaudeTrello&scope=read&response_type=token&key=YOUR_KEY
   ```

   `scope=read` means the token can *only read* — even if the URL leaked, no one
   could edit your boards with it. Copy the token Trello shows you.

Keep the **Key** and **Token** handy for Step 3.

---

## Step 2 — Deploy the server (no local install needed)

The simplest path uses **Render's** free tier and builds everything in the
cloud, so you don't need Node or a newer Python on your Mac.

1. Put this folder on GitHub (a private repo is fine). If you have the `gh` CLI:
   ```
   git init && git add -A && git commit -m "Trello MCP connector"
   gh repo create trello-mcp --private --source=. --push
   ```
   (Or create a repo in the GitHub web UI and upload these files.)
2. Go to <https://render.com> → **New + → Blueprint** → pick the repo. Render
   reads `render.yaml` and sets up a Python 3.11 web service automatically.
3. When prompted (or under the service's **Environment** tab) set:
   - `TRELLO_API_KEY` → your key from Step 1
   - `TRELLO_TOKEN` → your read-only token from Step 1
   - `MCP_PATH` → an unguessable path, e.g. `/mcp-7f3a9c2e1b` (make up your own)
4. Deploy. Render gives you a URL like `https://trello-mcp-xxxx.onrender.com`.

Your MCP endpoint is that URL **plus** your `MCP_PATH`, e.g.
`https://trello-mcp-xxxx.onrender.com/mcp-7f3a9c2e1b`.

> **Heads-up on Render free tier:** the service sleeps after inactivity, so the
> first request after a pause takes ~30–60s to wake. Fine for occasional use.

> Prefer containers? A `Dockerfile` is included — deploy it to Fly.io, Railway,
> Cloud Run, or your own VPS instead. Same env vars apply.

---

## Step 3 — Add it to Claude

1. In Claude (web): **Settings → Connectors → Add custom connector**.
2. Paste your full MCP endpoint URL (URL + `MCP_PATH` from Step 2).
3. Save. Claude will connect and discover the five tools above.

Now in claude.ai/design you can say things like *"list my Trello boards"*,
*"pull the cards from the 'Launch' list on my Marketing board"*, or *"search my
Trello for cards mentioning rebrand"* — and use them in your design work.

---

## Security — read this

In this simple setup, **the URL is the only thing protecting your data**: anyone
who has the full URL (including `MCP_PATH`) can read your Trello. That's why:

- `MCP_PATH` must be long and random — treat the full URL like a password.
- The Trello token is `scope=read`, so a leak can't *modify* your boards.
- Don't paste the URL into shared docs, screenshots, or chats.

Want stronger protection? The proper hardening is **OAuth** on the connector
(FastMCP supports it), so Claude authenticates instead of relying on a secret
URL. That's a worthwhile upgrade if this holds sensitive boards — say the word
and I'll wire it in.

---

## Running locally (optional)

Requires Python 3.10+ (your system Python is 3.9, so use a newer one, e.g. via
`pyenv` or `brew install python@3.11`):

```
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your key/token
set -a && source .env && set +a
python trello_mcp_server.py
```

The endpoint will be at `http://localhost:8000$MCP_PATH`. Local HTTP can't be
added to claude.ai (it needs public HTTPS) — local runs are just for testing,
e.g. with the MCP Inspector (`npx @modelcontextprotocol/inspector`).
