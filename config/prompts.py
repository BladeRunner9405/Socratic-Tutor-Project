# config/prompts.py
from pathlib import Path
import yaml

PROMPTS_FILE = Path(__file__).resolve().parent / "prompts.yaml"


def load_prompts():
    if not PROMPTS_FILE.exists():
        raise FileNotFoundError(f"Файл промптов не найден: {PROMPTS_FILE}")
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_PROMPTS = load_prompts()

PRE_CLASSIFIER_PROMPT = _PROMPTS.get("pre_classifier", "")
STRATEGIST_PROMPT = _PROMPTS.get("strategist", "")
ACTOR_SYSTEM_PROMPT = _PROMPTS.get("actor_system", "")
MOVE_ASSERT_INSTRUCTION = _PROMPTS.get("move_assert_instruction", "")
MOVE_HINT_INSTRUCTION = _PROMPTS.get("move_hint_instruction", "")
MOVE_COMPARISON_INSTRUCTION = _PROMPTS.get("move_comparison_instruction", "")  # <-- ДОБАВИТЬ ЭТУ СТРОКУ
MOVE_FEEDBACK_INSTRUCTION = _PROMPTS.get("move_feedback_instruction", "")
MOVE_REDIRECT_INSTRUCTION = _PROMPTS.get("move_redirect_instruction", "")
MOVE_DEFAULT_INSTRUCTION = _PROMPTS.get("move_default_instruction", "")
ACTOR_REGENERATE_STRICT_PROMPT = _PROMPTS.get("actor_regenerate_strict", "")
ACTOR_JUDGE_FEEDBACK_PROMPT = _PROMPTS.get("actor_judge_feedback", "")
JUDGE_PROMPT = _PROMPTS.get("judge", "")