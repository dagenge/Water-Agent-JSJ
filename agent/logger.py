"""结构化日志记录器：记录意图识别、Tool调用、代码执行、LLM输入输出"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Any

from agent.config import LOG_DIR

os.makedirs(LOG_DIR, exist_ok=True)


class AgentLogger:
    """本地 JSONL 追踪日志，替代 LangSmith，便于调试和复盘"""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.join(LOG_DIR, f"agent_{self.session_id}.jsonl")
        self._logger = logging.getLogger(f"agent.{self.session_id}")
        self._logger.setLevel(logging.DEBUG)
        if not self._logger.handlers:
            fh = logging.FileHandler(self.log_path, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(fh)

    def _write(self, entry: dict) -> None:
        entry["timestamp"] = datetime.now().isoformat()
        entry["session_id"] = self.session_id
        self._logger.info(json.dumps(entry, ensure_ascii=False))

    def log_intent(self, user_input: str, intent: str, confidence: float) -> None:
        self._write({
            "type": "intent",
            "user_input": user_input,
            "intent": intent,
            "confidence": confidence,
        })

    def log_plan(self, user_input: str, steps: list[str]) -> None:
        self._write({"type": "plan", "user_input": user_input, "steps": steps})

    def log_tool_call(
        self,
        tool_name: str,
        tool_input: dict,
        tool_output: str | None = None,
        sql: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "type": "tool_call",
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": (tool_output or "")[:800],
            "duration_ms": duration_ms,
        }
        if sql:
            entry["sql"] = sql
        self._write(entry)

    def log_code_exec(self, code: str, stdout: str, stderr: str, duration_ms: float) -> None:
        self._write({
            "type": "code_exec",
            "code": code[:2000],
            "stdout": stdout[:2000],
            "stderr": stderr[:500],
            "duration_ms": duration_ms,
        })

    def log_llm(self, stage: str, prompt: str, output: str, duration_ms: float) -> None:
        self._write({
            "type": "llm",
            "stage": stage,
            "prompt": prompt[:2000],
            "output": output[:2000],
            "duration_ms": duration_ms,
        })

    def log_final_output(self, output: str) -> None:
        self._write({"type": "final_output", "output": output[:3000]})

    def log_error(self, stage: str, error: str) -> None:
        self._write({"type": "error", "stage": stage, "error": error})


_logger_instance: AgentLogger | None = None


def get_logger(session_id: str | None = None) -> AgentLogger:
    global _logger_instance
    if _logger_instance is None or session_id:
        _logger_instance = AgentLogger(session_id)
    return _logger_instance
