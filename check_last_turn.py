# dump_last_turn.py
import json
import sqlite3

conn = sqlite3.connect("okr_tutor.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Получаем все таблицы в базе
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
tables = [row["name"] for row in cursor.fetchall()]
print(f"Таблицы в базе: {tables}\n")

# Ищем таблицу телеметрии или истории
target_table = None
for candidate in ["turn_telemetry", "telemetries", "telemetry_logs", "logs", "chat_history"]:
    if candidate in tables:
        target_table = candidate
        break

if not target_table and tables:
    target_table = tables[0]

if target_table:
    print(f"=== ПОСЛЕДНЯЯ ЗАПИСЬ ИЗ ТАБЛИЦЫ '{target_table}' ===")
    cursor.execute(f"SELECT * FROM {target_table} ORDER BY rowid DESC LIMIT 1;")
    row = cursor.fetchone()
    if row:
        for key in row.keys():
            val = row[key]
            # Пытаемся красиво распечатать JSON, если поле содержит сериализованный объект
            try:
                parsed = json.loads(val)
                print(f"\n[{key}]:\n{json.dumps(parsed, ensure_ascii=False, indent=2)}")
            except Exception:
                print(f"[{key}]: {val}")
    else:
        print("Таблица пуста.")
else:
    print("В базе данных нет таблиц.")

conn.close()