# Stock AI Home MySQL Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Point the local `stock-ai` environment at the home MySQL service while leaving the password slot empty for the user.

**Architecture:** Reuse the existing `MYSQL_URL` configuration consumed throughout `stock-ai`. Change only the ignored local `.env`; do not alter application code or commit credentials.

**Tech Stack:** dotenv configuration, SQLAlchemy/PyMySQL URL syntax, shell validation

## Global Constraints

- The connection target is `192.168.1.13:3306`.
- The MySQL user is `stt_app` and the database is `stock_data`.
- Do not print, commit, or otherwise expose any database password.
- Keep the password component empty until the user fills it locally.

---

### Task 1: Update the local MySQL URL

**Files:**
- Modify: `stock-ai/.env`
- Test: configuration shape and Git ignore status only

**Interfaces:**
- Consumes: the existing `MYSQL_URL` dotenv key
- Produces: `mysql+pymysql://stt_app:@192.168.1.13:3306/stock_data`

- [x] **Step 1: Confirm the target file is ignored**

Run: `git check-ignore stock-ai/.env`

Expected: output is `stock-ai/.env` and exit status is 0.

- [x] **Step 2: Replace only the MYSQL_URL assignment**

Set the existing assignment to this exact value:

```dotenv
MYSQL_URL=mysql+pymysql://stt_app:@192.168.1.13:3306/stock_data
```

The user will enter the URL-encoded password between `stt_app:` and `@192.168.1.13`.

- [x] **Step 3: Validate without displaying the secret component**

Parse the value locally and report only scheme, username, host, port, database, and whether the password is empty.

Expected: scheme `mysql+pymysql`, username `stt_app`, host `192.168.1.13`, port `3306`, database `stock_data`, and password empty.

- [x] **Step 4: Confirm no tracked secret or unrelated change was introduced**

Run: `git status --short --ignored stock-ai/.env`

Expected: `!! stock-ai/.env`.
