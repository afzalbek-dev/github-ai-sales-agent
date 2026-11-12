"""
GitHub AI Sales & Lead Generation Agent for @afzalbek-dev
Monitors all open issues, pull requests, and follow-up comments across every public repository.
Powered by Gemini AI (gemini-3.8-flash with automatic fallback) + GitHub CLI (gh) + Telegram Alerts.
"""

import html
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_dotenv(env_path: str) -> None:
    """Loads key=value pairs from a local .env file without overwriting existing env vars."""
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_dotenv(os.path.join(PROJECT_DIR, ".env"))

# ----------------- CONFIGURATION -----------------
GITHUB_USER = os.getenv("GITHUB_USER", "afzalbek-dev")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "7196940979"))
OWNER_CONTACT = os.getenv("OWNER_CONTACT", "@Obunachi786")
TELEGRAM_LINK = os.getenv("TELEGRAM_LINK", "https://t.me/Obunachi786")
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "180"))

LOG_FILE = os.path.join(PROJECT_DIR, "agent.log")
STATE_FILE = os.path.join(PROJECT_DIR, "processed_items.json")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# ----------------- TELEGRAM NOTIFIER -----------------
def send_telegram_alert(text: str):
    """Sends immediate lead/sales alert to the owner on Telegram using HTML parse mode."""
    if not TELEGRAM_BOT_TOKEN:
        logging.warning("TELEGRAM_BOT_TOKEN is not set; skipping Telegram alert.")
        return None

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_TELEGRAM_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logging.error(f"Telegram alert error: {exc}")
        return None


# ----------------- GITHUB CLI HELPERS -----------------
def run_gh_cmd(cmd_list: list[str]) -> str | None:
    """Runs a gh CLI command and returns stdout, or None on error."""
    try:
        res = subprocess.run(
            ["gh"] + cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        if res.returncode != 0:
            logging.warning(
                f"gh command failed: {' '.join(cmd_list)} -> {res.stderr.strip()}"
            )
            return None
        return res.stdout.strip()
    except Exception as exc:
        logging.error(f"Error running gh command {cmd_list}: {exc}")
        return None


def load_processed_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                data.setdefault("issues", [])
                data.setdefault("comments", [])
                return data
        except Exception:
            pass
    return {"comments": [], "issues": []}


def save_processed_state(state: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
    except Exception as exc:
        logging.error(f"Error saving state: {exc}")


# ----------------- GEMINI AI SALES ENGINE -----------------
SYSTEM_SALES_PROMPT = f"""
You are the official AI Sales Representative and Lead Closer for Afzalbek Abduraimov (@{GITHUB_USER}).
Your primary goal is to turn incoming GitHub questions, issues, inquiries, or feature requests into paid client orders or product sales.

Key Information & Store Catalog:
1. TeleShop AI — Telegram Mini App (TMA) E-Commerce Template ($39 Gumroad license / $149 full source code on SideProjectors / custom delivery setup from $100).
   Demo: https://afzalbek-dev.github.io/teleshop-tma/
2. TEZish WebApp — Daily Jobs & Local Services Marketplace MVP ($29 on Gumroad / custom setup from $150).
   Demo: https://afzalbek-dev.github.io/tezish-webapp/
3. Custom Development Services:
   - High-load Telegram Bots & WebApps: from $100
   - Autonomous AI Agents (Gemini / LLM): from $120
   - Modern Landing Pages, Admin Dashboards & Startup MVPs: from $150
4. Direct Contact:
   - Telegram: {OWNER_CONTACT} ({TELEGRAM_LINK})
   - Fast response, 24/7 client support, custom customization available upon request.

Response Guidelines:
- Language: Respond in the exact language the user wrote (English, Russian, Uzbek, etc.).
- Tone: Professional, welcoming, helpful, and direct.
- Solution-first: First answer their question or acknowledge their issue concisely and accurately.
- Soft Sales pitch: Gently pitch the ready solution, source code license, or custom implementation by Afzalbek, with a direct call-to-action (CTA) to message on Telegram {OWNER_CONTACT}.
- Signature:
  ---
  *🚀 Afzalbek Dev Team | Need custom features, setup or source code? Contact directly on Telegram: [{OWNER_CONTACT}]({TELEGRAM_LINK})*
"""


def generate_ai_sales_reply(
    user_comment: str, repo_name: str, issue_title: str, thread_context: str = ""
) -> str:
    """Generates a professional sales conversion reply using Gemini AI with fallback."""
    try:
        from google import genai

        client = genai.Client()
        prompt = f"""
Context:
Repository: {repo_name}
Issue/Topic: {issue_title}
{f"Previous Thread Context:{chr(10)}{thread_context}{chr(10)}" if thread_context else ""}
Latest User Message:
\"\"\"{user_comment}\"\"\"

Generate a polite, helpful, and commercially persuasive sales reply for GitHub.
"""
        models_to_try = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash"]
        for model in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        "system_instruction": SYSTEM_SALES_PROMPT,
                        "temperature": 0.7,
                    },
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as model_err:
                logging.warning(f"Model {model} failed, trying next: {model_err}")
                continue
    except Exception as exc:
        logging.error(f"Gemini API error: {exc}")

    return (
        f"Hello! Thank you for reaching out regarding **{repo_name}**.\n\n"
        f"Whether you need technical support, custom feature development, or access to the full turnkey commercial license, "
        f"our founder Afzalbek is available 24/7 to help implement this for your business.\n\n"
        f"👉 **Direct Telegram:** [{OWNER_CONTACT}]({TELEGRAM_LINK})\n\n"
        f"---\n"
        f"*🚀 Afzalbek Dev | Turnkey Telegram WebApps, Bots & Full-Stack Solutions*"
    )


# ----------------- AGENT WORKFLOW -----------------
def fetch_open_issues_across_all_repos() -> list[dict]:
    """Fetches all open issues/PRs across all repositories owned by GITHUB_USER in a single API call."""
    out = run_gh_cmd(["api", f"search/issues?q=user:{GITHUB_USER}+is:open&per_page=100"])
    if not out:
        return []
    try:
        data = json.loads(out)
        return data.get("items", [])
    except Exception as exc:
        logging.error(f"Error parsing GitHub search results: {exc}")
        return []


def fetch_issue_comments(repo_full: str, issue_number: int) -> list[dict]:
    """Fetches comments for a specific issue/PR."""
    out = run_gh_cmd(["api", f"repos/{repo_full}/issues/{issue_number}/comments"])
    if not out:
        return []
    try:
        return json.loads(out)
    except Exception:
        return []


def post_reply_and_notify(
    repo_full: str,
    issue_number: int,
    issue_title: str,
    author: str,
    user_message: str,
    reply_text: str,
    issue_url: str,
    kind: str,
) -> bool:
    """Posts a comment on GitHub and sends an HTML-escaped alert to Telegram."""
    res = run_gh_cmd(
        ["issue", "comment", str(issue_number), "--repo", repo_full, "--body", reply_text]
    )
    if res is None:
        return False

    snippet = html.escape(user_message[:220])
    alert_msg = (
        f"🎯 <b>Yangi GitHub {html.escape(kind)} Lead!</b>\n\n"
        f"📂 <b>Repo:</b> <code>{html.escape(repo_full)}</code>\n"
        f"👤 <b>Mijoz:</b> @{html.escape(author)}\n"
        f"📌 <b>Mavzu:</b> {html.escape(issue_title)}\n"
        f"💬 <b>Xabar:</b> {snippet}\n"
        f"🔗 <a href=\"{html.escape(issue_url)}\">GitHub'da ko'rish</a>\n\n"
        f"🤖 <i>AI Agent sotuv javobini yozdi va {html.escape(OWNER_CONTACT)} ga yo'naltirdi!</i>"
    )
    send_telegram_alert(alert_msg)
    return True


def is_bot_or_owner(author: str) -> bool:
    """Returns True if the author is the repo owner or an automated GitHub bot."""
    if not author:
        return True
    return author == GITHUB_USER or author.endswith("[bot]")


def process_issue_item(item: dict, state: dict) -> None:
    """Processes a single open issue/PR and any unanswered follow-up comments."""
    repo_url = item.get("repository_url", "")
    repo_full = repo_url.split("/repos/")[-1] if "/repos/" in repo_url else ""
    if not repo_full:
        return

    repo_name = repo_full.split("/")[-1]
    issue_number = item.get("number")
    title = item.get("title", "")
    body = item.get("body") or ""
    author = item.get("user", {}).get("login", "")
    issue_url = item.get("html_url", f"https://github.com/{repo_full}/issues/{issue_number}")
    issue_key = f"{repo_full}#{issue_number}"

    # 1. Handle new issue opened by an external human user
    if not is_bot_or_owner(author) and issue_key not in state["issues"]:
        logging.info(f"New external lead found: {issue_key} by @{author}")
        reply_text = generate_ai_sales_reply(
            user_comment=f"{title}\n{body}",
            repo_name=repo_name,
            issue_title=title,
        )
        if post_reply_and_notify(
            repo_full, issue_number, title, author, body or title, reply_text, issue_url, "Issue"
        ):
            state["issues"].append(issue_key)
            save_processed_state(state)

    # 2. Handle follow-up comments on any open issue/PR (even if owner opened the issue)
    if item.get("comments", 0) > 0:
        comments = fetch_issue_comments(repo_full, issue_number)
        if not comments:
            return

        # Check only the latest external comment that hasn't been processed yet
        for comment in comments:
            comment_id = str(comment.get("id"))
            c_author = comment.get("user", {}).get("login", "")
            c_body = comment.get("body") or ""

            if is_bot_or_owner(c_author):
                continue
            if comment_id in state["comments"]:
                continue

            logging.info(f"New follow-up comment {comment_id} on {issue_key} by @{c_author}")
            reply_text = generate_ai_sales_reply(
                user_comment=c_body,
                repo_name=repo_name,
                issue_title=title,
                thread_context=f"Issue description: {body[:400]}",
            )
            if post_reply_and_notify(
                repo_full, issue_number, title, c_author, c_body, reply_text, issue_url, "Comment"
            ):
                state["comments"].append(comment_id)
                save_processed_state(state)


def run_agent_cycle() -> None:
    """Single full scan cycle across all afzalbek-dev GitHub repositories."""
    logging.info("Starting GitHub AI Sales Agent scan cycle...")
    state = load_processed_state()
    items = fetch_open_issues_across_all_repos()
    for item in items:
        process_issue_item(item, state)
    logging.info(f"Scan cycle completed successfully. Checked {len(items)} open items.")


if __name__ == "__main__":
    print(f"[{datetime.now()}] GitHub AI Sales Agent started...")
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_agent_cycle()
        print("Single scan cycle completed.")
    else:
        while True:
            try:
                run_agent_cycle()
            except Exception as exc:
                logging.error(f"Cycle error: {exc}")
            time.sleep(SCAN_INTERVAL_SECONDS)
