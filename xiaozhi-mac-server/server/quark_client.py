"""Quark Drive bridge: search via official CLI, resolve CDN URL via Open API."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import httpx

from server.config import settings

log = logging.getLogger(__name__)

# Public constants embedded in quark-drive.cjs (WILD_DEFAULT_CLIENT_INFO).
_QUARK_CLIENT_ID = "third_party_agent"
_QUARK_SIGN_KEY = "cf134812e2de4032bd1cb7c3727e84b3"
_QUARK_API_BASE = "https://open-api-drive.quark.cn"
# Quark Open API rejects get_download_url above this size (bytes).
QUARK_STREAM_MAX_BYTES = 52 * 1024 * 1024
_MEDIA_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".aac",
    ".wav",
    ".flac",
    ".ogg",
    ".opus",
    ".mp4",
    ".mkv",
}
_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
_DISFAVOR_NAME_PARTS = ("预告", "片花", "铃声", "采访", "歌单", "mv", "bgm", "试播", "片头")


@dataclass(frozen=True)
class QuarkFile:
    fid: str
    filename: str
    size: int
    format_type: str

    @property
    def ext(self) -> str:
        return Path(self.filename).suffix.lower()


@dataclass(frozen=True)
class QuarkStreamSource:
    fid: str
    filename: str
    size: int
    download_url: str
    cookie: str
    # ffmpeg -map selector, e.g. "0:a:m:language:eng" or "0:a:2" (3rd audio = English in 国粤英)
    audio_map: str | None = None

    @property
    def ext(self) -> str:
        return Path(self.filename).suffix.lower()

    @property
    def is_video(self) -> bool:
        return self.ext in _VIDEO_EXTENSIONS

    @property
    def needs_audio_extract(self) -> bool:
        return self.is_video or self.size > QUARK_STREAM_MAX_BYTES


class QuarkClient:
    def __init__(
        self,
        cli_path: Path,
        hermes_config_path: Path,
        hermes_session_id: str | None = None,
    ) -> None:
        self.cli_path = cli_path
        self.hermes_config_path = hermes_config_path
        self.hermes_session_id = hermes_session_id or self._read_user_id()

    @classmethod
    def from_env(cls, workspace_root: Path | None = None) -> QuarkClient | None:
        enabled = os.getenv("QUARK_STREAM_ENABLED", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        if not enabled:
            return None

        root = workspace_root or Path(__file__).resolve().parents[2]
        default_cli = (
            root / ".cursor/skills/quarkclouddrive/scripts/quark-drive.cjs"
        )
        cli_path = Path(os.getenv("QUARK_DRIVE_CLI", str(default_cli)))
        config_path = Path(
            os.getenv(
                "QUARK_HERMES_CONFIG",
                str(root / ".cursor/skills/quarkclouddrive/hermes/config.json"),
            )
        )
        if not cli_path.is_file():
            log.warning("Quark CLI not found: %s", cli_path)
            return None
        if not config_path.is_file():
            log.warning("Quark hermes config not found: %s", config_path)
            return None
        return cls(
            cli_path=cli_path,
            hermes_config_path=config_path,
            hermes_session_id=os.getenv("HERMES_SESSION_ID") or None,
        )

    def _read_user_id(self) -> str:
        data = json.loads(self.hermes_config_path.read_text(encoding="utf-8"))
        user_id = data.get("currentUserId")
        if not user_id:
            raise RuntimeError("Quark hermes config missing currentUserId")
        return str(user_id)

    def _load_access_token(self) -> str:
        data = json.loads(self.hermes_config_path.read_text(encoding="utf-8"))
        user_id = data.get("currentUserId")
        if not user_id:
            raise RuntimeError("Quark hermes config missing currentUserId")
        account = data.get(user_id) or {}
        token = account.get("accessToken")
        if not token:
            raise RuntimeError("Quark not logged in (missing accessToken)")
        return str(token)

    def _persist_access_token(self, token: str, *, expires_at: str | None = None) -> None:
        """Save rotated token from Quark response header ``x-new-access-token``."""
        path = self.hermes_config_path
        data = json.loads(path.read_text(encoding="utf-8"))
        user_id = data.get("currentUserId")
        if not user_id or user_id not in data:
            return
        account = data[user_id] if isinstance(data[user_id], dict) else {}
        account["accessToken"] = token
        if expires_at:
            try:
                account["accessTokenExpiresAt"] = int(expires_at)
            except ValueError:
                pass
        data[user_id] = account
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        log.info("Quark access token rotated via response header")

    def _cli_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["HERMES_SESSION_ID"] = self.hermes_session_id or self._read_user_id()
        return env

    def _run_cli(self, *args: str) -> str:
        cmd = ["node", str(self.cli_path), *args]
        # Keep short: long CLI hangs feel like Xiaozhi "no response".
        timeout_s = float(os.getenv("QUARK_CLI_TIMEOUT", "12"))
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=self._cli_env(),
            timeout=timeout_s,
        )
        if proc.returncode != 0:
            tail = (proc.stdout + proc.stderr)[-500:]
            raise RuntimeError(f"quark CLI failed ({proc.returncode}): {tail}")
        return proc.stdout

    @staticmethod
    def _parse_ndjson(stdout: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def search_audio(self, keyword: str, limit: int = 20) -> list[QuarkFile]:
        return self.search_media(keyword, limit=limit, audio_only=True)

    @staticmethod
    def _rows_to_quark_files(
        rows: list[dict[str, Any]],
        *,
        limit: int,
        audio_only: bool,
    ) -> list[QuarkFile]:
        files: list[QuarkFile] = []
        for item in rows[:limit]:
            name = str(item.get("filename") or "")
            ext = Path(name).suffix.lower()
            if ext not in _MEDIA_EXTENSIONS:
                continue
            if audio_only and ext in _VIDEO_EXTENSIONS:
                continue
            files.append(
                QuarkFile(
                    fid=str(item.get("fid") or ""),
                    filename=name,
                    size=int(item.get("size") or 0),
                    format_type=str(item.get("format_type") or ""),
                )
            )
        return files

    @staticmethod
    def _load_artifact_rows(path: str) -> list[dict[str, Any]]:
        artifact_path = Path(path)
        if not artifact_path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        try:
            for line in artifact_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
        except (OSError, json.JSONDecodeError):
            return []
        return rows

    def _search_open_api(
        self, keyword: str, *, limit: int = 20, audio_only: bool = False
    ) -> list[QuarkFile]:
        """Direct Open API search (no Agent CLI). Used when CLI is unavailable."""
        body: dict[str, Any] = {
            "search_type": "mix",
            "keyword": keyword,
            "size": max(1, min(limit, 100)),
        }
        if audio_only:
            body["category"] = 2
        payload = self._signed_post("/agent/v1/file/search", body)
        file_list = list((payload.get("data") or {}).get("file_list") or [])
        return self._rows_to_quark_files(file_list, limit=limit, audio_only=audio_only)

    def search_media(self, keyword: str, limit: int = 20, *, audio_only: bool = False) -> list[QuarkFile]:
        # Prefer Open API (seconds). Only fall back to CLI when Open API errors —
        # empty result means "not found", not "try slower path".
        try:
            return self._search_open_api(keyword, limit=limit, audio_only=audio_only)
        except Exception as exc:
            log.warning("Quark Open API search failed for %r: %s; trying CLI", keyword, exc)

        args = [
            "search",
            "--keyword",
            keyword,
            "--size",
            str(max(1, min(limit, 100))),
            "--stdout-only",
        ]
        if audio_only:
            args.extend(["--category", "2"])
        try:
            stdout = self._run_cli(*args)
            rows = self._parse_ndjson(stdout)
            result = next(
                (row for row in rows if row.get("action") == "search" and row.get("type") == "result"),
                None,
            )
            if result:
                file_list = list((result.get("data") or {}).get("file_list") or [])
                artifact = next((row for row in rows if row.get("type") == "artifact"), None)
                if artifact:
                    artifact_path = str((artifact.get("data") or {}).get("file_path") or "")
                    artifact_rows = self._load_artifact_rows(artifact_path)
                    if artifact_rows:
                        file_list = artifact_rows
                return self._rows_to_quark_files(file_list, limit=limit, audio_only=audio_only)
        except Exception as exc:
            log.warning("Quark CLI search failed for %r: %s", keyword, exc)
        return []

    @staticmethod
    def _direct_streamable(files: list[QuarkFile]) -> list[QuarkFile]:
        return [
            item
            for item in files
            if item.fid and 0 < item.size <= QUARK_STREAM_MAX_BYTES and item.ext not in _VIDEO_EXTENSIONS
        ]

    @staticmethod
    def _video_candidates(files: list[QuarkFile]) -> list[QuarkFile]:
        return [
            item
            for item in files
            if item.fid and item.size > 0 and item.ext in _VIDEO_EXTENSIONS
        ]

    @staticmethod
    def rank_matches(
        keyword: str,
        files: list[QuarkFile],
        *,
        prefer_audio: bool = True,
        filename_bonus: int = 0,
        bonus_for: Callable[[QuarkFile], int] | None = None,
    ) -> list[QuarkFile]:
        key = keyword.strip().lower()
        direct = QuarkClient._direct_streamable(files)
        videos = QuarkClient._video_candidates(files)
        if not direct and not videos:
            return []

        def extra_bonus(item: QuarkFile) -> int:
            return filename_bonus + (bonus_for(item) if bonus_for else 0)

        def audio_score(item: QuarkFile) -> tuple[int, int]:
            name = item.filename.lower()
            exact = 100 if key and key in name else 0
            story_bonus = 10 if "故事" in name or "mp3" in name else 0
            mp3_bonus = 15 if item.ext == ".mp3" else 0
            m4a_penalty = -10 if item.ext == ".m4a" else 0
            trailer_penalty = -40 if any(part in name for part in _DISFAVOR_NAME_PARTS) else 0
            return (
                exact + story_bonus + mp3_bonus + m4a_penalty + trailer_penalty + extra_bonus(item),
                -item.size,
            )

        def video_score(item: QuarkFile) -> tuple[int, int]:
            name = item.filename.lower()
            exact = 100 if key and key in name else 0
            fmt = 10 if item.ext == ".mp4" else 0
            sequel_penalty = (
                -20
                if ("2" in name or "二" in name) and ("2" not in key and "二" not in key)
                else 0
            )
            return (exact, fmt + sequel_penalty)

        ranked_audio = sorted(direct, key=audio_score, reverse=True)
        ranked_video = sorted(videos, key=video_score, reverse=True)
        if prefer_audio and ranked_audio:
            return ranked_audio
        if ranked_audio and key and key in ranked_audio[0].filename.lower():
            return ranked_audio
        return ranked_audio + ranked_video

    def _signed_post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST signed Quark Open API; rotate token from ``x-new-access-token`` and retry once on 11017."""

        def _once(access_token: str) -> tuple[httpx.Response, dict[str, Any]]:
            tm = str(int(time.time() * 1000))
            pan_token = hashlib.sha256(
                f"POST&{path}&{tm}&{_QUARK_SIGN_KEY}".encode()
            ).hexdigest()
            req_id = str(uuid.uuid4())
            url = (
                f"{_QUARK_API_BASE}{path}?req_id={req_id}"
                f"&access_token={quote(access_token, safe='')}"
            )
            headers = {
                "x-pan-client-id": _QUARK_CLIENT_ID,
                "x-pan-tm": tm,
                "x-pan-token": pan_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            # Resolve/search should finish well under MCP patience (~30s).
            with httpx.Client(timeout=18.0) as client:
                resp = client.post(url, headers=headers, json=body)
                try:
                    payload = resp.json()
                except ValueError:
                    payload = {}
            new_token = resp.headers.get("x-new-access-token")
            if new_token and new_token != access_token:
                self._persist_access_token(
                    new_token,
                    expires_at=resp.headers.get("x-new-access-token-expires-at"),
                )
            return resp, payload if isinstance(payload, dict) else {}

        access_token = self._load_access_token()
        resp, payload = _once(access_token)
        detail = payload.get("error_info") or resp.text[:200] or f"HTTP {resp.status_code}"
        errno = payload.get("errno")
        expired = (
            resp.status_code == 401
            or errno == 11017
            or "宽限期已过期" in str(detail)
            or "Access Token" in str(detail)
        )
        if expired:
            # Prefer header token; else re-read hermes (another process may have rotated).
            refreshed = resp.headers.get("x-new-access-token") or self._load_access_token()
            if refreshed and refreshed != access_token:
                resp, payload = _once(refreshed)
                detail = (
                    payload.get("error_info") or resp.text[:200] or f"HTTP {resp.status_code}"
                )
            elif not resp.headers.get("x-new-access-token"):
                log.warning(
                    "Quark token expired and response missing x-new-access-token; "
                    "re-login may be required"
                )
        if resp.status_code >= 400 or payload.get("status") != 0:
            raise RuntimeError(detail)
        return payload

    def _resolve_via_multi(self, fid: str) -> dict[str, Any]:
        payload = self._signed_post(
            "/open/v1/file/multi_get_download_url",
            {"fids": [fid]},
        )
        rows = payload.get("data") or []
        if not rows:
            raise RuntimeError("multi_get_download_url returned empty data")
        row = rows[0]
        if not row.get("download_url"):
            raise RuntimeError("multi_get_download_url returned empty download_url")
        return row

    def resolve_stream_source(self, fid: str, *, filename_hint: str = "", size_hint: int = 0) -> QuarkStreamSource:
        data: dict[str, Any] | None = None
        try:
            payload = self._signed_post("/open/v1/file/get_download_url", {"fid": fid})
            data = payload.get("data") or {}
        except RuntimeError as exc:
            if "size limit" not in str(exc).lower():
                raise
            data = self._resolve_via_multi(fid)
        if not data or not data.get("download_url"):
            data = self._resolve_via_multi(fid)
        # Reload after possible token rotation inside _signed_post.
        access_token = self._load_access_token()
        cookie = f"x_pan_client_id={_QUARK_CLIENT_ID};x_pan_access_token={access_token}"
        return QuarkStreamSource(
            fid=str(data.get("fid") or fid),
            filename=str(data.get("file_name") or filename_hint or ""),
            size=int(data.get("size") or size_hint or 0),
            download_url=str(data.get("download_url")),
            cookie=cookie,
        )

    @staticmethod
    def pick_best_match(keyword: str, files: list[QuarkFile]) -> QuarkFile | None:
        ranked = QuarkClient.rank_matches(keyword, files)
        return ranked[0] if ranked else None

    def _try_index_source(
        self,
        catalog_key: str,
        *,
        keyword: str,
        episode: str | None,
        prefer_audio: bool,
        user_text: str = "",
    ) -> QuarkStreamSource | None:
        from server.media_index import index_available, pick_best_file

        if not index_available():
            return None
        picked = pick_best_file(
            catalog_key,
            keyword=keyword,
            episode=episode,
            prefer_audio=prefer_audio,
            user_text=user_text,
        )
        if picked is None:
            return None
        try:
            source = self.resolve_stream_source(
                picked.fid,
                filename_hint=picked.filename,
                size_hint=picked.size,
            )
            log.info(
                "Media index hit: %s -> %s",
                catalog_key,
                picked.filename,
            )
            return source
        except Exception as exc:
            log.warning(
                "Media index resolve failed %s (%s): %s",
                catalog_key,
                picked.filename,
                exc,
            )
            return None

    def find_stream_source(
        self,
        keyword: str,
        *,
        user_text: str = "",
        media_hint: str = "any",
    ) -> QuarkStreamSource | None:
        from server.content_catalog import catalog_filename_bonus, resolve_play_request
        from server.quark_picker import reorder_candidates_by_llm

        key = keyword.strip()
        if not key:
            return None
        utterance = (user_text or keyword).strip()
        hint = (media_hint or "any").strip().lower()
        if hint not in {"story_audio", "movie", "music", "any"}:
            hint = "any"

        search_key, hint, catalog_entry = resolve_play_request(
            key, user_text=utterance, media_hint=hint
        )
        key = search_key or key
        if catalog_entry:
            log.info(
                "Content catalog hit: %s -> %s",
                catalog_entry.key,
                catalog_entry.path_hint,
            )
            indexed = self._try_index_source(
                catalog_entry.key,
                keyword=key,
                episode=catalog_entry.episode,
                prefer_audio=hint != "movie",
                user_text=utterance,
            )
            if indexed is not None:
                return indexed

        wants_video = hint == "movie"
        prefer_audio = hint != "movie"
        # One search key per resolve — extra queries stacked CLI/API latency into "freeze".
        if catalog_entry and catalog_entry.search_queries:
            search_keys = list(catalog_entry.search_queries)[:1]
        elif hint == "story_audio":
            search_keys = [key]
        elif hint == "movie":
            search_keys = [key]
        elif hint == "music":
            search_keys = [key]
        else:
            search_keys = [key]

        ranked: list[QuarkFile] = []
        seen: set[str] = set()
        catalog_bonus = (
            (lambda f: catalog_filename_bonus(catalog_entry, f.filename))
            if catalog_entry
            else None
        )
        for query in search_keys:
            try:
                files = self.search_media(query, limit=settings.quark_pick_top)
            except Exception as exc:
                log.warning("Quark search failed for %r: %s", query, exc)
                continue
            for item in self.rank_matches(
                key,
                files,
                prefer_audio=prefer_audio,
                bonus_for=catalog_bonus,
            ):
                if item.fid in seen:
                    continue
                seen.add(item.fid)
                ranked.append(item)

        if catalog_entry and ranked:
            boosted = [
                f
                for f in ranked
                if catalog_filename_bonus(catalog_entry, f.filename) > 0
            ]
            if boosted:
                ranked = boosted

        if not wants_video:
            audio_first = [f for f in ranked if f.ext not in _VIDEO_EXTENSIONS]
            video_rest = [f for f in ranked if f.ext in _VIDEO_EXTENSIONS]
            ranked = audio_first + video_rest

        if not ranked:
            return None

        top_n = max(1, settings.quark_pick_top)
        ranked = ranked[:top_n]
        ranked = reorder_candidates_by_llm(
            utterance,
            key,
            ranked,
            media_hint=hint,
        )

        last_error: Exception | None = None
        for candidate in ranked[:3]:
            try:
                return self.resolve_stream_source(
                    candidate.fid,
                    filename_hint=candidate.filename,
                    size_hint=candidate.size,
                )
            except Exception as exc:
                last_error = exc
                log.warning(
                    "resolve failed fid=%s file=%s: %s",
                    candidate.fid,
                    candidate.filename,
                    exc,
                )
        if last_error is not None:
            log.warning("all stream candidates failed for %r: %s", key, last_error)
        return None
