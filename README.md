# Socratic OKR Tutor: Supervisor Architecture

Интеллектуальная диалоговая система сократического наставничества по методологии OKR (Objectives and Key Results), реализующая супервизорную архитектуру удержания ответа (Answer-Withholding Supervisor Architecture) с машиночитаемыми пошаговыми контрактами.

---

## 1. Теоретический фундамент

Архитектура системы опирается на две работы, дополняющие друг друга: одна даёт теорию диалогической педагогики и стратегии заземления, вторая — инженерную архитектуру супервизора и метод калибровки удержания ответа.

1. **Beale R. (2025).** *Dialogic Pedagogy for Large Language Models: Aligning Conversational AI with Proven Theories of Learning.* University of Birmingham, arXiv:2506.19484 [cs.CY].
   — теоретическая база: диалогическая педагогика, Vygotsky (ZPD и scaffolding), сократический метод, Laurillard conversational framework, tiered Socratic, стратегии RAG-заземления и персона-мотивации.

2. **Pisan Y. (2026).** *Teaching a Large Language Model Tutor to Withhold the Answer: A Supervisor Architecture and an Evidence-Driven Method for Tuning Socratic Behavior.* University of Washington Bothell, arXiv:2608.12292 [cs.CY].
   — архитектурная база: супервизорная модель удержания ответа, разделение ответственности между детерминированными фильтрами и LLM-генерацией, лестница подсказок H0–H7, четыре acceptance gate и метод калибровки «measure → diagnose → fix».

### Проблемы классического взаимодействия с LLM в обучении

Стандартные генеративные модели обладают фундаментальными дефектами при использовании в качестве тьюторов:

1. **Синдром чрезмерной услужливости («Too Helpful» Problem):**
   Языковая модель оптимизирована на максимально быстрое и полное удовлетворение запроса пользователя. При затруднении студента она мгновенно выдаёт готовый ответ. Однако исследования в области когнитивных наук (Bloom, VanLehn, Chi) показывают: готовый ответ — наименее эффективная форма обратной связи, потому что прочное усвоение требует самостоятельной когнитивной сборки решения (constructive engagement, productive struggle).

2. **Метакогнитивная разгрузка (Metacognitive Offloading):**
   Рандомизированное контролируемое исследование Бастани и др. (Bastani et al., 2025) на выборке около 1000 студентов показало: работа с базовым LLM-чатботом без ограничений повышает баллы во время практических занятий, но приводит к падению результатов на последующем самостоятельном экзамене без ассистента. Студент перекладывает планирование и верификацию на модель, создавая иллюзию понимания, но не формируя долговременного навыка.

3. **Отказ при наличии знания (Refusal-Under-Knowledge):**
   Классическая безопасность LLM направлена на отказ от генерации запрещённого контента. Тьютор решает обратную задачу: он знает правильный ответ, студент осознаёт это знание и настойчиво требует ответ («скажи сам», «не хочу думать»), а система обязана удержать сократическую рамку, оставаясь доброжелательной.

4. **Несостоятельность промпт-инжиниринга под давлением:**
   Единый системный промпт не способен одновременно обеспечивать педагогическую теплоту, строгое удержание ответа, заземление на факты и защиту от атак. Под воздействием социальной инженерии («мне разрешил преподаватель», саботаж, прямой шантаж) модель скатывается по «лестнице гипер-помощи» (Over-Help Ladder) — от прямого слива ответа к суфлированию и подсказыванию готовых формулировок.

---

## 2. Шесть принципов супервизора (Supervisor Principles)

Система реализует разделение ответственности между детерминированными и генеративными компонентами:

* **P1. Withhold by default (Удержание по умолчанию):** Тьютор не выдаёт готовые формулировки целей или метрик без системного фиксатора тупика.
* **P2. Decide without reading student text (Принятие решений без чтения текста студента):** Компонент, определяющий потолок помощи на ход (`PolicyCore`), читает исключительно доверенное состояние студента из БД, минимизируя влияние сырого текста ученика на выбор уровня раскрытия.
* **P3. Let deterministic signals outrank model judgments (Детерминированный приоритет):** Регулярные фильтры и шаблоны выполняются до проверок LLM и имеют абсолютный приоритет.
* **P4. Prefer revising a reply over refusing it (Приоритет перегенерации над блокировкой):** Частые отказы («я не могу ответить») раздражают ученика и уводят его в неконтролируемые чатботы. Супервизор отправляет черновик на повторную генерацию с указанием дефекта.
* **P5. Use one writer for learner state (Единая точка записи прогресса):** Только один компонент (`LearnerStateTracker`) обновляет уровень мастерства и счётчики тупиков через типизированные транзакции.
* **P6. Make everything observable (Полная наблюдаемость):** Каждый ход фиксирует телеметрию: назначенный контракт, выбранный педагогический ход, вердикт арбитра, время задержки и источники.

---

## 3. Лестница подсказок (Hint Ladder)

Система квантует помощь на дискретные уровни согласно педагогической модели (Aleven et al.), в соответствии с восьмиуровневой лестницей супервизорной архитектуры:

* **H0 — Acknowledge & Encourage:** Поддержка без смысловых подсказок.
* **H1 — Restate / Clarify:** Перефразирование или уточнение вопроса.
* **H2 — Point Concept:** Указание на ключевое понятие или определение.
* **H3 — Leading Question:** Наводящий вопрос или выбор из двух вариантов (дихотомия).
* **H4 — Explain in Words:** Описание концептуального подхода без готовых формулировок.
* **H5 — Worked Analogy:** Разбор параллельного примера на постороннем кейсе.
* **H6 — Template with Blanks:** Формулировка-шаблон с пропусками.
* **H7 — Full Solution:** Полный прямой ответ.

В текущей реализации OKR-тьютора активно используются уровни **H0–H5**. Уровни **H6** и **H7** зарезервированы архитектурно и в стандартном режиме заблокированы (доступны только через instructor-toggle).

---

## 4. Архитектурный пайплайн диалогового хода (Turn Pipeline)

Обработка каждого сообщения проходит строго детерминированный контур:

```
[ Пользователь ]
       │ (user_message)
       ▼
1. PreClassifier (Intent, IsAttempt, Evaluation)
       │
       ▼
2. LearnerStateTracker (Mastery, Impasse, CoveredConcepts)
       │
       ▼  [ ПЕРИМЕТР P2: сырой текст ученика изолирован ]
3. PolicyCore (PerTurnContract: потолок H0-H5, запреты)
       │
       ▼
4. Strategist (педагогический ход)
       │
       ▼
5. OKRRetriever (RAG: релевантные сниппеты)
       │
       ▼
6. Actor (draft_response)
       │
       ▼
7. DeterministicDetector (P3: утечки, шаблоны, маркеры)
       │ ──[Утечка]──► Регенерация / Fallback
       ▼
8. LLMJudge (Collusion-Resistant, без доступа к user_message)
       │ ──[REVISE]──► Actor.apply_judge_feedback (P4)
       ▼
9. Sanitizer (очистка от мета-фраз и тегов)
       │
       ▼
10. State Update (P5) & Telemetry Logging (P6)
       │
       ▼
[ Ответ студенту ]
```

### Компоненты

1. **`PreClassifier` (`src/pipeline/pre_classifier.py`)** — классифицирует намерение (`attempt`, `help_seeking`, `demand_answer`, `ask_feedback`, `off_topic`, `injection`), оценивает корректность ответа (`correct`, `partially_correct`, `incorrect`, `none`), пресекает эхо-атаки и повторы, отсеивает короткие отписки.

2. **`PolicyCore` (`src/core/policy_core.py`)** — алгоритмический модуль без вызовов нейросетей. На основе прогресса (<30%, <70%, ≥70%) и счётчика тупиков назначает `max_hint_level` и формирует контракт на ход.

3. **`Strategist` (`src/pipeline/strategist.py`)** — задаёт методический ход диалога (ASSERT_AND_QUESTION, ASK_COMPARISON, CHECK_UNDERSTANDING, GIVE_FEEDBACK, ACKNOWLEDGE_AND_REDIRECT и др.). При `rewrite_attempts >= 2` принудительно возвращает ASSERT_AND_QUESTION для выхода из цикла.

4. **`Actor` (`src/pipeline/actor.py`)** — генератор реплики наставника. Лаконичный стиль (2–4 предложения), запрет на лекции, завершение одним содержательным вопросом. Следует выбранному ходу стратега.

5. **`DeterministicDetector` (`src/pipeline/detector.py`)** — регулярными выражениями блокирует суфлирование, цифры в модуле Objective, попытки уклонения от ответа и служебные заголовки. Санитайзер очищает финальный текст от мета-фраз, `[...]`-меток и технических тегов.

6. **`LLMJudge` (`src/pipeline/judge.py`)** — независимый арбитр. Не видит текст студента (устойчив к prompt injection), валидирует черновик по критериям `TOPIC_PARKING_BREACH`, `META_QUESTION`, `META_TALK`, `SPOON_FEEDING`, `NUMBERS_IN_OBJECTIVE`, `FORMAL_VOICE`, `EVASION_OF_ASSERT`, `LOOP_DETECTED`, `FALSE_VALIDATION`.

---

```

## 5. Структура проекта

```text
├── config/
│   ├── config.py             # Настройки окружения (Pydantic Settings)
│   ├── prompts.py            # Загрузчик промптов
│   ├── prompts.yaml          # Шаблоны инструкций суперагентов
│   └── ui_text.yaml          # Тексты интерфейса и приветствие
├── data/
│   ├── curriculum.yaml       # Куррикулум: цели, правила, ключевые концепты
│   └── socratic_prod.db      # Основная база данных SQLite
├── src/
│   ├── core/
│   │   ├── learner_state.py  # Single-writer трекер прогресса и тупиков
│   │   ├── policy_core.py    # Расчёт контракта без чтения пользовательского ввода (P2)
│   │   ├── security.py       # JWT-авторизация и хеширование паролей
│   │   └── types.py          # Доменные структуры данных, Enums и DTO
│   ├── db/
│   │   ├── database.py       # Подключение SQLAlchemy и сессии
│   │   ├── models.py         # ORM-модели (Users, History, Telemetry, States)
│   │   └── repository.py     # Репозитории доступа к данным
│   ├── knowledge/
│   │   ├── okr_curriculum.py # Загрузчик структуры тем OKR
│   │   └── retriever.py      # Модуль поиска релевантного контекста (RAG)
│   ├── llm/
│   │   ├── base.py           # Базовый интерфейс LLM-клиента
│   │   ├── factory.py        # Фабрика провайдеров (GigaChat, Ollama, OpenAI)
│   │   └── gigachat_client.py# Клиент API Сбер GigaChat с сокетными таймаутами
│   ├── pipeline/
│   │   ├── actor.py          # Актор диалога (Тьютор)
│   │   ├── detector.py       # Детерминированный анализатор утечек (P3)
│   │   ├── judge.py          # Изолированный LLM-арбитр рискованных ходов
│   │   ├── pipeline.py       # Главный оркестратор супервизора
│   │   ├── pre_classifier.py # Семантический анализатор входящего ввода
│   │   └── strategist.py     # Педагогический диспетчер
│   └── utils/
│       └── logger.py         # Структурированное логирование
├── static/                   # SPA-интерфейс (HTML, CSS, JS)
├── tests/                    # Модульные и интеграционные тесты
├── requirements.txt          # Зависимости проекта
└── server.py                 # FastAPI приложение и REST API эндпоинты
```

---

## 6. Установка и запуск

### Требования

* Python 3.10+
* Доступ к GigaChat API (клиентский идентификатор и секрет) или локальный экземпляр Ollama.

### 1. Клонирование и настройка окружения

```bash
git clone <repository_url>
cd Socratic-Tutor-Project

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Переменные окружения

Создайте файл `.env` в корне проекта:

```bash
cp .env.example .env
```

Заполните ключи:

```ini
GIGACHAT_CREDENTIALS="ваш_авторизационный_токен_base64"
GIGACHAT_SCOPE="GIGACHAT_API_PERS"
GIGACHAT_MODEL="GigaChat"
JWT_SECRET_KEY="сгенерированный_секретный_ключ_для_токенов"
DATABASE_URL="sqlite:///./data/socratic_prod.db"
```

### 3. Запуск сервера

```bash
python server.py
```

Веб-интерфейс: `http://localhost:8000`
Swagger/OpenAPI: `http://localhost:8000/docs`

---

## 7. Запуск тестов

Прогон детерминированных тестов инвариантов и детектора:

```bash
pytest tests/ -v
```

---

## 8. Теоретические ссылки

1. Beale, R. (2025). *Dialogic Pedagogy for Large Language Models: Aligning Conversational AI with Proven Theories of Learning.* University of Birmingham. arXiv:2506.19484 [cs.CY].

2. Pisan, Y. (2026). *Teaching a Large Language Model Tutor to Withhold the Answer: A Supervisor Architecture and an Evidence-Driven Method for Tuning Socratic Behavior.* University of Washington Bothell. arXiv:2608.12292 [cs.CY].