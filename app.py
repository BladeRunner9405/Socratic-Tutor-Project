import streamlit as st
import uuid
from sqlalchemy.orm import Session

from config.config import settings
from src.db.database import init_db, SessionLocal
from src.db.repository import LearnerStateRepository
from src.db.models import TurnTelemetryModel
from src.llm.factory import LLMFactory
from src.knowledge.retriever import OKRRetriever
from src.knowledge.okr_curriculum import OKR_CURRICULUM
from src.core.policy_core import PolicyCore

from src.pipeline.pre_classifier import PreClassifier
from src.pipeline.strategist import Strategist
from src.pipeline.actor import Actor
from src.pipeline.detector import DeterministicDetector
from src.pipeline.judge import LLMJudge
from src.pipeline.pipeline import SocraticPipeline


# Инициализация базы данных
init_db()

st.set_page_config(
    page_title="Сократический Тьютор по OKR",
    page_icon="🎓",
    layout="wide"
)

# Инициализация переменных сессии
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "student_id" not in st.session_state:
    st.session_state.student_id = "student_demo_01"
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Привет! Я твой персональный сократический наставник по методике OKR. "
                       "Представь, что твоя команда решила внедрить OKR. Как ты своими словами понимаешь, "
                       "в чем главное отличие OKR от обычных бизнес-целей или KPI?"
        }
    ]
if "last_telemetry" not in st.session_state:
    st.session_state.last_telemetry = None


def get_pipeline(db_session: Session, provider: str) -> SocraticPipeline:
    llm_client = LLMFactory.create(provider=provider)
    
    classifier = PreClassifier(llm_client)
    policy_core = PolicyCore()
    strategist = Strategist(llm_client)
    actor = Actor(llm_client)
    detector = DeterministicDetector()
    judge = LLMJudge(llm_client)
    retriever = OKRRetriever()

    return SocraticPipeline(
        db_session=db_session,
        classifier=classifier,
        policy_core=policy_core,
        strategist=strategist,
        actor=actor,
        detector=detector,
        judge=judge,
        retriever=retriever
    )


# ---------------------------------------------------------
# БОКОВАЯ ПАНЕЛЬ (SIDEBAR)
# ---------------------------------------------------------
with st.sidebar:
    st.title("🎓 Панель Тьютора (Supervisor UI)")
    
    # 1. Смена / Идентификация ученика
    student_id_input = st.text_input("ID Ученика:", value=st.session_state.student_id)
    if student_id_input != st.session_state.student_id:
        st.session_state.student_id = student_id_input
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = [st.session_state.messages[0]]
        st.session_state.last_telemetry = None
        st.rerun()

    # 2. Кнопки управления
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧹 Новая сессия"):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = [st.session_state.messages[0]]
            st.session_state.last_telemetry = None
            st.rerun()
            
    with col2:
        if st.button("❌ Сбросить прогресс"):
            db = SessionLocal()
            try:
                repo = LearnerStateRepository(db)
                repo.reset_student_progress(st.session_state.student_id)
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.messages = [st.session_state.messages[0]]
                st.session_state.last_telemetry = None
                st.success("Прогресс сброшен!")
                st.rerun()
            finally:
                db.close()
                
    st.caption("Визуализация работы сократического конвейера (Pisan, 2026)")
    
    provider = st.selectbox(
        "Выберите LLM-провайдер:",
        options=["ollama", "gigachat", "openai"],
        index=0,
        help="Вы можете переключаться между Ollama и GigaChat API"
    )
    
    if st.button("🔄 Начать диалог заново", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = [st.session_state.messages[0]]
        st.session_state.last_telemetry = None
        st.rerun()

    st.divider()

    st.subheader("📊 Прогресс освоения OKR")
    db = SessionLocal()
    try:
        state_repo = LearnerStateRepository(db)
        for topic_id, topic in OKR_CURRICULUM.items():
            score = state_repo.get_topic_mastery(st.session_state.student_id, topic_id)
            st.write(f"**{topic.title}**")
            st.progress(score, text=f"{int(score * 100)}%")
    finally:
        db.close()

    st.divider()

    st.subheader("🔍 Анализ последнего хода")
    telemetry = st.session_state.last_telemetry

    if telemetry:
        st.info(f"**Распознанный интент:** `{getattr(telemetry, 'detected_intent', 'N/A')}`")
        st.warning(f"**Потолок подсказки (Contract):** H{getattr(telemetry, 'max_hint_level', 'N/A')}")
        st.success(f"**Педагогический ход:** `{getattr(telemetry, 'strategist_move', 'N/A')}`")
        
        verdict = getattr(telemetry, 'judge_verdict', None)
        if verdict:
            st.write(f"**Вердикт Судьи:** `{str(verdict).upper()}`")
            st.caption(f"Причина: {getattr(telemetry, 'judge_reason', 'N/A')}")
        else:
            st.caption("Вердикт Судьи: Проверка не потребовалась")
            
        latency = getattr(telemetry, 'latency_ms', 0.0)
        st.caption(f"⏱️ Задержка ответа: {latency:.0f} мс")
    else:
        st.caption("Ожидание первого ответа пользователя...")


# ---------------------------------------------------------
# ОСНОВНАЯ ОБЛАСТЬ ЧАТА
# ---------------------------------------------------------
st.title("💬 Сократический Диалог по OKR")
st.markdown(
    "Этот тьютор **не выдает готовых ответов**, а помогает освоить методологию OKR "
    "через рассуждения и наводящие вопросы."
)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

if user_input := st.chat_input("Напишите ваш ответ или вопрос по OKR..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Тьютор размышляет над вашим ответом..."):
            db = SessionLocal()
            try:
                pipeline = get_pipeline(db, provider=provider)
                
                response_text = pipeline.process_turn(
                    user_message=user_input,
                    session_id=st.session_state.session_id,
                    student_id=st.session_state.student_id
                )
                
                # Получение последней записи телеметрии из БД
                last_db_entry = db.query(TurnTelemetryModel).order_by(TurnTelemetryModel.id.desc()).first()
                if last_db_entry:
                    st.session_state.last_telemetry = last_db_entry
                
                st.write(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
                
            except Exception as e:
                st.error(f"Ошибка выполнения: {str(e)}")
            finally:
                db.close()

    # Перерисовываем интерфейс для обновления данных в Sidebar
    st.rerun()