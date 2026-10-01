# src/core/learner_state.py
import re
from typing import Dict, Union, Set, Optional, List
from sqlalchemy.orm import Session
from src.knowledge.okr_curriculum import OKR_CURRICULUM
from src.db.repository import LearnerStateRepository

_IMPASSE_STORE: Dict[str, int] = {}
# student_id:topic_id -> Set[найденные ключевые концепты]
_CONCEPT_COVERAGE_STORE: Dict[str, Set[str]] = {}


class LearnerStateTracker:
    def __init__(self, db_session: Session, student_id: str, session_id: Optional[str] = None):
        self.db = db_session
        self.repo = LearnerStateRepository(db_session)
        self.student_id = student_id
        self.session_id = session_id
        self.topics_sequence = list(OKR_CURRICULUM.keys())

    def get_current_topic_id(self) -> str:
        for topic_id in self.topics_sequence:
            score = self.repo.get_topic_mastery(self.student_id, topic_id)
            if score < 0.70:
                return topic_id
        return self.topics_sequence[-1]

    def is_course_completed(self) -> bool:
        return all(
            self.repo.get_topic_mastery(self.student_id, topic_id) >= 0.70
            for topic_id in self.topics_sequence
        )

    def get_topic_mastery(self, topic_id: str) -> float:
        return self.repo.get_topic_mastery(self.student_id, topic_id)

    def get_covered_concepts(self, topic_id: str) -> Set[str]:
        return _CONCEPT_COVERAGE_STORE.get(f"{self.student_id}:{topic_id}", set())

    def register_concept_mention(self, topic_id: str, text: str) -> int:
        """Определяет, какие ключевые концепты темы затронуты в сообщении ученика."""
        if topic_id not in OKR_CURRICULUM:
            return 0

        key = f"{self.student_id}:{topic_id}"
        if key not in _CONCEPT_COVERAGE_STORE:
            _CONCEPT_COVERAGE_STORE[key] = set()

        text_lower = text.lower()
        topic_info = OKR_CURRICULUM[topic_id]

        for concept in topic_info.key_concepts:
            concept_words = [w.lower() for w in re.findall(r'[a-zA-Zа-яА-ЯёЁ0-9]+', concept) if len(w) > 3]
            if concept_words and any(w in text_lower for w in concept_words):
                _CONCEPT_COVERAGE_STORE[key].add(concept)

        return len(_CONCEPT_COVERAGE_STORE[key])

    def get_impasse_count(self, topic_id: str) -> int:
        return _IMPASSE_STORE.get(f"{self.student_id}:{topic_id}", 0)

    def increment_impasse(self, topic_id: str) -> int:
        key = f"{self.student_id}:{topic_id}"
        _IMPASSE_STORE[key] = _IMPASSE_STORE.get(key, 0) + 1
        return _IMPASSE_STORE[key]

    def reset_impasse(self, topic_id: str) -> None:
        key = f"{self.student_id}:{topic_id}"
        _IMPASSE_STORE[key] = 0

    def record_attempt_result(
        self,
        topic_id: str,
        evaluation: Union[str, bool],
        user_message: Optional[str] = None
    ) -> float:
        current_score = self.repo.get_topic_mastery(self.student_id, topic_id)

        if isinstance(evaluation, bool):
            raw_delta = 0.25 if evaluation else -0.05
            is_successful = evaluation
            is_error = not evaluation
        elif evaluation == "correct":
            raw_delta = 0.25
            is_successful = True
            is_error = False
        elif evaluation == "partially_correct":
            raw_delta = 0.15
            is_successful = True
            is_error = False
        elif evaluation == "incorrect":
            raw_delta = -0.05
            is_successful = False
            is_error = True
        else:
            raw_delta = 0.0
            is_successful = False
            is_error = False

        key = f"{self.student_id}:{topic_id}"
        if key not in _CONCEPT_COVERAGE_STORE:
            _CONCEPT_COVERAGE_STORE[key] = set()

        # 1. Попытка детекции по ключевым словам
        if user_message and is_successful:
            self.register_concept_mention(topic_id, user_message)

        # 2. Scaffolding credit: если ответ верный (correct), но в прикладной формулировке
        # не было академических терминов, закрываем следующий непокрытый концепт темы
        topic_info = OKR_CURRICULUM.get(topic_id)
        if topic_info and is_successful and evaluation == "correct":
            missing = [c for c in topic_info.key_concepts if c not in _CONCEPT_COVERAGE_STORE[key]]
            if missing:
                _CONCEPT_COVERAGE_STORE[key].add(missing[0])

        covered_concepts = self.get_covered_concepts(topic_id)
        required_concepts_count = min(2, len(topic_info.key_concepts)) if topic_info else 2

        # 3. Расчет скора
        unclamped_score = round(min(1.0, max(0.0, current_score + raw_delta)), 4)

        if len(covered_concepts) < required_concepts_count and unclamped_score >= 0.70:
            target_score = 0.50
        else:
            target_score = unclamped_score

        effective_delta = round(target_score - current_score, 4)

        if hasattr(self.repo, "set_topic_mastery"):
            self.repo.set_topic_mastery(self.student_id, topic_id, target_score)
        else:
            self.repo.update_mastery(self.student_id, topic_id, effective_delta)

        if is_successful:
            self.reset_impasse(topic_id)
        elif is_error:
            self.increment_impasse(topic_id)

        return target_score

    def get_overall_progress(self) -> Dict[str, float]:
        return {
            topic_id: self.repo.get_topic_mastery(self.student_id, topic_id)
            for topic_id in self.topics_sequence
        }

    def get_missing_concepts(self, topic_id: str) -> List[str]:
        if topic_id not in OKR_CURRICULUM:
            return []
        covered = self.get_covered_concepts(topic_id)
        all_concepts = OKR_CURRICULUM[topic_id].key_concepts
        return [c for c in all_concepts if c not in covered]