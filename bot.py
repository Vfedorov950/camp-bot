import os
import sqlite3
import asyncio
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
bot = Bot(token=os.getenv("API_TOKEN"))
dp = Dispatcher()

# Состояния для FSM
class GameStates(StatesGroup):
    selecting_goal = State()
    selecting_age = State()
    adding_comment = State()
    adding_game = State()
    waiting_comment_choice = State()
    moderating_game = State()
# Инициализация БД
def init_db():
    conn = sqlite3.connect('camp_games.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        goal TEXT NOT NULL,
        age TEXT NOT NULL,
        prep TEXT NOT NULL,
        rules TEXT NOT NULL,
        instruction TEXT NOT NULL,
        comments TEXT DEFAULT '',
        rating_sum INTEGER DEFAULT 0,
        rating_count INTEGER DEFAULT 0,
        plays_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending'
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER,
        user_id INTEGER,
        rating INTEGER,
        comment TEXT,
        moderated BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (game_id) REFERENCES games (id)
    )''')
    conn.commit()
    conn.close()

init_db()

# Клавиатуры
async def main_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="🔍 Найти игру"))
    builder.add(types.KeyboardButton(text="✏ Добавить игру"))
    return builder.as_markup(resize_keyboard=True)

async def yesnot_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Да"))
    builder.add(types.KeyboardButton(text="⬅️ Назад"))
    return builder.as_markup(resize_keyboard=True)

async def goal_keyboard():
    goals = ["Знакомство", "Подвижные", "Сплочение", "Сканер", "Фоновые"]
    builder = ReplyKeyboardBuilder()
    for goal in goals:
        builder.add(types.KeyboardButton(text=goal))
    builder.add(types.KeyboardButton(text="⬅️ Назад"))
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

async def age_keyboard():
    ages = ["7-9 лет", "10-12 лет", "13-15 лет", "16+", "Для всех"]
    builder = ReplyKeyboardBuilder()
    for age in ages:
        builder.add(types.KeyboardButton(text=age))
    builder.add(types.KeyboardButton(text="⬅️ Назад"))
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

async def rating_keyboard(game_id):
    builder = ReplyKeyboardBuilder()
    for i in range(1, 6):
        builder.add(types.KeyboardButton(text=f"{1 * i}"))  # 1-5 звезд
    builder.add(types.KeyboardButton(text="⬅️ Назад"))
    builder.adjust(5, 1)
    return builder.as_markup(resize_keyboard=True)

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Я бот-помощник для вожатых 🏕️",
        reply_markup=await main_menu()
    )

@dp.message(lambda message: message.text == "⬅️ Назад")
async def back_to_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Возвращаемся в главное меню",
        reply_markup=await main_menu()
    )

@dp.message(lambda message: message.text == "🔍 Найти игру")
async def find_game(message: types.Message, state: FSMContext):
    await state.set_state(GameStates.selecting_goal)
    await message.answer(
        "Выберите цель игры:",
        reply_markup=await goal_keyboard()
    )

@dp.message(GameStates.selecting_goal, lambda message: message.text in ["Знакомство", "Подвижные", "Сплочение", "Сканер", "Фоновые"])
async def select_goal(message: types.Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await state.set_state(GameStates.selecting_age)
    await message.answer(
        "Выберите возрастную категорию:",
        reply_markup=await age_keyboard()
    )

@dp.message(GameStates.selecting_age, lambda message: message.text in ["7-9 лет", "10-12 лет", "13-15 лет", "16+", "Для всех"])
async def select_age(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    goal = user_data.get("goal")
    age = message.text
    
    conn = sqlite3.connect('camp_games.db')
    cursor = conn.cursor()
    
    games = {
        "Новая": None,
        "Популярная": None,
        "Топовая": None
    }
    
    try:
        # Получаем игры из БД
        cursor.execute('''
        SELECT id, name, description FROM games 
        WHERE goal = ? AND (age = ? OR age = 'Для всех') AND status = 'approved'
        ORDER BY rating_count ASC, 
        CASE WHEN rating_count > 0 THEN rating_sum*1.0/rating_count ELSE 0 END DESC 
        LIMIT 1
        ''', (goal, age))
        games["Новая"] = cursor.fetchone()
        
        cursor.execute('''
        SELECT id, name, description FROM games 
        WHERE goal = ? AND (age = ? OR age = 'Для всех') AND status = 'approved'
        ORDER BY rating_count DESC 
        LIMIT 1
        ''', (goal, age))
        games["Популярная"] = cursor.fetchone()
        
        cursor.execute('''
        SELECT id, name, description FROM games 
        WHERE goal = ? AND (age = ? OR age = 'Для всех') AND status = 'approved'
        ORDER BY 
        CASE WHEN rating_count > 0 THEN rating_sum*1.0/rating_count ELSE 0 END DESC 
        LIMIT 1
        ''', (goal, age))
        games["Топовая"] = cursor.fetchone()
        
        # Формируем ответ
        response = "Вот подходящие игры:\n\n"
        for game_type, game in games.items():
            if game:
                game_id, name, desc = game
                response += f"🎲 <b>{game_type}: {name}</b>\n"
                response += f"📝 {desc}\n"
                response += f"🔗 /game_{game_id}\n\n"
        
        await message.answer(
            response,
            reply_markup=await main_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            f"Произошла ошибка при поиске игр: {str(e)}",
            reply_markup=await main_menu()
        )
    finally:
        conn.close()
    await state.clear()

@dp.message(lambda message: message.text.startswith('/game_'))
async def show_full_game(message: types.Message, state: FSMContext):
    try:
        game_id = message.text.split('_')[1]
        await state.update_data(game_id=game_id)  # Сохраняем game_id в состоянии
        
        conn = sqlite3.connect('camp_games.db')
        cursor = conn.cursor()
        
        # Проверяем существование игры
        cursor.execute('SELECT id FROM games WHERE id = ? AND status = "approved"', (game_id,))
        if not cursor.fetchone():
            await message.answer("🚫 Игра не найдена или еще не прошла модерацию")
            return
            
        cursor.execute('''
        SELECT name, prep, rules, instruction 
        FROM games 
        WHERE id = ? AND status = 'approved'
        ''', (game_id,))
        game = cursor.fetchone()
        
        if game:
            name, prep, rules, instruction = game
            response = (
                f"🎯 <b>{name}</b>\n\n"
                f"🔧 <b>Подготовка:</b>\n{prep}\n\n"
                f"📜 <b>Правила:</b>\n{rules}\n\n"
                f"🗣 <b>Инструкция:</b>\n{instruction}\n\n"
                "Оцените игру:"
            )
            await message.answer(response, parse_mode="HTML", reply_markup=await rating_keyboard(game_id))
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")
    finally:
        conn.close()

@dp.message(GameStates.waiting_comment_choice, lambda message: message.text in ["Да", "Нет", "⬅️ Назад"])
async def handle_comment_choice(message: types.Message, state: FSMContext):
    logger.info(f"Обработка выбора комментария: {message.text}")
    if message.text.lower() in ["нет", "⬅️ назад"]:
        await state.clear()
        await message.answer(
            "Возвращаемся в главное меню",
            reply_markup=await main_menu()
        )
    elif message.text.lower() == "да":
        await state.set_state(GameStates.adding_comment)
        logger.info("Установлено состояние adding_comment")
        
        builder = ReplyKeyboardBuilder()
        builder.add(types.KeyboardButton(text="⬅️ Назад"))
        
        await message.answer(
            "Напишите ваш комментарий к игре:",
            reply_markup=builder.as_markup(resize_keyboard=True),
            parse_mode="HTML"
        )

@dp.message(GameStates.adding_game)
async def process_new_game(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != GameStates.adding_game:
        return
        
    # ... остальной код без изменений
    # Проверяем, не пытается ли пользователь добавить игру
    if "Название:" in message.text and "Цель:" in message.text:
        await state.set_state(GameStates.adding_game)
        await process_new_game(message, state)
        return
    
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("Комментарий не добавлен", reply_markup=await main_menu())
        return
    
    # ... остальной код без изменений
    
    user_data = await state.get_data()
    game_id = user_data.get('game_id')
    review_id = user_data.get('review_id')
    
    if not game_id or not review_id:
        await message.answer("❌ Ошибка: сначала поставьте оценку", reply_markup=await main_menu())
        await state.clear()
        return
    
    conn = None
    try:
        conn = sqlite3.connect('camp_games.db')
        cursor = conn.cursor()
        
        # Просто сохраняем комментарий с moderated=FALSE
        cursor.execute('''
        UPDATE reviews 
        SET comment = ?, moderated = FALSE
        WHERE id = ?
        ''', (message.text, review_id))
        
        conn.commit()
        
        await message.answer(
            "✅ Комментарий отправлен на модерацию!",
            reply_markup=await main_menu()
        )
        
    except Exception as e:
        await message.answer("❌ Ошибка при сохранении", reply_markup=await main_menu())
    finally:
        if conn:
            conn.close()
        await state.clear()
        

@dp.message(lambda message: message.text and any(str(i) in message.text for i in range(1, 6)))
async def rate_game(message: types.Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        game_id = user_data.get('game_id')
        
        if not game_id:
            await message.answer("❌ Сначала откройте игру через меню поиска")
            return

        rating = int(message.text.strip()[0])
        if rating < 1 or rating > 5:
            await message.answer("⚠️ Пожалуйста, выберите оценку от 1 до 5")
            return

        conn = sqlite3.connect('camp_games.db')
        cursor = conn.cursor()
        
        try:
            # Обновляем рейтинг игры
            cursor.execute('''
            UPDATE games 
            SET rating_sum = rating_sum + ?, 
                rating_count = rating_count + 1,
                plays_count = plays_count + 1
            WHERE id = ?
            ''', (rating, game_id))
            
            # Добавляем запись в отзывы и получаем ID
            cursor.execute('''
            INSERT INTO reviews (game_id, user_id, rating)
            VALUES (?, ?, ?)
            ''', (game_id, message.from_user.id, rating))
            
            # Сохраняем review_id в состоянии
            review_id = cursor.lastrowid
            await state.update_data(review_id=review_id)
            
            conn.commit()
            
            builder = ReplyKeyboardBuilder()
            builder.add(types.KeyboardButton(text="Да"))
            builder.add(types.KeyboardButton(text="Нет"))
            builder.adjust(2)
            
            await message.answer(
                f"⭐ Спасибо за оценку {rating}! Хотите добавить комментарий?",
                reply_markup=builder.as_markup(resize_keyboard=True)
            )
            
            await state.set_state(GameStates.waiting_comment_choice)
            
        except Exception as e:
            await message.answer(f"⚠️ Ошибка базы данных: {str(e)}")
        finally:
            conn.close()
            
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите число от 1 до 5")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")

@dp.message(lambda message: message.text == "✏ Добавить игру")
async def add_new_game(message: types.Message, state: FSMContext):
    await state.clear()  # Очищаем предыдущие состояния
    await state.set_state(GameStates.adding_game)
    # ... остальной код без изменений
    await message.answer(
        "Чтобы добавить новую игру, отправьте её в формате:\n\n"
        "Название: Название игры\n"
        "Цель: Знакомство/Подвижные/Сплочение/Сканер/Фоновые\n"
        "Возраст: 7-9 лет/10-12 лет/13-15 лет/16+/Для всех\n"
        "Описание: Краткое описание\n"
        "Подготовка: Что нужно подготовить\n"
        "Правила: Как играть\n"
        "Инструкция: Что говорить детям",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message(GameStates.adding_game)
async def process_new_game(message: types.Message, state: FSMContext):
    try:
        parts = message.text.split('\n')
        game_data = {}
        for part in parts:
            if ':' in part:
                key, value = part.split(':', 1)
                game_data[key.strip()] = value.strip()
        
        conn = sqlite3.connect('camp_games.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO games (name, goal, age, description, prep, rules, instruction, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        ''', (
            game_data.get("Название", ""),
            game_data.get("Цель", ""),
            game_data.get("Возраст", ""),
            game_data.get("Описание", ""),
            game_data.get("Подготовка", ""),
            game_data.get("Правила", ""),
            game_data.get("Инструкция", "")
        ))
        conn.commit()
        
        await message.answer(
            "✅ Игра отправлена на модерацию! После проверки она станет доступна для всех.",
            reply_markup=await main_menu()
        )
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при добавлении игры: {str(e)}\nПопробуйте ещё раз.",
            reply_markup=await main_menu()
        )
    finally:
        conn.close()
        await state.clear()


# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())