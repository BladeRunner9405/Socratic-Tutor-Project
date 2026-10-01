# src/pipeline/detector.py
import re
from typing import List
from src.core.types import HintLevel, PerTurnContract


class DeterministicDetector:
    def __init__(self):
        # 1. Поиск шаблона готового решения кейса
        self.okr_template_solution_regex = re.compile(
            r"(?im)^\s*[-*•]?\s*(?:objective|цель)\s*:\s*.+?\n\s*[-*•]?\s*(?:kr|key\s*result|ключевой\s*результат)\s*:\s*",
            re.MULTILINE
        )
        # 2. Уклонение от подсказки при прямом запросе факта
        self.evasion_regex = re.compile(
            r"(?i)\b(подумай сам|напряги память|вспомни сам|попробуй сам догадаться)\b"
        )
        # 3. Сервисные мета-вопросы о диалоге
        self.meta_question_regex = re.compile(
            r"(?i)\b(что\s+(именно\s+)?тебя\s+интересует|о\s+чем\s+хочешь|какой\s+аспект\s+хочешь|чем\s+могу\s+помочь|задавай\s+вопросы)\b"
        )
        # 4. Служебные теги и маркеры
        self.technical_tags_regex = re.compile(
            r"(?im)^\s*(?:вопрос|question|assertion|check|действие \d+|шаг \d+)\s*:\s*",
            re.MULTILINE
        )
        # 5. Выдача готовых формулировок целей/метрик в кавычках после «например» (суфлирование)
        self.spoonfeeding_regex = re.compile(
            r"(?i)например[,\s]+(?:можешь\s+сказать|возьми|напиши|сформулируй|попробуй|скажи|как)?\s*[«\"'].+?[»\"']"
        )
        # 6. Предложение готовых формулировок с цифрами/процентами в модуле Objective
        self.objective_digits_leak_regex = re.compile(
            r"(?i)[«\"'][^»\"']*(?:\d+|%|процент)[^»\"']*[»\"']"
        )

    def sanitize(self, text: str) -> str:
        if not text:
            return ""

        # 1. Удаление квадратных скобок с инструкциями/метаданными
        cleaned = re.sub(r'\[.*?\]', '', text)

        # 2. Удаление HTML/XML-тегов (<context>, <thought> и т.д.)
        cleaned = re.sub(r'</?[a-zA-Z_]+[^>]*>', '', cleaned)

        # 3. Удаление круглых скобок с системными инструкциями
        cleaned = re.sub(
            r'\((?:[Пп]роверь|[Уу]чти|[Оо]брати|[Вв]нимание|[Кк]онтекст|[Ии]нструкц|[Пп]одсказ|[Шш]аг|[Дд]ействие|[Оо]жидаемый|[Пп]равильный)[^)]*\)',
            '',
            cleaned
        )

        # 4. Удаление служебных маркеров с двоеточием (Вопрос:, Шаг 1:, Assertion:)
        cleaned = self.technical_tags_regex.sub('', cleaned)

        # 5. Удаление служебных команд, интентов и ходов капсом (DEMAND_ANSWER, GIVE_BIG_HINT и т.д.)
        cleaned = re.sub(r'(?m)^\s*[A-Z_]{4,35}:?\s*$', '', cleaned)

        # 6. Удаление изолированного слова «Вопрос:» в начале или середине строки
        cleaned = re.sub(r'(?i)\bвопрос:\s*', '', cleaned)

        # 7. Схлопывание лишних пустых строк
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

        # 4. Обрезка по первому абзацу: забираем только первый смысловой блок
        paragraphs = [p.strip() for p in cleaned.split('\n') if p.strip()]
        if paragraphs:
            cleaned = paragraphs[0]


    def check_leak(
        self,
        draft_response: str,
        forbidden_answers: List[str],
        contract: PerTurnContract
    ) -> bool:
        # 1. Сервисные вопросы техподдержки бракуются всегда
        if self.meta_question_regex.search(draft_response):
            return True

        # 2. Технические скобки и теги разметки бракуются всегда
        if "[" in draft_response and "]" in draft_response:
            return True
        if self.technical_tags_regex.search(draft_response):
            return True

        # 3. Уклонение от подсказки при прямом запросе помощи (H4-H5)
        if contract.max_hint_level >= HintLevel.H4_EXPLAIN_IN_WORDS or contract.is_assert_mode:
            if self.evasion_regex.search(draft_response):
                return True

        if not contract.strict_no_answer or contract.is_assert_mode:
            return False

        # 4. Проверка на прямое вхождение запрещенных ответов темы
        draft_lower = draft_response.lower()
        for forbidden in forbidden_answers:
            if forbidden.lower() in draft_lower:
                return True

        # 5. Проверка шаблона связки Objective + Key Results
        if contract.max_hint_level <= HintLevel.H3_LEADING_QUESTION:
            if self.okr_template_solution_regex.search(draft_response):
                return True

        # 6. Блокировка суфлирования готовых формулировок («например: "создать игру..."»)
        if contract.target_topic_id in ("objective_rules", "key_results_rules"):
            if self.spoonfeeding_regex.search(draft_response):
                return True

        # 7. Блокировка формулировок с цифрами/процентами в теме правил Objective
        if contract.target_topic_id == "objective_rules":
            if self.objective_digits_leak_regex.search(draft_response):
                return True

        return False