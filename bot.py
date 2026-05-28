"""
╔══════════════════════════════════════════════════════════════╗
║          BioChemBot — Бот для тестирования учеников          ║
║          Биология и Химия | Учитель + Ученики                ║
╚══════════════════════════════════════════════════════════════╝

Установка:
    pip install pyTelegramBotAPI

Запуск:
    1. Замените TOKEN на ваш токен от @BotFather
    2. Замените TEACHER_ID на ваш Telegram ID (узнать: @userinfobot)
    3. python bot.py
"""

import telebot
from telebot import types
import json
import os
import datetime
import random
import time
from collections import defaultdict

# ─── НАСТРОЙКИ ────────────────────────────────────────────────────────────────
TOKEN = "8916131771:AAHQy8Z2uHvfbBS2pyKGA3ufLnhX_EAgsZg"          # Токен от @BotFather
TEACHER_ID = 1381276020              # Ваш Telegram ID (узнать: @userinfobot)
DATA_FILE = "quiz_data.json"
# ──────────────────────────────────────────────────────────────────────────────

bot = telebot.TeleBot(TOKEN)

# ─── УРОВНИ СЛОЖНОСТИ ─────────────────────────────────────────────────────────
LEVELS = {
    "easy":   "🟢 Лёгкий",
    "medium": "🟡 Средний",
    "hard":   "🔴 Сложный"
}

SUBJECTS = {
    "bio": "🌿 Биология",
    "chem": "⚗️ Химия",
    "both": "📚 Оба предмета"
}

CLASSES = [str(i) for i in range(5, 12)]  # 5–11 классы

# ─── ХРАНИЛИЩЕ ДАННЫХ ─────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "quizzes": {},       # id -> quiz object
        "results": {},       # user_id -> [result, ...]
        "users": {},         # user_id -> {name, class, role}
        "sessions": {}       # user_id -> current session
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ──────────────────────────────────────────────────
def is_teacher(user_id):
    return user_id == TEACHER_ID

def get_user(user_id):
    return data["users"].get(str(user_id), {})

def get_session(user_id):
    return data["sessions"].get(str(user_id), {})

def set_session(user_id, session):
    data["sessions"][str(user_id)] = session
    save_data(data)

def clear_session(user_id):
    data["sessions"].pop(str(user_id), None)
    save_data(data)

def gen_quiz_id():
    import uuid
    return str(uuid.uuid4())[:8].upper()

def score_grade(percent):
    if percent >= 90: return "⭐️⭐️⭐️ Отлично"
    elif percent >= 75: return "⭐️⭐️ Хорошо"
    elif percent >= 50: return "⭐️ Удовлетворительно"
    else: return "❌ Неудовлетворительно"

def format_quiz_info(quiz, detailed=False):
    subject_name = SUBJECTS.get(quiz.get("subject", "both"), "📚 Оба предмета")
    level_name   = LEVELS.get(quiz.get("level", "medium"), "🟡 Средний")
    q_count      = len(quiz.get("questions", []))
    lines = [
        f"📋 *{quiz['title']}*",
        f"🆔 Код: `{quiz['id']}`",
        f"📖 Предмет: {subject_name}",
        f"🏫 Класс: {quiz.get('class_grade', '—')} класс",
        f"📊 Уровень: {level_name}",
        f"❓ Вопросов: {q_count}",
        f"⏱ Время: {quiz.get('time_limit', 0)} мин" if quiz.get('time_limit') else "⏱ Без ограничения",
        f"📅 Создан: {quiz.get('created_at', '—')}",
    ]
    if detailed and quiz.get("description"):
        lines.append(f"📝 Описание: {quiz['description']}")
    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════════════════════
#  РЕГИСТРАЦИЯ И СТАРТ
# ══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = str(message.from_user.id)
    if is_teacher(message.from_user.id):
        send_teacher_menu(message)
        return

    if uid not in data["users"] or not data["users"][uid].get("class_grade"):
        bot.send_message(message.chat.id,
            "👋 Добро пожаловать в *BioChemBot*!\n\n"
            "Здесь вы можете проходить тесты по 🌿 биологии и ⚗️ химии.\n\n"
            "Для начала, укажи свой *класс*:",
            parse_mode="Markdown",
            reply_markup=class_keyboard()
        )
        set_session(message.from_user.id, {"state": "reg_class"})
    else:
        send_student_menu(message)

@bot.message_handler(commands=["menu"])
def cmd_menu(message):
    if is_teacher(message.from_user.id):
        send_teacher_menu(message)
    else:
        send_student_menu(message)

# ─── КЛАВИАТУРЫ ───────────────────────────────────────────────────────────────
def class_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=4)
    kb.add(*[types.KeyboardButton(f"{c} класс") for c in CLASSES])
    return kb

def teacher_main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("➕ Создать тест"),
        types.KeyboardButton("📋 Мои тесты"),
        types.KeyboardButton("📊 Результаты"),
        types.KeyboardButton("🔍 Найти тест"),
        types.KeyboardButton("🗑 Удалить тест"),
        types.KeyboardButton("📈 Статистика"),
    )
    return kb

def student_main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("🎯 Пройти тест"),
        types.KeyboardButton("📊 Мои результаты"),
        types.KeyboardButton("🏆 Рейтинг"),
        types.KeyboardButton("ℹ️ Мой профиль"),
    )
    return kb

def subject_inline_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    for key, val in SUBJECTS.items():
        if key != "both":
            kb.add(types.InlineKeyboardButton(val, callback_data=f"subj_{key}"))
    return kb

def level_inline_kb():
    kb = types.InlineKeyboardMarkup(row_width=3)
    for key, val in LEVELS.items():
        kb.add(types.InlineKeyboardButton(val, callback_data=f"lvl_{key}"))
    return kb

def class_inline_kb():
    kb = types.InlineKeyboardMarkup(row_width=4)
    for c in CLASSES:
        kb.add(types.InlineKeyboardButton(f"{c} кл.", callback_data=f"cls_{c}"))
    return kb

# ══════════════════════════════════════════════════════════════════════════════
#  МЕНЮ УЧИТЕЛЯ
# ══════════════════════════════════════════════════════════════════════════════

def send_teacher_menu(message):
    bot.send_message(message.chat.id,
        "👨‍🏫 *Панель учителя*\n\n"
        "Добро пожаловать! Выберите действие:",
        parse_mode="Markdown",
        reply_markup=teacher_main_kb()
    )

@bot.message_handler(func=lambda m: is_teacher(m.from_user.id) and m.text == "➕ Создать тест")
def teacher_create_quiz(message):
    set_session(message.from_user.id, {"state": "create_title"})
    bot.send_message(message.chat.id,
        "📝 *Создание нового теста*\n\n"
        "Шаг 1/6 — Введите *название* теста:",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda m: is_teacher(m.from_user.id) and m.text == "📋 Мои тесты")
def teacher_my_quizzes(message):
    quizzes = [q for q in data["quizzes"].values() if q.get("teacher_id") == message.from_user.id]
    if not quizzes:
        bot.send_message(message.chat.id, "У вас пока нет тестов. Создайте первый! ➕", reply_markup=teacher_main_kb())
        return
    text = f"📋 *Ваши тесты* ({len(quizzes)} шт.)\n\n"
    for q in quizzes:
        attempts = sum(1 for uid, results in data["results"].items()
                       for r in results if r["quiz_id"] == q["id"])
        text += format_quiz_info(q) + f"\n👥 Попыток: {attempts}\n\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=teacher_main_kb())

@bot.message_handler(func=lambda m: is_teacher(m.from_user.id) and m.text == "📊 Результаты")
def teacher_results(message):
    quizzes = [q for q in data["quizzes"].values() if q.get("teacher_id") == message.from_user.id]
    if not quizzes:
        bot.send_message(message.chat.id, "Нет тестов.", reply_markup=teacher_main_kb())
        return
    kb = types.InlineKeyboardMarkup()
    for q in quizzes:
        kb.add(types.InlineKeyboardButton(f"📋 {q['title']}", callback_data=f"res_{q['id']}"))
    bot.send_message(message.chat.id, "Выберите тест для просмотра результатов:", reply_markup=kb)

@bot.message_handler(func=lambda m: is_teacher(m.from_user.id) and m.text == "📈 Статистика")
def teacher_stats(message):
    quizzes = [q for q in data["quizzes"].values() if q.get("teacher_id") == message.from_user.id]
    total_attempts = 0
    total_score = 0
    count_scored = 0
    subject_counts = defaultdict(int)
    level_counts = defaultdict(int)

    for q in quizzes:
        subject_counts[q.get("subject", "both")] += 1
        level_counts[q.get("level", "medium")] += 1
        for uid, results in data["results"].items():
            for r in results:
                if r["quiz_id"] == q["id"]:
                    total_attempts += 1
                    total_score += r.get("percent", 0)
                    count_scored += 1

    avg = round(total_score / count_scored, 1) if count_scored else 0
    text = (
        f"📈 *Общая статистика*\n\n"
        f"📋 Тестов создано: {len(quizzes)}\n"
        f"👥 Всего попыток: {total_attempts}\n"
        f"📊 Средний балл: {avg}%\n\n"
        f"📖 По предметам:\n"
    )
    for s, cnt in subject_counts.items():
        text += f"  {SUBJECTS.get(s, s)}: {cnt} тест(ов)\n"
    text += "\n📊 По уровням:\n"
    for l, cnt in level_counts.items():
        text += f"  {LEVELS.get(l, l)}: {cnt} тест(ов)\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=teacher_main_kb())

@bot.message_handler(func=lambda m: is_teacher(m.from_user.id) and m.text == "🔍 Найти тест")
def teacher_search(message):
    set_session(message.from_user.id, {"state": "teacher_search"})
    bot.send_message(message.chat.id, "Введите код теста или ключевое слово из названия:",
                     reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: is_teacher(m.from_user.id) and m.text == "🗑 Удалить тест")
def teacher_delete(message):
    quizzes = [q for q in data["quizzes"].values() if q.get("teacher_id") == message.from_user.id]
    if not quizzes:
        bot.send_message(message.chat.id, "Нет тестов для удаления.", reply_markup=teacher_main_kb())
        return
    kb = types.InlineKeyboardMarkup()
    for q in quizzes:
        kb.add(types.InlineKeyboardButton(f"🗑 {q['title']}", callback_data=f"del_{q['id']}"))
    bot.send_message(message.chat.id, "Выберите тест для удаления:", reply_markup=kb)

# ══════════════════════════════════════════════════════════════════════════════
#  СОЗДАНИЕ ТЕСТА (FSM для учителя)
# ══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(func=lambda m: is_teacher(m.from_user.id) and
                     get_session(m.from_user.id).get("state") == "create_title")
def create_title(message):
    session = get_session(message.from_user.id)
    session["title"] = message.text.strip()
    session["state"] = "create_description"
    set_session(message.from_user.id, session)
    bot.send_message(message.chat.id,
        f"✅ Название: *{message.text.strip()}*\n\n"
        "Шаг 2/6 — Введите *описание* теста (или напишите `-` чтобы пропустить):",
        parse_mode="Markdown")

@bot.message_handler(func=lambda m: is_teacher(m.from_user.id) and
                     get_session(m.from_user.id).get("state") == "create_description")
def create_description(message):
    session = get_session(message.from_user.id)
    session["description"] = "" if message.text.strip() == "-" else message.text.strip()
    session["state"] = "create_subject"
    set_session(message.from_user.id, session)
    bot.send_message(message.chat.id,
        "Шаг 3/6 — Выберите *предмет*:",
        parse_mode="Markdown",
        reply_markup=subject_inline_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("subj_"))
def create_subject(call):
    session = get_session(call.from_user.id)
    if session.get("state") != "create_subject":
        return
    session["subject"] = call.data.split("_")[1]
    session["state"] = "create_class"
    set_session(call.from_user.id, session)
    bot.edit_message_text(
        f"✅ Предмет: {SUBJECTS[session['subject']]}\n\nШаг 4/6 — Выберите *класс*:",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown",
        reply_markup=class_inline_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("cls_"))
def create_class(call):
    session = get_session(call.from_user.id)
    if session.get("state") != "create_class":
        return
    session["class_grade"] = call.data.split("_")[1]
    session["state"] = "create_level"
    set_session(call.from_user.id, session)
    bot.edit_message_text(
        f"✅ Класс: {session['class_grade']}\n\nШаг 5/6 — Выберите *уровень сложности*:",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown",
        reply_markup=level_inline_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("lvl_"))
def create_level(call):
    session = get_session(call.from_user.id)
    if session.get("state") != "create_level":
        return
    session["level"] = call.data.split("_")[1]
    session["state"] = "create_time"
    set_session(call.from_user.id, session)
    bot.edit_message_text(
        f"✅ Уровень: {LEVELS[session['level']]}\n\n"
        "Шаг 6/6 — Введите *лимит времени* (в минутах, или `0` — без ограничения):",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown")

@bot.message_handler(func=lambda m: is_teacher(m.from_user.id) and
                     get_session(m.from_user.id).get("state") == "create_time")
def create_time(message):
    try:
        t = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, "Введите число (минуты). Например: 20")
        return
    session = get_session(message.from_user.id)
    session["time_limit"] = t
    session["state"] = "add_question"
    session["questions"] = []
    session["q_step"] = "question"
    set_session(message.from_user.id, session)
    bot.send_message(message.chat.id,
        "✅ *Настройки теста сохранены!*\n\n"
        "Теперь добавьте вопросы.\n\n"
        "📝 Введите текст *первого вопроса*:",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove())

# ─── ДОБАВЛЕНИЕ ВОПРОСОВ ──────────────────────────────────────────────────────

@bot.message_handler(func=lambda m: is_teacher(m.from_user.id) and
                     get_session(m.from_user.id).get("state") == "add_question")
def add_question_step(message):
    session = get_session(message.from_user.id)
    q_step = session.get("q_step", "question")
    current_q = session.get("current_q", {})

    if q_step == "question":
        session["current_q"] = {"text": message.text.strip(), "options": [], "correct": None}
        session["q_step"] = "opt_a"
        set_session(message.from_user.id, session)
        bot.send_message(message.chat.id, "🅰️ Введите вариант ответа *А*:", parse_mode="Markdown")

    elif q_step in ["opt_a", "opt_b", "opt_c", "opt_d"]:
        opt_map = {"opt_a": "A", "opt_b": "B", "opt_c": "C", "opt_d": "D"}
        next_map = {"opt_a": "opt_b", "opt_b": "opt_c", "opt_c": "opt_d", "opt_d": "correct"}
        letter_map = {"opt_a": "Б", "opt_b": "В", "opt_c": "Г", "opt_d": None}

        session["current_q"]["options"].append({"letter": opt_map[q_step], "text": message.text.strip()})
        session["q_step"] = next_map[q_step]
        set_session(message.from_user.id, session)

        if next_map[q_step] == "correct":
            opts = session["current_q"]["options"]
            opts_text = "\n".join([f"  {o['letter']}) {o['text']}" for o in opts])
            kb = types.InlineKeyboardMarkup(row_width=4)
            kb.add(*[types.InlineKeyboardButton(o["letter"], callback_data=f"correct_{o['letter']}") for o in opts])
            bot.send_message(message.chat.id,
                f"❓ *{session['current_q']['text']}*\n{opts_text}\n\nКакой ответ *правильный*?",
                parse_mode="Markdown", reply_markup=kb)
        else:
            next_letter = letter_map[q_step]
            bot.send_message(message.chat.id, f"🅱️ Введите вариант *{next_letter}*:", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("correct_"))
def set_correct_answer(call):
    session = get_session(call.from_user.id)
    if session.get("state") != "add_question" or session.get("q_step") != "correct":
        return
    letter = call.data.split("_")[1]
    session["current_q"]["correct"] = letter
    session["questions"].append(session["current_q"])
    q_num = len(session["questions"])
    session["current_q"] = {}
    set_session(call.from_user.id, session)

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ Добавить вопрос", callback_data="quiz_add_more"),
        types.InlineKeyboardButton("✅ Завершить тест", callback_data="quiz_finish")
    )
    bot.edit_message_text(
        f"✅ Вопрос {q_num} добавлен! Правильный ответ: *{letter}*\n\nЧто дальше?",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "quiz_add_more")
def quiz_add_more(call):
    session = get_session(call.from_user.id)
    session["q_step"] = "question"
    set_session(call.from_user.id, session)
    q_num = len(session["questions"]) + 1
    bot.edit_message_text(
        f"📝 Введите текст *вопроса {q_num}*:",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "quiz_finish")
def quiz_finish(call):
    session = get_session(call.from_user.id)
    if len(session.get("questions", [])) == 0:
        bot.answer_callback_query(call.id, "Добавьте хотя бы один вопрос!")
        return

    quiz_id = gen_quiz_id()
    quiz = {
        "id": quiz_id,
        "teacher_id": call.from_user.id,
        "title": session["title"],
        "description": session.get("description", ""),
        "subject": session.get("subject", "bio"),
        "class_grade": session.get("class_grade", "—"),
        "level": session.get("level", "medium"),
        "time_limit": session.get("time_limit", 0),
        "questions": session["questions"],
        "created_at": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "active": True
    }
    data["quizzes"][quiz_id] = quiz
    save_data(data)
    clear_session(call.from_user.id)

    bot.edit_message_text(
        f"🎉 *Тест успешно создан!*\n\n"
        f"{format_quiz_info(quiz, detailed=True)}\n\n"
        f"📤 Поделитесь кодом с учениками: `{quiz_id}`",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown")
    bot.send_message(call.message.chat.id, "Выберите действие:", reply_markup=teacher_main_kb())

# ══════════════════════════════════════════════════════════════════════════════
#  ПРОСМОТР РЕЗУЛЬТАТОВ (учитель)
# ══════════════════════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda c: c.data.startswith("res_"))
def view_quiz_results(call):
    quiz_id = call.data[4:]
    quiz = data["quizzes"].get(quiz_id)
    if not quiz:
        bot.answer_callback_query(call.id, "Тест не найден")
        return

    results = []
    for uid, user_results in data["results"].items():
        for r in user_results:
            if r["quiz_id"] == quiz_id:
                user = data["users"].get(uid, {})
                results.append({**r, "user": user, "uid": uid})

    if not results:
        bot.edit_message_text(f"📊 *{quiz['title']}*\n\nРезультатов пока нет.",
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        return

    results.sort(key=lambda x: x.get("percent", 0), reverse=True)
    text = f"📊 *Результаты: {quiz['title']}*\n"
    text += f"👥 Всего попыток: {len(results)}\n"
    avg = round(sum(r.get("percent", 0) for r in results) / len(results), 1)
    text += f"📈 Средний балл: {avg}%\n\n"
    text += "─" * 30 + "\n"
    for i, r in enumerate(results, 1):
        name = r["user"].get("name", "Неизвестный")
        cls  = r["user"].get("class_grade", "?")
        pct  = r.get("percent", 0)
        correct = r.get("correct", 0)
        total   = r.get("total", 0)
        date    = r.get("date", "—")
        grade   = score_grade(pct)
        text += f"{i}. *{name}* ({cls} кл.)\n   ✅ {correct}/{total} ({pct}%) — {grade}\n   📅 {date}\n\n"

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def delete_quiz_confirm(call):
    quiz_id = call.data[4:]
    quiz = data["quizzes"].get(quiz_id)
    if not quiz:
        bot.answer_callback_query(call.id, "Тест не найден")
        return
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"delconfirm_{quiz_id}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="delcancel")
    )
    bot.edit_message_text(
        f"❗️ Вы уверены, что хотите удалить тест *{quiz['title']}*?\nВсе результаты будут сохранены.",
        call.message.chat.id, call.message.message_id,
        parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("delconfirm_"))
def delete_quiz(call):
    quiz_id = call.data[11:]
    if quiz_id in data["quizzes"]:
        del data["quizzes"][quiz_id]
        save_data(data)
    bot.edit_message_text("✅ Тест удалён.", call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "Выберите действие:", reply_markup=teacher_main_kb())

@bot.callback_query_handler(func=lambda c: c.data == "delcancel")
def delete_cancel(call):
    bot.edit_message_text("Отмена удаления.", call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "Выберите действие:", reply_markup=teacher_main_kb())

# ══════════════════════════════════════════════════════════════════════════════
#  РЕГИСТРАЦИЯ УЧЕНИКА
# ══════════════════════════════════════════════════════════════════════════════

@bot.message_handler(func=lambda m: not is_teacher(m.from_user.id) and
                     get_session(m.from_user.id).get("state") == "reg_class" and
                     any(m.text == f"{c} класс" for c in CLASSES))
def reg_class(message):
    class_grade = message.text.replace(" класс", "")
    session = get_session(message.from_user.id)
    session["class_grade"] = class_grade
    session["state"] = "reg_name"
    set_session(message.from_user.id, session)
    bot.send_message(message.chat.id,
        f"✅ Класс {class_grade} выбран!\n\nВведите ваше *имя и фамилию*:",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: not is_teacher(m.from_user.id) and
                     get_session(m.from_user.id).get("state") == "reg_name")
def reg_name(message):
    session = get_session(message.from_user.id)
    uid = str(message.from_user.id)
    data["users"][uid] = {
        "name": message.text.strip(),
        "class_grade": session["class_grade"],
        "registered_at": datetime.datetime.now().strftime("%d.%m.%Y")
    }
    save_data(data)
    clear_session(message.from_user.id)
    bot.send_message(message.chat.id,
        f"🎉 *Отлично, {message.text.strip()}!*\n"
        f"Вы зарегистрированы как ученик {session['class_grade']} класса.\n\n"
        "Теперь вы можете проходить тесты!",
        parse_mode="Markdown",
        reply_markup=student_main_kb())

# ══════════════════════════════════════════════════════════════════════════════
#  МЕНЮ УЧЕНИКА
# ══════════════════════════════════════════════════════════════════════════════

def send_student_menu(message):
    user = get_user(message.from_user.id)
    name = user.get("name", message.from_user.first_name)
    bot.send_message(message.chat.id,
        f"👋 Привет, *{name}*! Что хотите сделать?",
        parse_mode="Markdown",
        reply_markup=student_main_kb())

@bot.message_handler(func=lambda m: not is_teacher(m.from_user.id) and m.text == "🎯 Пройти тест")
def student_take_quiz(message):
    set_session(message.from_user.id, {"state": "enter_quiz_code"})
    bot.send_message(message.chat.id,
        "📨 Введите *код теста*, который вам дал учитель:",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda m: not is_teacher(m.from_user.id) and
                     get_session(m.from_user.id).get("state") == "enter_quiz_code")
def enter_quiz_code(message):
    code = message.text.strip().upper()
    quiz = data["quizzes"].get(code)
    if not quiz:
        bot.send_message(message.chat.id,
            "❌ Тест с таким кодом не найден. Проверьте код и попробуйте снова.")
        return
    if not quiz.get("active", True):
        bot.send_message(message.chat.id, "⛔️ Этот тест деактивирован учителем.")
        clear_session(message.from_user.id)
        return

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("▶️ Начать тест", callback_data=f"start_{code}"))
    bot.send_message(message.chat.id,
        f"📋 *Найден тест!*\n\n{format_quiz_info(quiz, detailed=True)}\n\n"
        "Готовы начать?",
        parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("start_"))
def start_quiz(call):
    quiz_id = call.data[6:]
    quiz = data["quizzes"].get(quiz_id)
    if not quiz:
        bot.answer_callback_query(call.id, "Тест не найден")
        return

    questions = quiz["questions"].copy()
    random.shuffle(questions)  # Перемешать вопросы

    session = {
        "state": "in_quiz",
        "quiz_id": quiz_id,
        "questions": questions,
        "current_q": 0,
        "correct": 0,
        "answers": [],
        "start_time": time.time()
    }
    set_session(call.from_user.id, session)
    bot.edit_message_text("✅ Тест начат! Удачи!", call.message.chat.id, call.message.message_id)
    send_question(call.from_user.id, call.message.chat.id, session)

def send_question(user_id, chat_id, session):
    q_idx = session["current_q"]
    questions = session["questions"]
    if q_idx >= len(questions):
        finish_quiz(user_id, chat_id)
        return
    q = questions[q_idx]
    total = len(questions)
    kb = types.InlineKeyboardMarkup(row_width=2)
    for opt in q["options"]:
        kb.add(types.InlineKeyboardButton(
            f"{opt['letter']}) {opt['text']}",
            callback_data=f"ans_{opt['letter']}"
        ))
    bot.send_message(chat_id,
        f"❓ *Вопрос {q_idx+1}/{total}*\n\n{q['text']}",
        parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ans_") and
                             get_session(c.from_user.id).get("state") == "in_quiz")
def answer_question(call):
    session = get_session(call.from_user.id)
    q_idx = session["current_q"]
    questions = session["questions"]
    q = questions[q_idx]
    chosen = call.data[4:]
    correct = q["correct"]
    is_correct = (chosen == correct)
    if is_correct:
        session["correct"] += 1
        feedback = f"✅ *Правильно!*"
    else:
        correct_text = next((o["text"] for o in q["options"] if o["letter"] == correct), correct)
        feedback = f"❌ *Неверно.* Правильный ответ: *{correct})* {correct_text}"
    session["answers"].append({"q": q["text"], "chosen": chosen, "correct": correct, "ok": is_correct})
    session["current_q"] += 1
    set_session(call.from_user.id, session)
    bot.edit_message_text(feedback, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    time.sleep(0.5)
    send_question(call.from_user.id, call.message.chat.id, session)

def finish_quiz(user_id, chat_id):
    session = get_session(user_id)
    quiz_id = session["quiz_id"]
    quiz = data["quizzes"].get(quiz_id, {})
    total = len(session["questions"])
    correct = session["correct"]
    percent = round((correct / total) * 100) if total else 0
    elapsed = round((time.time() - session.get("start_time", time.time())) / 60, 1)
    grade = score_grade(percent)

    result = {
        "quiz_id": quiz_id,
        "quiz_title": quiz.get("title", "—"),
        "correct": correct,
        "total": total,
        "percent": percent,
        "grade": grade,
        "time_spent": elapsed,
        "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "answers": session.get("answers", [])
    }
    uid = str(user_id)
    if uid not in data["results"]:
        data["results"][uid] = []
    data["results"][uid].append(result)
    save_data(data)
    clear_session(user_id)

    user = data["users"].get(uid, {})
    bot.send_message(chat_id,
        f"🏁 *Тест завершён!*\n\n"
        f"📋 {quiz.get('title', '—')}\n"
        f"✅ Правильных: {correct}/{total}\n"
        f"📊 Результат: {percent}%\n"
        f"🏅 Оценка: {grade}\n"
        f"⏱ Затрачено: {elapsed} мин.\n\n"
        f"Так держать, {user.get('name', 'ученик')}! 💪",
        parse_mode="Markdown",
        reply_markup=student_main_kb())

    # Уведомить учителя
    teacher_id = quiz.get("teacher_id")
    if teacher_id:
        try:
            bot.send_message(teacher_id,
                f"📩 *Новый результат!*\n\n"
                f"👤 {user.get('name', 'Неизвестный')} ({user.get('class_grade', '?')} кл.)\n"
                f"📋 {quiz.get('title', '—')}\n"
                f"✅ {correct}/{total} ({percent}%) — {grade}\n"
                f"📅 {result['date']}",
                parse_mode="Markdown")
        except Exception:
            pass

# ─── МОИ РЕЗУЛЬТАТЫ (ученик) ──────────────────────────────────────────────────

@bot.message_handler(func=lambda m: not is_teacher(m.from_user.id) and m.text == "📊 Мои результаты")
def student_my_results(message):
    uid = str(message.from_user.id)
    results = data["results"].get(uid, [])
    if not results:
        bot.send_message(message.chat.id, "Вы ещё не прошли ни одного теста. Пора начать! 🎯",
                         reply_markup=student_main_kb())
        return
    text = f"📊 *Ваши результаты* ({len(results)} попыток)\n\n"
    for r in results[-10:]:  # последние 10
        text += (
            f"📋 {r['quiz_title']}\n"
            f"   ✅ {r['correct']}/{r['total']} ({r['percent']}%) — {r['grade']}\n"
            f"   📅 {r['date']}\n\n"
        )
    avg = round(sum(r["percent"] for r in results) / len(results), 1)
    text += f"📈 Средний балл: *{avg}%*"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=student_main_kb())

@bot.message_handler(func=lambda m: not is_teacher(m.from_user.id) and m.text == "🏆 Рейтинг")
def student_rating(message):
    scores = []
    for uid, results in data["results"].items():
        if not results:
            continue
        avg = round(sum(r["percent"] for r in results) / len(results), 1)
        user = data["users"].get(uid, {})
        scores.append({"name": user.get("name", "?"), "class": user.get("class_grade", "?"),
                        "avg": avg, "count": len(results)})
    scores.sort(key=lambda x: x["avg"], reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 *Рейтинг учеников*\n\n"
    for i, s in enumerate(scores[:15], 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        text += f"{medal} *{s['name']}* ({s['class']} кл.) — {s['avg']}% ({s['count']} тестов)\n"
    if not scores:
        text += "Рейтинг пуст. Будьте первым!"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=student_main_kb())

@bot.message_handler(func=lambda m: not is_teacher(m.from_user.id) and m.text == "ℹ️ Мой профиль")
def student_profile(message):
    uid = str(message.from_user.id)
    user = data["users"].get(uid, {})
    results = data["results"].get(uid, [])
    avg = round(sum(r["percent"] for r in results) / len(results), 1) if results else 0
    best = max((r["percent"] for r in results), default=0)
    text = (
        f"👤 *Профиль*\n\n"
        f"📛 Имя: {user.get('name', '—')}\n"
        f"🏫 Класс: {user.get('class_grade', '—')}\n"
        f"📅 Зарегистрирован: {user.get('registered_at', '—')}\n\n"
        f"📊 Тестов пройдено: {len(results)}\n"
        f"📈 Средний балл: {avg}%\n"
        f"🌟 Лучший результат: {best}%\n"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=student_main_kb())

# ─── ПОИСК ТЕСТА (учитель) ───────────────────────────────────────────────────

@bot.message_handler(func=lambda m: is_teacher(m.from_user.id) and
                     get_session(m.from_user.id).get("state") == "teacher_search")
def teacher_search_result(message):
    query = message.text.strip().upper()
    found = []
    for q in data["quizzes"].values():
        if query in q["id"] or query.lower() in q["title"].lower():
            found.append(q)
    clear_session(message.from_user.id)
    if not found:
        bot.send_message(message.chat.id, "❌ Тест не найден.", reply_markup=teacher_main_kb())
        return
    text = f"🔍 *Найдено: {len(found)} тест(ов)*\n\n"
    for q in found:
        text += format_quiz_info(q) + "\n\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=teacher_main_kb())

# ─── FALLBACK ─────────────────────────────────────────────────────────────────

@bot.message_handler(func=lambda m: True)
def fallback(message):
    if is_teacher(message.from_user.id):
        send_teacher_menu(message)
    else:
        uid = str(message.from_user.id)
        if uid in data["users"]:
            send_student_menu(message)
        else:
            cmd_start(message)

# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("🤖 BioChemBot запущен!")
    print(f"👨‍🏫 ID учителя: {TEACHER_ID}")
    bot.infinity_polling()