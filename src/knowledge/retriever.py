# src/knowledge/retriever.py
from typing import List, Optional, Tuple
from src.knowledge.okr_curriculum import OKR_RAW_TEXT, OKR_CURRICULUM


class OKRRetriever:
    """
    Модуль извлечения учебного контекста с XML-маркировкой принадлежности к темам (Pisan, 2026).
    """

    def __init__(self, raw_text: str = OKR_RAW_TEXT):
        self.raw_text = raw_text.strip()
        self.paragraphs = [p.strip() for p in self.raw_text.split("\n") if p.strip()]
        self.tagged_paragraphs: List[Tuple[str, str]] = [
            (self.detect_topic_by_content(p) or "okr_basics", p)
            for p in self.paragraphs
        ]

    def get_full_text(self) -> str:
        return self.raw_text

    def detect_topic_by_content(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        topic_scores = {}

        for topic_id, topic in OKR_CURRICULUM.items():
            score = 0
            for concept in topic.key_concepts:
                if concept.lower() in text_lower:
                    score += 2
            for word in topic.title.lower().split():
                if len(word) > 3 and word in text_lower:
                    score += 1
            if score > 0:
                topic_scores[topic_id] = score

        if topic_scores:
            return max(topic_scores, key=topic_scores.get)
        return None

    def retrieve_relevant_snippets(self, query: str, active_topic_id: Optional[str] = None) -> List[str]:
        query_words = [w.lower() for w in query.split() if len(w) > 3]
        target_topic = active_topic_id or "okr_basics"
        topic_keywords = [k.lower() for k in OKR_CURRICULUM[target_topic].key_concepts]

        current_topic_snippets = []
        other_topic_snippets = []

        for p_topic_id, para in self.tagged_paragraphs:
            para_lower = para.lower()
            matches_topic = (p_topic_id == target_topic) or any(kw in para_lower for kw in topic_keywords)
            matches_query = any(w in para_lower for w in query_words)

            if matches_topic or matches_query:
                topic_title = OKR_CURRICULUM.get(p_topic_id, OKR_CURRICULUM[target_topic]).title
                if p_topic_id == target_topic:
                    current_topic_snippets.append(
                        f'<current_topic_context topic="{topic_title}">\n{para}\n</current_topic_context>'
                    )
                else:
                    other_topic_snippets.append(
                        f'<reference_context topic="{topic_title}">\n{para}\n</reference_context>'
                    )

        combined = current_topic_snippets + other_topic_snippets
        if not combined:
            fallback_para = self.paragraphs[0]
            fallback_title = OKR_CURRICULUM[target_topic].title
            return [f'<current_topic_context topic="{fallback_title}">\n{fallback_para}\n</current_topic_context>']

        return combined[:3]