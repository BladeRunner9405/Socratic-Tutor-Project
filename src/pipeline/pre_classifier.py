# src/pipeline/pre_classifier.py
import json
import re
from typing import Optional, List, Set
from src.llm.base import BaseLLMClient
from src.core.types import IntentEnum, ClassificationResult
from src.knowledge.okr_curriculum import OKR_CURRICULUM
from config.prompts import PRE_CLASSIFIER_PROMPT

HELP_MARKERS = re.compile(
    r"(?i)\b(не\s*(знаю|помню|понимаю|уверен)|забыл|подскажи|дай\s*подсказку|помоги|сдаюсь|в\s*тупике|не\s*могу)\b"
)
SURRENDER_MARKERS = re.compile(
    r"(?i)\b(не\s*(задумывался|думал|знаю|помню|понимаю|уверен)|без\s*понятия|затрудняюсь|сложно\s*сказать)\b"
)
CAUSAL_MARKERS = re.compile(
    r"(?i)\b(потому\s*что|так\s*как|из-за|смысл\s*в\s*том|суть\s*в\s*том|для\s*того|чтобы|если\s+.*,\s*то|дает|позволяет|влияет|приводит)\b"
)

RUSSIAN_STOPWORDS = {
    "это", "как", "так", "и", "в", "над", "к", "до", "по", "из", "у", "для", 
    "за", "что", "с", "ли", "бы", "то", "или", "да", "но", "не", "на", "же", 
    "вы", "мы", "он", "она", "они", "их", "его", "ее", "чем", "при", "быть", 
    "был", "была", "было", "будет", "были", "такой", "свой", "свои", "очень"
}


def extract_content_tokens(text: str) -> Set[str]:
    words = re.findall(r'[a-zA-Zа-яА-ЯёЁ0-9]+', text.lower())
    return {w for w in words if len(w) >= 3 and w not in RUSSIAN_STOPWORDS}


def compute_containment(source_text: str, target_text: str) -> float:
    """Вычисляет долю слов из source_text, присутствующих в target_text."""
    src_tokens = extract_content_tokens(source_text)
    if not src_tokens:
        return 0.0
    target_tokens = extract_content_tokens(target_text)
    overlap = src_tokens.intersection(target_tokens)
    return round(len(overlap) / len(src_tokens), 4)


class PreClassifier:
    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    def classify(
        self,
        user_message: str,
        last_tutor_question: Optional[str] = None,
        past_student_answers: Optional[List[str]] = None,
        recent_tutor_context: Optional[str] = None
    ) -> ClassificationResult:
        has_help = bool(HELP_MARKERS.search(user_message))
        has_surrender = bool(SURRENDER_MARKERS.search(user_message))
        has_causal = bool(CAUSAL_MARKERS.search(user_message))

        attempt_intent = getattr(
            IntentEnum, "GENUINE_ATTEMPT", 
            getattr(IntentEnum, "ATTEMPT", IntentEnum.CONCEPT_QUESTION)
        )

        # 1. Защита от самоповторов (ученик присылает то же самое)
        if past_student_answers:
            for prev_ans in past_student_answers:
                if compute_containment(user_message, prev_ans) >= 0.70:
                    return ClassificationResult(
                        intent=attempt_intent,
                        confidence=1.0,
                        is_attempt=False,  # Повтор не оценивается
                        target_topic_id=None,
                        attempt_evaluation="none",
                        raw_analysis="DUPLICATE_STUDENT_ANSWER: ученик повторил свою прошлую мысль."
                    )

        # 2. Защита от эхо-ответов по контексту тьютора (только для коротких отписок < 8 слов)
        student_content_tokens = extract_content_tokens(user_message)
        if recent_tutor_context and len(student_content_tokens) < 8:
            tutor_echo = compute_containment(user_message, recent_tutor_context)
            if tutor_echo >= 0.60:
                return ClassificationResult(
                    intent=attempt_intent,
                    confidence=1.0,
                    is_attempt=False,
                    target_topic_id=None,
                    attempt_evaluation="none",
                    raw_analysis=f"TUTOR_ECHO: {tutor_echo} слов скопировано из контекста."
                )

        context_prompt = ""
        if last_tutor_question:
            context_prompt = f"<tutor_question>\n{last_tutor_question}\n</tutor_question>\n"

        messages = [
            {"role": "system", "content": PRE_CLASSIFIER_PROMPT},
            {"role": "user", "content": f"{context_prompt}<student_message>\n{user_message}\n</student_message>"}
        ]

        try:
            response = self.llm.generate(messages, temperature=0.0, max_tokens=256)
            raw_content = response.content.strip()

            json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
            clean_str = json_match.group(0) if json_match else raw_content

            data = json.loads(clean_str)
            normalized_data = {str(k).strip(): v for k, v in data.items()}

            intent_str = str(normalized_data.get("intent", "question")).lower().strip()
            if has_help or has_surrender or intent_str == "help_seeking":
                intent = IntentEnum.HELP_SEEKING
            elif intent_str in IntentEnum.__members__.values():
                intent = IntentEnum(intent_str)
            else:
                intent = IntentEnum.CONCEPT_QUESTION

            target_topic = normalized_data.get("target_topic_id")
            if target_topic not in OKR_CURRICULUM:
                target_topic = None

            raw_eval = str(normalized_data.get("attempt_evaluation", "none")).lower().strip()
            llm_attempt_flag = bool(normalized_data.get("is_attempt", False))

            if (has_surrender or has_help) and not has_causal:
                is_attempt = False
                attempt_eval = "none"
            else:
                is_attempt = llm_attempt_flag or has_causal
                attempt_eval = raw_eval if raw_eval in ["correct", "partially_correct", "incorrect"] else "none"

            return ClassificationResult(
                intent=intent,
                confidence=float(normalized_data.get("confidence", 0.9)),
                is_attempt=is_attempt,
                target_topic_id=target_topic,
                attempt_evaluation=attempt_eval,
                raw_analysis=normalized_data.get("reasoning")
            )
        except Exception as e:
            return ClassificationResult(
                intent=IntentEnum.CONCEPT_QUESTION,
                confidence=0.5,
                is_attempt=False,
                target_topic_id=None,
                attempt_evaluation="none",
                raw_analysis=f"Fallback error: {str(e)}"
            )