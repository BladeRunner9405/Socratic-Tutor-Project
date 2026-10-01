import inspect
from unittest.mock import MagicMock
import pytest

from src.core.policy_core import PolicyCore
from src.core.learner_state import LearnerStateTracker
from src.core.types import HintLevel, IntentEnum, PerTurnContract


@pytest.fixture
def mock_state_tracker():
    tracker = MagicMock(spec=LearnerStateTracker)
    tracker.get_current_topic_id.return_value = "objective_rules"
    tracker.get_topic_mastery.return_value = 0.0
    return tracker


@pytest.fixture
def policy_core():
    return PolicyCore()


class TestPolicyCoreInvariants:
    """Проверка математических и архитектурных инвариантов ядра политики (Pisan, 2026)."""

    def test_p2_trust_boundary_signature(self, policy_core):
        """Инвариант P2: Метод compute_contract не должен принимать сырой текст сообщения."""
        sig = inspect.signature(policy_core.compute_contract)
        param_names = list(sig.parameters.keys())
        
        forbidden_params = {"message", "user_message", "student_text", "text", "prompt"}
        for p in param_names:
            assert p.lower() not in forbidden_params, (
                f"Нарушение границы доверия P2: параметр '{p}' может передавать нефильтрованный текст пользователя"
            )

    @pytest.mark.parametrize(
        "mastery, expected_hint",
        [
            (0.00, HintLevel.H3_LEADING_QUESTION),
            (0.15, HintLevel.H3_LEADING_QUESTION),
            (0.29, HintLevel.H3_LEADING_QUESTION),
            (0.30, HintLevel.H2_POINT_CONCEPT),
            (0.50, HintLevel.H2_POINT_CONCEPT),
            (0.69, HintLevel.H2_POINT_CONCEPT),
        ],
    )
    def test_mastery_band_staircase(self, policy_core, mock_state_tracker, mastery, expected_hint):
        """Проверка ступеней лестницы подсказок в зависимости от уровня мастерства."""
        mock_state_tracker.get_topic_mastery.return_value = mastery
        
        contract = policy_core.compute_contract(
            state_tracker=mock_state_tracker,
            is_attempt=False,
            intent=IntentEnum.CONCEPT_QUESTION
        )
        assert contract.max_hint_level == expected_hint
        assert contract.strict_no_answer is True
        assert contract.is_exam_mode is False

    @pytest.mark.parametrize(
        "mastery, base_hint",
        [
            (0.10, HintLevel.H3_LEADING_QUESTION),
            (0.50, HintLevel.H2_POINT_CONCEPT),
            (0.85, HintLevel.H1_CLARIFY_PROBLEM),
        ],
    )
    def test_constructive_attempt_floor(self, policy_core, mock_state_tracker, mastery, base_hint):
        """
        Rung 2 & 3: Конструктивный пол гарантирует ceiling >= H4_EXPLAIN_IN_WORDS
        при наличии честной попытки студента независимо от текущего мастерства.
        """
        mock_state_tracker.get_topic_mastery.return_value = mastery

        # Проверка через флаг is_attempt
        contract_attempt_flag = policy_core.compute_contract(
            state_tracker=mock_state_tracker,
            is_attempt=True,
            intent=IntentEnum.CONCEPT_QUESTION
        )
        assert contract_attempt_flag.max_hint_level >= HintLevel.H4_EXPLAIN_IN_WORDS

        # Проверка через интент GENUINE_ATTEMPT
        contract_attempt_intent = policy_core.compute_contract(
            state_tracker=mock_state_tracker,
            is_attempt=False,
            intent=IntentEnum.GENUINE_ATTEMPT
        )
        assert contract_attempt_intent.max_hint_level >= HintLevel.H4_EXPLAIN_IN_WORDS

    def test_no_privilege_escalation_on_demand_answer(self, policy_core, mock_state_tracker):
        """Инвариант P4: Прямое требование ответа не должно поднимать потолок подсказки."""
        # Для продвинутого ученика (mastery = 0.5 -> базовый H2)
        mock_state_tracker.get_topic_mastery.return_value = 0.50
        
        contract = policy_core.compute_contract(
            state_tracker=mock_state_tracker,
            is_attempt=False,
            intent=IntentEnum.DEMAND_ANSWER
        )
        assert contract.max_hint_level <= HintLevel.H2_POINT_CONCEPT
        assert contract.strict_no_answer is True

    def test_exam_mode_lockdown_gate_g4(self, policy_core, mock_state_tracker):
        """
        Gate G4: При достижении порога освоения (>= 0.70) без попытки ответа
        включается режим экзамена, блокирующий подсказки выше H0_ENCOURAGE.
        """
        mock_state_tracker.get_topic_mastery.return_value = 0.75
        
        contract = policy_core.compute_contract(
            state_tracker=mock_state_tracker,
            is_attempt=False,
            intent=IntentEnum.CONCEPT_QUESTION
        )
        assert contract.is_exam_mode is True
        assert contract.max_hint_level == HintLevel.H0_ENCOURAGE

    def test_target_topic_override(self, policy_core, mock_state_tracker):
        """Проверка явной маршрутизации на тему, отличную от текущей активной."""
        mock_state_tracker.get_current_topic_id.return_value = "okr_basics"
        
        def mastery_side_effect(topic_id):
            return 0.10 if topic_id == "okr_basics" else 0.60
            
        mock_state_tracker.get_topic_mastery.side_effect = mastery_side_effect

        contract = policy_core.compute_contract(
            state_tracker=mock_state_tracker,
            is_attempt=False,
            intent=IntentEnum.CONCEPT_QUESTION,
            target_topic_id="key_results_rules"
        )
        assert contract.target_topic_id == "key_results_rules"
        assert contract.max_hint_level == HintLevel.H2_POINT_CONCEPT


class TestLearnerStateTrackerMath:
    """Тестирование математики обновления мастерства (P5 - Single Writer)."""

    def test_mastery_clipping_bounds(self):
        """Значение мастерства должно быть строго зажато в диапазоне [0.0, 1.0]."""
        mock_repo = MagicMock()
        mock_session = MagicMock()
        
        # Эмуляция репозитория
        state_store = {"score": 0.10}
        def get_score(sid, tid): return state_store["score"]
        def set_score(sid, tid, val): state_store["score"] = val
        
        mock_repo.get_topic_mastery.side_effect = get_score
        mock_repo.set_topic_mastery.side_effect = set_score

        tracker = LearnerStateTracker(mock_session, "student_test_1")
        tracker.repo = mock_repo

        # 1. Проверка нижней границы: серия ошибок не должна уводить score < 0.0
        for _ in range(5):
            tracker.record_attempt_result("okr_basics", is_successful=False)
        assert state_store["score"] == 0.0

        # 2. Проверка верхней границы: серия успехов не должна превышать 1.0
        for _ in range(10):
            tracker.record_attempt_result("okr_basics", is_successful=True)
        assert state_store["score"] == 1.0

    def test_prerequisite_progression_threshold(self):
        """Переход к следующей теме происходит строго при преодолении порога 0.70."""
        mock_repo = MagicMock()
        mock_session = MagicMock()
        
        scores = {
            "okr_basics": 0.65,
            "objective_rules": 0.0,
            "key_results_rules": 0.0,
            "okr_philosophy_and_kpi": 0.0
        }
        mock_repo.get_topic_mastery.side_effect = lambda sid, tid: scores[tid]

        tracker = LearnerStateTracker(mock_session, "student_test_2")
        tracker.repo = mock_repo

        # При 0.65 активной остается okr_basics
        assert tracker.get_current_topic_id() == "okr_basics"

        # Преодоление порога переключает на objective_rules
        scores["okr_basics"] = 0.70
        assert tracker.get_current_topic_id() == "objective_rules"