import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, ContentType, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, \
    InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
import asyncio
from datetime import datetime, timedelta

# Ваш токен Telegram Bot API
API_TOKEN = '8087708008:AAEQBHTwwv7GDvXkJngs7MkdBPlKI1VIBEw'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Инициализация базы данных
conn = sqlite3.connect("bot_database.db")
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    photo_id TEXT NOT NULL,
    hashtags TEXT NOT NULL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    target_user_id INTEGER NOT NULL,
    interaction_type TEXT NOT NULL,
    interaction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, target_user_id)
)
''')
conn.commit()


# Определение состояний
class ProfileStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_hashtags = State()
    waiting_for_photo = State()
    changing_hashtags = State()
    changing_photo = State()
    viewing_profiles = State()
    waiting_for_show_liker_response = State()
    filling_profile_again = State()


# Команда /start
@dp.message(Command(commands=['start']))
async def start_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    cursor.execute("SELECT username, photo_id, hashtags FROM profiles WHERE user_id = ?", (user_id,))
    profile = cursor.fetchone()

    if profile:
        await message.answer("Ваша анкета уже существует. Вот она:")
        await show_profile(message, user_id)
    else:
        await message.answer("Привет! Введите ваше имя для создания анкеты.")
        await state.set_state(ProfileStates.waiting_for_name)


# Обработчик имени
@dp.message(ProfileStates.waiting_for_name)
@dp.message(ProfileStates.filling_profile_again)
async def handle_name(message: Message, state: FSMContext):
    if message.text is None:
        await message.answer("Пожалуйста, введите ваше имя.")
        return

    name = message.text.strip()

    if not name:  # Check if the name is empty or just whitespace
        await message.answer("Пожалуйста, введите ваше имя.")
        return

    await state.update_data(name=name)
    await message.answer("Введите минимум 3 хэштега (слова через пробел) для вашей анкеты.")
    await state.set_state(ProfileStates.waiting_for_hashtags)


# Обработчик хэштегов
@dp.message(ProfileStates.waiting_for_hashtags)
async def handle_hashtags(message: Message, state: FSMContext):
    hashtags = message.text.lower()  # Преобразуем хэштеги в нижний регистр
    hashtags_list = hashtags.split()

    if len(hashtags_list) < 3:
        await message.answer("Пожалуйста, введите минимум 3 хэштега.")
        return

    await state.update_data(hashtags=hashtags)
    await message.answer("Отправьте ваше фото.")
    await state.set_state(ProfileStates.waiting_for_photo)


# Обработчик фото
@dp.message(ProfileStates.waiting_for_photo, F.content_type == ContentType.PHOTO)
async def handle_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    username = data.get('name')
    hashtags = data.get('hashtags')
    photo_id = message.photo[-1].file_id

    # Проверяем, существует ли анкета пользователя
    cursor.execute("SELECT user_id FROM profiles WHERE user_id = ?", (user_id,))
    profile_exists = cursor.fetchone()

    if profile_exists:
        # Обновление анкеты в базе данных
        cursor.execute("UPDATE profiles SET username = ?, photo_id = ?, hashtags = ? WHERE user_id = ?",
                       (username, photo_id, hashtags, user_id))
    else:
        # Сохранение анкеты в базу данных
        cursor.execute("INSERT INTO profiles (user_id, username, photo_id, hashtags) VALUES (?, ?, ?, ?)",
                       (user_id, username, photo_id, hashtags))
    conn.commit()

    await message.answer("Анкета сохранена! Вот ваша анкета:")
    await show_profile(message, user_id)

    await state.clear()


# Обработчик, если фото не отправлено
@dp.message(ProfileStates.waiting_for_photo)
async def handle_no_photo(message: Message):
    await message.answer("Пожалуйста, отправьте фото!")


# Команда /myprofile для просмотра своей анкеты
@dp.message(Command(commands=['myprofile']))
async def my_profile_command(message: Message):
    user_id = message.from_user.id
    await show_profile(message, user_id)


# Команда /changehashtags для изменения хэштегов
@dp.message(Command(commands=['changehashtags']))
async def change_hashtags_command(message: Message, state: FSMContext):
    await message.answer("Введите новые хэштеги (минимум 3 хэштега, слова через пробел):")
    await state.set_state(ProfileStates.changing_hashtags)


# Обработчик изменения хэштегов
@dp.message(ProfileStates.changing_hashtags)
async def handle_change_hashtags(message: Message, state: FSMContext):
    hashtags = message.text.lower()  # Преобразуем хэштеги в нижний регистр
    hashtags_list = hashtags.split()

    if len(hashtags_list) < 3:
        await message.answer("Пожалуйста, введите минимум 3 хэштега.")
        return

    user_id = message.from_user.id
    cursor.execute("UPDATE profiles SET hashtags = ? WHERE user_id = ?", (hashtags, user_id))
    conn.commit()

    await message.answer("Хэштеги обновлены! Вот ваша новая анкета:")
    await show_profile(message, user_id)
    await state.clear()


# Команда /changephoto для изменения фотографии
@dp.message(Command(commands=['changephoto']))
async def change_photo_command(message: Message, state: FSMContext):
    await message.answer("Отправьте новую фотографию:")
    await state.set_state(ProfileStates.changing_photo)


# Обработчик изменения фотографии
@dp.message(ProfileStates.changing_photo, F.content_type == ContentType.PHOTO)
async def handle_change_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id

    cursor.execute("UPDATE profiles SET photo_id = ? WHERE user_id = ?", (photo_id, user_id))
    conn.commit()

    await message.answer("Фотография обновлена! Вот ваша новая анкета:")
    await show_profile(message, user_id)
    await state.clear()


# Обработчик, если фото не отправлено при изменении фотографии
@dp.message(ProfileStates.changing_photo)
async def handle_no_photo_change(message: Message):
    await message.answer("Пожалуйста, отправьте фото!")


# Функция для показа анкеты
async def show_profile(message: Message, user_id: int):
    cursor.execute("SELECT username, photo_id, hashtags FROM profiles WHERE user_id = ?", (user_id,))
    profile = cursor.fetchone()

    if profile:
        username, photo_id, hashtags = profile
        caption = (f"Имя: {username}\n"
                   f"Хэштеги: {hashtags}")
        await bot.send_photo(message.chat.id, photo_id, caption=caption)

        # Добавление меню взаимодействий
        interaction_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Смотреть анкеты", callback_data="view_profiles")],
            [InlineKeyboardButton(text="Заполнить анкету заново", callback_data="fill_profile_again")],
            [InlineKeyboardButton(text="Изменить фото", callback_data="change_photo")],
            [InlineKeyboardButton(text="Изменить хэштеги", callback_data="change_hashtags")]
        ])
        await bot.send_message(message.chat.id, "Выберите действие:", reply_markup=interaction_keyboard)
    else:
        await message.answer("Анкета не найдена.")


# Обработчик нажатий на кнопки меню взаимодействий
@dp.callback_query(F.data == "view_profiles")
async def handle_view_profiles(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    cursor.execute("SELECT user_id FROM profiles WHERE user_id = ?", (user_id,))
    profile_exists = cursor.fetchone()

    if profile_exists:
        # Создаем эмуляцию сообщения пользователя, чтобы вызвать команду /search
        fake_message = types.Message(
            message_id=callback_query.message.message_id,
            from_user=callback_query.from_user,
            chat=callback_query.message.chat,
            date=callback_query.message.date,
            text="/search"
        )
        await search_command(fake_message, state, bot)
    else:
        await bot.send_message(callback_query.message.chat.id,
                               "Анкета не найдена. Сначала создайте анкету с помощью команды /start.")
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query(F.data == "fill_profile_again")
async def handle_fill_profile_again(callback_query: CallbackQuery, state: FSMContext):
    await bot.send_message(callback_query.message.chat.id, "Введите ваше имя для создания анкеты.")
    await state.set_state(ProfileStates.filling_profile_again)
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query(F.data == "change_photo")
async def handle_change_photo(callback_query: CallbackQuery, state: FSMContext):
    await change_photo_command(callback_query.message, state)
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query(F.data == "change_hashtags")
async def handle_change_hashtags(callback_query: CallbackQuery, state: FSMContext):
    await change_hashtags_command(callback_query.message, state)
    await bot.answer_callback_query(callback_query.id)


# Функция для показа анкеты с кнопками лайка и дизлайка, а также с новыми кнопками "Сон" и "Профиль"
# Функция для показа анкеты с кнопками лайка и дизлайка, а также с новыми кнопками "Сон" и "Профиль"

async def show_profile_with_buttons(message: Message, state: FSMContext, target_user_id: int, username: str, photo_id: str, hashtags: str):
    caption = f"Имя: {username}\nХэштеги: {hashtags}"
    await bot.send_photo(message.chat.id, photo_id, caption=caption)

    # Сохранение target_user_id в состоянии
    await state.update_data(target_user_id=target_user_id)

    # Создаем меню снизу с кнопками
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👍"), KeyboardButton(text="👎")],
            [KeyboardButton(text="💤"), KeyboardButton(text="Профиль")]
        ],
        resize_keyboard=True
    )
    await bot.send_message(chat_id=message.chat.id, text="Оцените анкету:", reply_markup=keyboard)


# Обработчик команды /search
@dp.message(Command(commands=['search']))
async def search_command(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    cursor.execute("SELECT hashtags FROM profiles WHERE user_id = ?", (user_id,))
    profile = cursor.fetchone()

    if profile:
        hashtags = profile[0].split()
        matching_profiles = {}
        one_day_ago = datetime.now() - timedelta(days=2)

        for hashtag in hashtags:
            cursor.execute("""
                SELECT p.user_id, p.username, p.photo_id, p.hashtags
                FROM profiles p
                LEFT JOIN interactions i ON p.user_id = i.target_user_id AND i.user_id = ?
                WHERE p.hashtags LIKE ? AND p.user_id != ? AND (i.interaction_time IS NULL OR i.interaction_time < ?)
            """, (user_id, f"%{hashtag}%", user_id, one_day_ago))
            results = cursor.fetchall()
            for target_user_id, username, photo_id, hashtags in results:
                if (target_user_id, username, photo_id, hashtags) in matching_profiles:
                    matching_profiles[(target_user_id, username, photo_id, hashtags)] += 1
                else:
                    matching_profiles[(target_user_id, username, photo_id, hashtags)] = 1

        filtered_profiles = [profile for profile, count in matching_profiles.items() if count >= 2]

        if filtered_profiles:
            await state.update_data(profiles=filtered_profiles)
            await state.update_data(current_profile_index=0)
            await show_next_profile(message, state)
        else:
            await bot.send_message(message.chat.id, "Анкеты закончили, возвращайтесь завтра.")
    else:
        await bot.send_message(message.chat.id, "Анкета не найдена. Сначала создайте анкету с помощью команды /start.")


# Показать следующую анкету

async def show_next_profile(message: Message, state: FSMContext):
    data = await state.get_data()
    profiles = data.get('profiles', [])
    index = data.get('current_profile_index', 0)

    if index < len(profiles):
        target_user_id, username, photo_id, hashtags = profiles[index]
        await state.update_data(current_profile_index=index + 1)
        await show_profile_with_buttons(message, state, target_user_id, username, photo_id, hashtags)
    else:
        await bot.send_message(message.chat.id, "На этом всё, возвращайтесь завтра.")
        await state.clear()


# Обработчик нажатия на кнопки лайка и дизлайка
@dp.message(F.text.startswith("👍"))
async def handle_like(message: Message, state: FSMContext):
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    user_id = message.from_user.id

    if target_user_id is None:
        return

    cursor.execute(
        "INSERT OR REPLACE INTO interactions (user_id, target_user_id, interaction_type, interaction_time) VALUES (?, ?, ?, ?)",
        (user_id, target_user_id, "like", datetime.now()))
    conn.commit()

    # Отправка уведомления пользователю о лайке с кнопками "Да" и "Нет"
    liker_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data=f"show_liker_{user_id}"),
         InlineKeyboardButton(text="Нет", callback_data="ignore_liker")]
    ])
    await bot.send_message(target_user_id,
                           f"Вы кому-то понравились! Вы хотите посмотреть его анкету?",
                           reply_markup=liker_keyboard)

    cursor.execute("SELECT interaction_type FROM interactions WHERE user_id = ? AND target_user_id = ?",
                   (target_user_id, user_id))
    target_interaction = cursor.fetchone()
    if target_interaction and target_interaction[0] == "like":
        # Получение имени пользователя
        target_user = await bot.get_chat(target_user_id)
        target_username = target_user.username or target_user.first_name
        user_user = await bot.get_chat(user_id)
        user_username = user_user.username or user_user.first_name

        await message.answer(f"У вас взаимная симпатия с @{target_username}!")
        await bot.send_message(target_user_id, f"У вас взаимная симпатия с @{user_username}!")

    await show_next_profile(message, state)


@dp.message(F.text.startswith("👎"))
async def handle_dislike(message: Message, state: FSMContext):
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    user_id = message.from_user.id

    if target_user_id is None:
        await message.answer("Ошибка: не удалось получить ID пользователя.")
        return

    cursor.execute(
        "INSERT OR REPLACE INTO interactions (user_id, target_user_id, interaction_type, interaction_time) VALUES (?, ?, ?, ?)",
        (user_id, target_user_id, "dislike", datetime.now()))
    conn.commit()

    await show_next_profile(message, state)


# Обработчик нажатия на кнопку "Сон", чтобы остановить показ анкет
@dp.message(F.text == "💤")
async def handle_sleep(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Показ анкет остановлен.")


# Обработчик нажатия на кнопку "Профиль", чтобы показать профиль пользователя
@dp.message(F.text == "Профиль")
async def handle_profile(message: Message):
    user_id = message.from_user.id
    await show_profile(message, user_id)


@dp.callback_query(F.data.startswith("show_liker_"))
async def show_liker_profile(callback_query: CallbackQuery, state: FSMContext):
    user_id = int(callback_query.data.split('_')[2])
    cursor.execute("SELECT username, photo_id, hashtags FROM profiles WHERE user_id = ?", (user_id,))
    profile = cursor.fetchone()

    if profile:
        username, photo_id, hashtags = profile
        await show_profile_with_buttons(callback_query.message, state, user_id, username, photo_id, hashtags)

    await bot.answer_callback_query(callback_query.id)


@dp.callback_query(F.data == "ignore_liker")
async def ignore_liker(callback_query: CallbackQuery):
    await bot.answer_callback_query(callback_query.id, text="Вы отказались смотреть анкету.")
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)


# Периодическая задача для обнуления лайков и дизлайков раз в два дня
async def reset_likes_dislikes():
    while True:
        await asyncio.sleep(2 * 24 * 60 * 60)  # 2 дня
        cursor.execute("DELETE FROM interactions")
        conn.commit()


async def main():
    asyncio.create_task(reset_likes_dislikes())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())