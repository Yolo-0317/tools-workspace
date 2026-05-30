#!/usr/bin/env node
/**
 * Tail wechat-acp.log and pulse WeChat "typing" while the agent is working.
 * Complements built-in typing (throttled ~5s on ACP chunks) during long session init.
 */
import { spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const INSTANCE = process.env.WECHAT_ACP_INSTANCE || "tools-workspace";
const HOME = process.env.HOME || "";
const INSTANCE_DIR = path.join(HOME, ".wechat-acp", "instances", INSTANCE);
const LOG_FILE = path.join(INSTANCE_DIR, "wechat-acp.log");
const TOKEN_FILE = path.join(INSTANCE_DIR, "token.json");
const STATE_FILE = path.join(INSTANCE_DIR, "state.json");
const PID_FILE = path.join(__dirname, "..", "logs", "typing-watcher.pid");

const TYPING = 1;
const CANCEL = 2;
const PULSE_MS = Number(process.env.WECHAT_TYPING_PULSE_MS || 3000);
const CHANNEL_VERSION = "1.0.2";

/** @type {{ userId: string, contextToken: string, tokenData: object } | null} */
let active = null;
/** @type {ReturnType<typeof setInterval> | null} */
let pulseTimer = null;
/** @type {Map<string, { ticket: string, expiresAt: number }>} */
const ticketCache = new Map();

function log(msg) {
  console.log(`[${new Date().toISOString().slice(11, 19)}] ${msg}`);
}

function randomWechatUin() {
  const uint32 = crypto.randomBytes(4).readUInt32BE(0);
  return Buffer.from(String(uint32), "utf-8").toString("base64");
}

async function apiPost(baseUrl, endpoint, body, token) {
  const url = `${baseUrl.replace(/\/$/, "")}/${endpoint}`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      AuthorizationType: "ilink_bot_token",
      "X-WECHAT-UIN": randomWechatUin(),
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ ...body, base_info: { channel_version: CHANNEL_VERSION } }),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${text}`);
  return text ? JSON.parse(text) : {};
}

async function getTypingTicket(userId, contextToken, tokenData) {
  const cached = ticketCache.get(userId);
  if (cached && cached.expiresAt > Date.now()) return cached.ticket;

  const resp = await apiPost(tokenData.baseUrl, "ilink/bot/getconfig", {
    ilink_user_id: userId,
    context_token: contextToken,
  }, tokenData.token);

  if (resp.typing_ticket) {
    ticketCache.set(userId, {
      ticket: resp.typing_ticket,
      expiresAt: Date.now() + 24 * 60 * 60_000,
    });
    return resp.typing_ticket;
  }
  return null;
}

async function sendTyping(userId, contextToken, tokenData, status) {
  const ticket = await getTypingTicket(userId, contextToken, tokenData);
  if (!ticket) return;
  await apiPost(tokenData.baseUrl, "ilink/bot/sendtyping", {
    ilink_user_id: userId,
    typing_ticket: ticket,
    status,
  }, tokenData.token);
}

function loadState() {
  return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
}

function loadToken() {
  return JSON.parse(fs.readFileSync(TOKEN_FILE, "utf8"));
}

function resolveUserFromLogLine(line) {
  const m = line.match(/Message from ([^:]+):/);
  if (m) return m[1].trim();
  const inj = line.match(/\[inject\] enqueue \S+ for (.+)$/);
  if (inj) return inj[1].trim();
  return null;
}

async function startPulse(userId) {
  if (!fs.existsSync(STATE_FILE) || !fs.existsSync(TOKEN_FILE)) return;
  const state = loadState();
  const tokenData = loadToken();
  const contextToken = state.users?.[userId]?.contextToken;
  if (!contextToken) {
    log(`no contextToken for ${userId}, skip typing`);
    return;
  }

  active = { userId, contextToken, tokenData };
  const pulse = async () => {
    if (!active) return;
    try {
      await sendTyping(active.userId, active.contextToken, active.tokenData, TYPING);
    } catch (err) {
      log(`typing pulse failed: ${err.message}`);
    }
  };

  await pulse();
  if (pulseTimer) clearInterval(pulseTimer);
  pulseTimer = setInterval(pulse, PULSE_MS);
  log(`typing on for ${userId} (every ${PULSE_MS}ms)`);
}

async function stopPulse() {
  if (pulseTimer) {
    clearInterval(pulseTimer);
    pulseTimer = null;
  }
  if (!active) return;
  const { userId, contextToken, tokenData } = active;
  active = null;
  try {
    await sendTyping(userId, contextToken, tokenData, CANCEL);
  } catch {
    // best effort
  }
  log(`typing off for ${userId}`);
}

function handleLine(line) {
  if (/Message from /.test(line) || /\[inject\] enqueue /.test(line)) {
    const userId = resolveUserFromLogLine(line);
    if (userId) startPulse(userId);
    return;
  }
  if (
    /Agent done \(end_turn\)/.test(line) ||
    /Failed to enqueue message/.test(line) ||
    /\[inject\] failed /.test(line) ||
    /Stopping bridge/.test(line)
  ) {
    stopPulse();
  }
}

function main() {
  if (!fs.existsSync(LOG_FILE)) {
    console.error(`Log not found: ${LOG_FILE}`);
    process.exit(1);
  }

  fs.mkdirSync(path.dirname(PID_FILE), { recursive: true });
  fs.writeFileSync(PID_FILE, String(process.pid));

  log(`watching ${LOG_FILE}`);
  const tail = spawn("tail", ["-F", "-n", "0", LOG_FILE], { stdio: ["ignore", "pipe", "inherit"] });
  tail.stdout.on("data", (buf) => {
    for (const line of buf.toString().split("\n")) {
      if (line.trim()) handleLine(line);
    }
  });
  tail.on("exit", (code) => {
    log(`tail exited ${code}`);
    process.exit(code ?? 1);
  });

  const cleanup = () => {
    stopPulse().finally(() => process.exit(0));
  };
  process.on("SIGINT", cleanup);
  process.on("SIGTERM", cleanup);
}

main();
