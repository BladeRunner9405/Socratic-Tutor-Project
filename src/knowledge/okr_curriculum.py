from pathlib import Path
from typing import Dict, List, Optional
import yaml
from pydantic import BaseModel

CURRICULUM_FILE = Path(__file__).parent.parent.parent / "data" / "curriculum.yaml"


class TopicInfo(BaseModel):
    id: str
    title: str
    description: str
    intro_question: Optional[str] = None
    key_concepts: List[str]
    declarative_facts: List[str] = []
    prerequisites: List[str] = []
    forbidden_direct_answers: List[str] = []
    fallback_socratic_prompt: Optional[str] = None
    rubric_criteria: List[str] = []


def load_curriculum_data():
    with open(CURRICULUM_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    topics = {
        topic_id: TopicInfo(**topic_data)
        for topic_id, topic_data in data["topics"].items()
    }
    return data["raw_text"], topics


OKR_RAW_TEXT, OKR_CURRICULUM = load_curriculum_data()