import json
import time
from pathlib import Path
from typing import List, Dict, Any
from uuid import uuid4

from .config import CHATS_DIR


def _ensure_dir():
    CHATS_DIR.mkdir(parents=True, exist_ok=True)


def _chat_path(chat_id: str) -> Path:
    return CHATS_DIR / f"{chat_id}.json"


def _default_welcome_message() -> Dict[str, Any]:
    return {
        "id": f"welcome-{int(time.time() * 1000)}",
        "role": "assistant",
        "content": "Hi! Ask me anything about the files in your data folder.",
        "sources": [],
    }


def create_chat(title: str | None = None, messages: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    _ensure_dir()
    chat_id = f"chat-{uuid4().hex}"
    chat = {
        "id": chat_id,
        "title": title or "New chat",
        "messages": messages if messages is not None else [_default_welcome_message()],
        "updated_at": int(time.time()),
    }
    save_chat(chat)
    return chat


def list_chats() -> List[Dict[str, Any]]:
    _ensure_dir()
    chats: List[Dict[str, Any]] = []
    for p in CHATS_DIR.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                chat = json.load(f)
                if isinstance(chat, dict) and chat.get("id"):
                    chats.append(chat)
        except Exception:
            continue
    chats.sort(key=lambda c: c.get("updated_at", 0), reverse=True)
    return chats


def get_chat(chat_id: str) -> Dict[str, Any] | None:
    _ensure_dir()
    p = _chat_path(chat_id)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_chat(chat: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_dir()
    if not chat.get("id"):
        raise ValueError("Chat must include an id")
    chat["updated_at"] = int(time.time())
    p = _chat_path(chat["id"])
    with open(p, "w", encoding="utf-8") as f:
        json.dump(chat, f)
    return chat


def delete_chat(chat_id: str) -> bool:
    _ensure_dir()
    p = _chat_path(chat_id)
    if not p.exists():
        return False
    p.unlink()
    return True
