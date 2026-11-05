"""
GitHub AI Sales & Lead Generation Agent for @afzalbek-dev
Monitors issues, discussions, mentions, stars, repo visitors/leads across afzalbek-dev repositories.
Powered by Gemini AI (gemini-3.8-flash with gemini-3.7-flash fallback) + GitHub CLI (gh) + Telegram Alerts (@Obunachi786).
"""

import os
import sys
import time
import json
import logging
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime

# ----------------- CONFIGURATION -----------------
GITHUB_USER = "afzalbek-dev"
TELEGRAM_BOT_TOKEN = "8637997053:AAGXpxGndPxGvFBhG2NqSnlNKsc4kNKIOis"
ADMIN_TELEGRAM_ID = 7196940979  # @Obunachi786 (Afzalbek)
OWNER_CONTACT = "@Obunachi786"
TELEGRAM_LINK = "https://t.me/Obunachi786"
PROJECT_DIR = "/home/ubuntu/projects/github_ai_sales_agent"

LOG_FILE = os.path.join(PROJECT_DIR, "agent.log")
STATE_FILE = os.path.join(PROJECT_DIR, "processed_items.json")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ----------------- TELEGRAM NOTIFIER -----------------
def send_telegram_alert(text: str):
    """Sends immediate lead/sales alert to Afzalbek on Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_TELEGRAM_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logging.error(f"Telegram alert error: {e}")
        return None

# ----------------- GITHUB CLI HELPERS -----------------
def run_gh_cmd(cmd_list):
    """Runs a gh CLI command and returns stdout."""
    try:
        res = subprocess.run(
            ["gh"] + cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )
        if res.returncode != 0:
            logging.warning(f"gh command failed: {' '.join(cmd_list)} -> {res.stderr.strip()}")
            return None
        return res.stdout.strip()
    except Exception as e:
        logging.error(f"Error running gh command {cmd_list}: {e}")
        return None

def load_processed_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"comments": [], "issues": []}

def save_processed_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logging.error(f"Error saving state: {e}")

# ----------------- GEMINI AI SALES ENGINE -----------------
SYSTEM_SALES_PROMPT = f"""
You are the official AI Sales Representative and Lead Closer for Afzalbek Abduraimov (@afzalbek-dev).
Your primary goal is to turn incoming GitHub questions, issues, inquiries, or feature requests into paid client orders or product sales.

Key Information & Store Catalog:
1. TeleShop AI — Telegram Mini App (TMA) E-Commerce Template ($39 Gumroad license / $149 full source code on SideProjectors / custom delivery setup from $100).
   Demo: https://afzalbek-dev.github.io/teleshop-tma/
2. TEZish WebApp — Daily Jobs & Local Services Marketplace MVP ($29 on Gumroad / custom setup from $150).
   Demo: https://afzalbek-dev.github.io/tezish-webapp/
3. Custom Development Services:
   - High-load Telegram Bots & WebApps: from $100
   - Modern Landing Pages & Admin Dashboards: from $80
   - Android APK & Full MVP Development: from $150
4. Direct Contact:
   - Telegram: {OWNER_CONTACT} ({TELEGRAM_LINK})
   - Fast response, 24/7 client support, custom customization available upon request.

Response Guidelines:
- Language: Respond in the exact language the user wrote (if English, reply in friendly English; if Russian, in Russian; if Uzbek, in Uzbek).
- Tone: Professional, welcoming, highly helpful, and direct.
- Solution-first: First answer their question or acknowledge their issue concisely and politely.
- Soft Sales pitch: Gently pitch the ready solution, source code license, or custom implementation by Afzalbek, with a direct call-to-action (CTA) to message on Telegram {OWNER_CONTACT}.
- Signature:
  ---
  *🚀 Afzalbek Dev Team | Need custom features, setup or source code? Contact directly on Telegram: [{OWNER_CONTACT}]({TELEGRAM_LINK})*
"""

def generate_ai_sales_reply(user_comment: str, repo_name: str, issue_title: str) -> str:
    """Generates a professional sales conversion reply using Gemini AI with fallback."""
    try:
        from google import genai
        client = genai.Client()
        prompt = f"""
Context:
Repository: {repo_name}
Issue/Topic: {issue_title}
User Message:
\"\"\"{user_comment}\"\"\"

Generate a polite, helpful and commercially persuasive sales reply for GitHub.
"""
        # Try gemini-3.8-flash, fallback to gemini-3.7-flash / gemini-3.5-flash
        models_to_try = ['gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.5-flash']
        for model in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        'system_instruction': SYSTEM_SALES_PROMPT,
                        'temperature': 0.7
                    }
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as model_err:
                logging.warning(f"Model {model} failed, trying next: {model_err}")
                continue

    except Exception as e:
        logging.error(f"Gemini API error: {e}")

    # Robust Fallback
    return (
        f"Hello! Thank you for reaching out regarding **{repo_name}**.\n\n"
        f"Whether you need technical support, custom feature development, or access to the full turnkey commercial license, "
        f"our founder Afzalbek is available 24/7 to help implement this for your business.\n\n"
        f"👉 **Direct Telegram:** [{OWNER_CONTACT}]({TELEGRAM_LINK})\n\n"
        f"---\n"
        f"*🚀 Afzalbek Dev | Turnkey Telegram WebApps, Bots & Full-Stack Solutions*"
    )

# ----------------- AGENT WORKFLOW -----------------
def get_user_repositories():
    """Fetches list of public repositories for afzalbek-dev."""
    out = run_gh_cmd(["repo", "list", GITHUB_USER, "--limit", "30", "--json", "name,description,isPrivate"])
    if not out:
        return []
    try:
        repos = json.loads(out)
        return [r["name"] for r in repos if not r.get("isPrivate", False)]
    except Exception as e:
        logging.error(f"Parse repos error: {e}")
        return []

def scan_repo_issues_and_sell(repo: str, state: dict):
    """Scans open issues, answers inquiries, and pitches sales/consultations."""
    repo_full = f"{GITHUB_USER}/{repo}"
    out = run_gh_cmd(["issue", "list", "--repo", repo_full, "--state", "open", "--json", "number,title,body,author,comments"])
    if not out:
        return

    try:
        issues = json.loads(out)
    except Exception:
        return

    for issue in issues:
        issue_id = f"{repo}#{issue['number']}"
        author = issue.get("author", {}).get("login", "")
        
        # Don't reply if author is owner
        if author == GITHUB_USER:
            continue

        if issue_id in state["issues"]:
            continue

        title = issue.get("title", "")
        body = issue.get("body", "") or ""

        logging.info(f"New potential client lead found: {issue_id} by @{author}")
        
        # Generate AI Sales response
        reply_text = generate_ai_sales_reply(user_comment=f"{title}\n{body}", repo_name=repo, issue_title=title)
        
        # Post comment to GitHub
        add_comment_res = run_gh_cmd(["issue", "comment", str(issue["number"]), "--repo", repo_full, "--body", reply_text])
        
        if add_comment_res is not None:
            logging.info(f"Successfully posted AI Sales response to {issue_id}")
            state["issues"].append(issue_id)
            save_processed_state(state)

            # Alert Afzalbek on Telegram
            alert_msg = (
                f"🎯 *Yangi GitHub Lead & Savdo Javobi!*\n\n"
                f"📂 *Repo:* `{repo_full}`\n"
                f"👤 *Mijoz:* @{author}\n"
                f"📌 *Mavzu:* {title}\n"
                f"💬 *Mijoz xabari:* {body[:200]}...\n\n"
                f"🤖 *AI Agent sotuv javobini qoldirdi va @Obunachi786 ga yo'naltirdi!*"
            )
            send_telegram_alert(alert_msg)

def run_agent_cycle():
    """Single full scan cycle across afzalbek-dev GitHub repositories."""
    logging.info("Starting GitHub AI Sales Agent scan cycle...")
    state = load_processed_state()
    repos = get_user_repositories()
    
    for repo in repos:
        scan_repo_issues_and_sell(repo, state)

    logging.info("Scan cycle completed successfully.")

if __name__ == "__main__":
    print(f"[{datetime.now()}] GitHub AI Sales Agent ishga tushdi...")
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_agent_cycle()
        print("Bitta sikl to'liq bajarildi.")
    else:
        # 24/7 background loop with 3-minute intervals
        while True:
            try:
                run_agent_cycle()
            except Exception as e:
                logging.error(f"Cycle error: {e}")
            time.sleep(180)  # Har 3 daqiqada tekshiradi
