from pathlib import Path
from typing import Any, Dict, List, Optional
import traceback
import uuid
import yaml

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from config.config import settings
from src.core.policy_core import PolicyCore
from src.core.security import create_access_token, decode_access_token, hash_password, verify_password
from src.db.database import SessionLocal, init_db
from src.db.models import ChatHistoryModel, TurnTelemetryModel, UserModel
from src.db.repository import ChatHistoryRepository, LearnerStateRepository
from src.knowledge.okr_curriculum import OKR_CURRICULUM
from src.knowledge.retriever import OKRRetriever
from src.llm.factory import LLMFactory
from src.pipeline.actor import Actor
from src.pipeline.detector import DeterministicDetector
from src.pipeline.judge import LLMJudge
from src.pipeline.pipeline import SocraticPipeline
from src.pipeline.pre_classifier import PreClassifier
from src.pipeline.strategist import Strategist
from src.core.learner_state import LearnerStateTracker

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

init_db()

app = FastAPI(
    title="Socratic Tutor API",
    description="REST API для Сократического Диалога по OKR (Pisan, 2026)",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


# --- Зависимости FastAPI ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> UserModel:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация"
        )
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или истекший токен"
        )
    user = db.query(UserModel).filter_by(id=payload["sub"]).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден"
        )
    return user


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[UserModel]:
    """Возвращает объект пользователя при валидном токене, иначе None (гостевой режим)."""
    if not credentials:
        return None
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    return db.query(UserModel).filter_by(id=payload["sub"]).first()


# --- DTO Схемы API ---

class AuthRegisterRequest(BaseModel):
    email: EmailStr
    password: str


class AuthLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


class UserProfileResponse(BaseModel):
    id: str
    email: str


class ChatTurnRequest(BaseModel):
    user_message: str
    session_id: str
    provider: str = "gigachat"


class ChatTurnResponse(BaseModel):
    response: str
    session_id: str
    telemetry: Optional[Dict[str, Any]] = None


# --- Фабрика супервизора ---

def build_pipeline(db: Session, provider: str) -> SocraticPipeline:
    llm_client = LLMFactory.create(provider=provider)
    return SocraticPipeline(
        db_session=db,
        classifier=PreClassifier(llm_client),
        policy_core=PolicyCore(),
        strategist=Strategist(llm_client),
        actor=Actor(llm_client),
        detector=DeterministicDetector(),
        judge=LLMJudge(llm_client),
        retriever=OKRRetriever()
    )


# --- REST Маршруты ---

@app.get("/")
def read_root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/v1/ui/greeting")
def get_ui_greeting():
    """Чтение дефолтного сократического вопроса из config/ui_text.yaml."""
    ui_path = BASE_DIR / "config" / "ui_text.yaml"
    if ui_path.exists():
        try:
            with open(ui_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                greeting = (
                    data.get("initial_assistant_message")
                    or data.get("greeting")
                    or data.get("welcome_message")
                )
                if greeting:
                    return {"greeting": str(greeting).strip()}
        except Exception:
            pass
    return {
        "greeting": "Привет! Я твой персональный сократический наставник по методике OKR. Представь, что твоя команда решила внедрить OKR. Как ты своими словами понимаешь, в чем главное отличие OKR от обычных бизнес-целей или KPI?"
    }


# --- Аутентификация ---

@app.post("/api/v1/auth/register", response_model=AuthResponse)
def register_user(payload: AuthRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(UserModel).filter_by(email=payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже зарегистрирован")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен содержать минимум 6 символов")

    user_id = str(uuid.uuid4())
    user = UserModel(
        id=user_id,
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password)
    )
    db.add(user)
    db.commit()

    token = create_access_token({"sub": user.id, "email": user.email})
    return AuthResponse(access_token=token, user_id=user.id, email=user.email)


@app.post("/api/v1/auth/login", response_model=AuthResponse)
def login_user(payload: AuthLoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter_by(email=payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    token = create_access_token({"sub": user.id, "email": user.email})
    return AuthResponse(access_token=token, user_id=user.id, email=user.email)


@app.get("/api/v1/auth/me", response_model=UserProfileResponse)
def get_current_user_profile(user: UserModel = Depends(get_current_user)):
    return UserProfileResponse(id=user.id, email=user.email)


# --- Диалог и история ---

# server.py

@app.get("/api/v1/chat/history")
def get_chat_history(
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Optional[UserModel] = Depends(get_optional_current_user)
):
    chat_repo = ChatHistoryRepository(db)
    target_session = session_id

    if user:
        # Проверяем, есть ли у переданного session_id сообщения именно этого пользователя
        has_user_session = False
        if target_session:
            has_user_session = db.query(ChatHistoryModel).filter_by(
                session_id=target_session, student_id=user.id
            ).first() is not None

        # Если session_id не был передан или принадлежал гостю — загружаем последнюю сессию пользователя
        if not target_session or not has_user_session:
            latest = chat_repo.get_latest_user_session(user.id)
            if latest:
                target_session = latest
            elif not target_session:
                target_session = str(uuid.uuid4())
    else:
        target_session = session_id or str(uuid.uuid4())

    messages = chat_repo.get_recent_messages(session_id=target_session, limit=40)
    return {
        "session_id": target_session,
        "messages": messages
    }


@app.post("/api/v1/chat/turn", response_model=ChatTurnResponse)
def process_chat_turn(
    payload: ChatTurnRequest,
    db: Session = Depends(get_db),
    user: Optional[UserModel] = Depends(get_optional_current_user)
):
    try:
        student_id = user.id if user else f"guest_{payload.session_id[:16]}"

        pipeline = build_pipeline(db, provider=payload.provider)
        response_text = pipeline.process_turn(
            user_message=payload.user_message,
            session_id=payload.session_id,
            student_id=student_id
        )

        telemetry_data = None
        last_entry = db.query(TurnTelemetryModel).filter_by(
            student_id=student_id
        ).order_by(TurnTelemetryModel.id.desc()).first()

        if last_entry:
            telemetry_data = {
                "detected_intent": last_entry.detected_intent,
                "max_hint_level": last_entry.max_hint_level,
                "strategist_move": last_entry.strategist_move,
                "judge_verdict": last_entry.judge_verdict,
                "judge_reason": last_entry.judge_reason,
                "latency_ms": round(last_entry.latency_ms, 0)
            }

        return ChatTurnResponse(
            response=response_text,
            session_id=payload.session_id,
            telemetry=telemetry_data
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Прогресс по куррикулуму ---

# server.py

@app.get("/api/v1/student/progress")
def get_student_progress(
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Optional[UserModel] = Depends(get_optional_current_user)
):
    if user:
        student_id = user.id
    elif session_id:
        student_id = f"guest_{session_id[:16]}"
    else:
        student_id = "guest_default"

    tracker = LearnerStateTracker(db, student_id)
    return tracker.get_overall_progress()


@app.post("/api/v1/student/reset")
def reset_student(
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Optional[UserModel] = Depends(get_optional_current_user)
):
    student_id = user.id if user else (f"guest_{session_id[:16]}" if session_id else "guest_default")
    
    # 1. Сброс матриц мастерства в learner_states
    learner_repo = LearnerStateRepository(db)
    learner_repo.reset_student_progress(student_id)
    
    # 2. Удаление истории сообщений аккаунта/гостя
    db.query(ChatHistoryModel).filter_by(student_id=student_id).delete()
    # 3. Удаление телеметрии аккаунта/гостя
    db.query(TurnTelemetryModel).filter_by(student_id=student_id).delete()
    db.commit()

    return {"status": "success", "message": "Прогресс и история успешно сброшены"}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)