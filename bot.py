import asyncio
import logging
import os
from datetime import datetime, timedelta
from urllib.parse import quote

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# Загружаем переменные окружения
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN", "7884349748:AAEZC82Nd72L1eR1rhupuDWihjWdEKG4bd8")
CHAT_ID = int(os.getenv("CHAT_ID", "-1003650005079"))
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "765740972,6933111964").split(",")]


def telegram_proxy_url() -> str | None:
    """Нормализовать прокси для Telegram API.

    Поддерживаем:
    - socks5://user:pass@host:port (или http://...)
    - host:port:user:pass (формат из панелей)
    """
    raw = (os.getenv("TELEGRAM_PROXY") or "").strip()
    if not raw:
        return None
    if "://" in raw:
        return raw
    parts = raw.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        user_q = quote(user, safe="")
        pass_q = quote(password, safe="")
        return f"socks5://{user_q}:{pass_q}@{host}:{port}"
    return raw

# Ссылки на документы (PDF файлы на GitHub)
BASE_DOCS_URL = "https://raw.githubusercontent.com/SiteCraftorCPP/domastroi_price_bot/main/politika%20i%20soglasie/"
CONSENT_URL = os.getenv("CONSENT_URL", BASE_DOCS_URL + quote("agreement.pdf", safe=""))  # URL текста согласия
PRIVACY_POLICY_URL = os.getenv("PRIVACY_POLICY_URL", BASE_DOCS_URL + quote("Privacy Policy.pdf", safe=""))  # URL политики конфиденциальности

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Инициализация бота (с прокси — нужен пакет aiohttp-socks)
_proxy = telegram_proxy_url()
_bot_session = AiohttpSession(proxy=_proxy) if _proxy else AiohttpSession()
bot = Bot(token=BOT_TOKEN, session=_bot_session)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Словарь для отслеживания задач напоминаний (user_id -> list of tasks)
reminder_tasks = {}

# Стикеры для напоминаний (в порядке отправки: 15 мин, 1 час, 3 часа, 6 часов)
REMINDER_STICKERS = [
    "CAACAgIAAxkBApUFg2lNaL09xGOpfkD_m9xkc0VKXOPdAAJ4JQACns4LAAGDyOccgT5A2DYE",  # 😐 15 мин
    "CAACAgIAAxkBApUFjWlNaMVKyr4HFrx4exu29A6fbsC4AAKAJQACns4LAAGBQrQPedmR7TYE",  # 😥 1 час
    "CAACAgIAAxkBApUFoGlNaNngFpNsm9luIbTVrNsdEfjoAAJ8JQACns4LAAEL1z71bsX8fzYE",  # 💪 3 часа
    "CAACAgIAAxkBApUFq2lNaN2gLezX5w8wTd6HJufwS1oPAAKOJQACns4LAAFbqxE8XpCvUzYE",  # ❤️ 6 часов
]

# Интервалы напоминаний в минутах
REMINDER_INTERVALS = [15, 60, 180, 360]  # 15 мин, 1 час, 3 часа, 6 часов

# ============= СИСТЕМА НАПОМИНАНИЙ =============

async def send_reminder(user_id: int, sticker_index: int):
    """Отправляет стикер-напоминание пользователю, если он все еще в процессе опроса"""
    try:
        # Проверяем, что пользователь все еще в процессе (не завершил опрос)
        # Создаем временный FSMContext для проверки состояния
        from aiogram.fsm.context import FSMContext
        from aiogram.fsm.storage.base import StorageKey
        
        # Создаем ключ для storage
        storage_key = StorageKey(
            chat_id=user_id,
            user_id=user_id,
            bot_id=bot.id
        )
        
        temp_state = FSMContext(storage=storage, key=storage_key)
        current_state = await temp_state.get_state()
        
        if current_state is None:
            # Пользователь завершил опрос или вышел, отменяем напоминания
            cancel_reminders(user_id)
            return
        
        # Отправляем стикер
        if sticker_index < len(REMINDER_STICKERS):
            await bot.send_sticker(user_id, REMINDER_STICKERS[sticker_index])
            logging.info(f"Sent reminder {sticker_index + 1} to user {user_id}")
    except Exception as e:
        logging.error(f"Error sending reminder to user {user_id}: {e}")
        # Если ошибка, отменяем напоминания для этого пользователя
        cancel_reminders(user_id)

async def schedule_reminders(user_id: int):
    """Планирует отправку напоминаний для пользователя"""
    # Отменяем предыдущие задачи, если они есть
    cancel_reminders(user_id)
    
    # Создаем новые задачи для каждого интервала
    tasks = []
    for i, interval_minutes in enumerate(REMINDER_INTERVALS):
        # Исправляем замыкание - создаем функцию-фабрику
        def create_reminder_task(index, minutes):
            async def reminder_task():
                sleep_seconds = minutes * 60
                logging.info(f"Reminder task {index + 1} for user {user_id} will sleep {sleep_seconds} seconds ({minutes} minutes)")
                await asyncio.sleep(sleep_seconds)  # Конвертируем минуты в секунды
                logging.info(f"Reminder task {index + 1} for user {user_id} woke up, sending sticker {index + 1}")
                await send_reminder(user_id, index)
            return reminder_task
        
        task = asyncio.create_task(create_reminder_task(i, interval_minutes)())
        tasks.append(task)
    
    reminder_tasks[user_id] = tasks
    logging.info(f"Scheduled {len(tasks)} reminders for user {user_id}")

def cancel_reminders(user_id: int):
    """Отменяет все напоминания для пользователя"""
    if user_id in reminder_tasks:
        for task in reminder_tasks[user_id]:
            if not task.done():
                task.cancel()
        del reminder_tasks[user_id]
        logging.info(f"Cancelled reminders for user {user_id}")

# Состояния FSM
class Form(StatesGroup):
    property_type = State()
    repair_type = State()
    style_type = State()
    square_meters = State()
    deadline = State()
    consent = State()
    phone = State()


# ============= АДМИНСКИЕ КОМАНДЫ =============

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return
    
    await message.answer("🔐 <b>Админ-панель</b>\n\nДоступные функции будут добавлены позже.", parse_mode="HTML")

# ============= ОСНОВНОЙ СЦЕНАРИЙ БОТА =============

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    # Отменяем предыдущие напоминания, если они есть
    cancel_reminders(message.from_user.id)
    # Запускаем напоминания при команде /start
    await schedule_reminders(message.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Рассчитать стоимость", callback_data="start_calc")]
    ])
    
    welcome_text = (
        "Привет! Я бот компании Domastroi — мы разрабатываем качественные проекты и делаем ремонт под ключ.\n\n"
        "<b>Репутация:</b> <b>15 лет, 8 стран, 2000+ проектов</b>, формат <b>«под ключ в одной компании»</b> и очень качественные чертежи без ошибок. Мы сделаем интерьер, которым <b>вы будете гордиться</b>.\n\n"
        "<b>Сделаем расчет?</b>\n"
        "Это займет всего несколько минут, и вы получите:\n\n"
        "🏆 Расчет стоимости ремонта\n"
        "🏆 Пошаговый план ремонта от А до Я\n"
        "🏆 Консультацию дизайнера по вашей планировке\n\n"
        "<b>Готовы начать?</b>\n\n"
        f"🤝 Продолжая использовать чат-бот вы выражаете <a href=\"{CONSENT_URL}\">согласие</a> на обработку персональных данных в соответствии с <a href=\"{PRIVACY_POLICY_URL}\">политикой</a>. 🔒"
    )
    
    # Отправляем только текст без фото
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)

@dp.callback_query(F.data == "start_calc")
async def start_calculation(callback: types.CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Новостройка", callback_data="prop_new")],
        [InlineKeyboardButton(text="Вторичка", callback_data="prop_old")],
        [InlineKeyboardButton(text="Дом", callback_data="prop_house")],
        [InlineKeyboardButton(text="Коммерция", callback_data="prop_commercial")]
    ])
    
    text = (
        "Вопрос 1 из 5\n"
        "Какую недвижимость нужно отремонтировать?\n\n"
        "▰▱▱▱▱\n"
        "Расчёт готов на 20%"
    )
    
    msg = await callback.message.answer(text, reply_markup=keyboard)
    await state.update_data(last_message_id=msg.message_id)
    await state.set_state(Form.property_type)
    await callback.answer()

@dp.callback_query(Form.property_type, F.data.startswith("prop_"))
async def process_property_type(callback: types.CallbackQuery, state: FSMContext):
    property_mapping = {
        "prop_new": "Новостройка",
        "prop_old": "Вторичка",
        "prop_house": "Дом",
        "prop_commercial": "Коммерция"
    }
    
    await state.update_data(property_type=property_mapping[callback.data])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Косметический", callback_data="repair_cosmetic")],
        [InlineKeyboardButton(text="Капитальный", callback_data="repair_capital")]
    ])
    
    text = (
        "Вопрос 2 из 5\n"
        "Какой ремонт будем делать?\n\n"
        "▰▰▱▱▱\n"
        "Расчёт готов на 40%"
    )
    
    msg = await callback.message.answer(text, reply_markup=keyboard)
    await state.update_data(last_message_id=msg.message_id)
    await state.set_state(Form.repair_type)
    await callback.answer()

@dp.callback_query(Form.repair_type, F.data.startswith("repair_"))
async def process_repair_type(callback: types.CallbackQuery, state: FSMContext):
    repair_mapping = {
        "repair_cosmetic": "Косметический",
        "repair_capital": "Капитальный"
    }
    
    await state.update_data(repair_type=repair_mapping[callback.data])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Базовый", callback_data="style_basic")],
        [InlineKeyboardButton(text="Комфорт", callback_data="style_comfort")],
        [InlineKeyboardButton(text="Бизнес", callback_data="style_business")],
        [InlineKeyboardButton(text="Премиум", callback_data="style_premium")]
    ])
    
    text = (
        "Вопрос 3 из 5\n"
        "Какой тип ремонта вам ближе?\n\n"
        "▰▰▰▱▱\n"
        "Расчёт готов на 60%"
    )
    
    msg = await callback.message.answer(text, reply_markup=keyboard)
    await state.update_data(last_message_id=msg.message_id)
    await state.set_state(Form.style_type)
    await callback.answer()

@dp.callback_query(Form.style_type, F.data.startswith("style_"))
async def process_style_type(callback: types.CallbackQuery, state: FSMContext):
    style_mapping = {
        "style_basic": "Базовый",
        "style_comfort": "Комфорт",
        "style_business": "Бизнес",
        "style_premium": "Премиум"
    }
    
    await state.update_data(style_type=style_mapping[callback.data])
    
    text = (
        "Вопрос 4 из 5\n"
        "Сколько квадратных метров помещение?\n\n"
        "▰▰▰▰▱\n"
        "Отлично! осталось чуть-чуть 🥁 Расчёт готов на 80%\n\n"
        "Введите число:"
    )
    
    msg = await callback.message.answer(text)
    await state.update_data(last_message_id=msg.message_id)
    await state.set_state(Form.square_meters)
    await callback.answer()

@dp.message(Form.square_meters)
async def process_square_meters(message: types.Message, state: FSMContext):
    # Проверяем, что сообщение содержит только цифры
    if not message.text.isdigit():
        await message.answer("❌ Пожалуйста, введите только число (например: 50)")
        return
    
    await state.update_data(square_meters=message.text)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="2-3 месяца", callback_data="deadline_2-3")],
        [InlineKeyboardButton(text="4-5 месяцев", callback_data="deadline_4-5")],
        [InlineKeyboardButton(text="Полгода", callback_data="deadline_6")],
        [InlineKeyboardButton(text="Полгода и более", callback_data="deadline_6+")]
    ])
    
    text = (
        "Вопрос 5 из 5\n"
        "Какие сроки на ремонт?\n\n"
        "▰▰▰▰▰\n"
        "Расчёт почти готов (99%)"
    )
    
    msg = await message.answer(text, reply_markup=keyboard)
    await state.update_data(last_message_id=msg.message_id)
    await state.set_state(Form.deadline)

@dp.callback_query(Form.deadline, F.data.startswith("deadline_"))
async def process_deadline(callback: types.CallbackQuery, state: FSMContext):
    deadline_mapping = {
        "deadline_2-3": "2-3 месяца",
        "deadline_4-5": "4-5 месяцев",
        "deadline_6": "Полгода",
        "deadline_6+": "Полгода и более"
    }
    
    await state.update_data(deadline=deadline_mapping[callback.data])
    
    # Автоматически переходим к следующему шагу
    
    # Получаем имя пользователя
    user_name = callback.from_user.first_name or "Пользователь"
    await state.update_data(user_name=user_name)
    
    # Вычисляем дату через 3 дня
    future_date = datetime.now() + timedelta(days=3)
    date_str = future_date.strftime("%d.%m.%Y")
    
    # Базовый текст сообщения
    base_text = (
        f"{user_name},\n\n"
        f"Ваш расчет стоимости почти готов!\n\n"
        f"Закрепим за номером стоимость, бесплатную консультацию и разбор планировки дизайнером. Разбор с дизайнером действителен до {date_str}."
    )
    
    # Анимация "бот думает" - меняется нижняя часть сообщения
    thinking_messages = [
        "💬 Собираю данные для точного расчета стоимости ремонта",
        "💬 Анализирую введенные данные",
        "💬 Начинаю анализ ваших критериев",
        "💬 Начинаю анализ ваших критериев\n💬 Делаю расчет по вашим критериям",  # Сначала п.3, потом добавляется 3.1
        "💬 Сравниваю цены на материалы",
        "💬 Сверяю объем работ со сроками",
        "💬 Все внимательно проверяю, оптимизирую ✅"
    ]
    
    # Отправляем первое сообщение с базовым текстом и первой анимацией
    main_msg = await callback.message.answer(f"{base_text}\n\n{thinking_messages[0]}")
    await asyncio.sleep(1.5)
    
    # Редактируем сообщение, меняя только нижнюю часть с анимацией
    for thinking_text in thinking_messages[1:]:
        try:
            await main_msg.edit_text(f"{base_text}\n\n{thinking_text}")
        except Exception as e:
            # Игнорируем ошибку "message is not modified"
            if "message is not modified" not in str(e):
                logging.error(f"Failed to edit message: {e}")
                # Если редактирование не удалось, удаляем старое и отправляем новое
                try:
                    await main_msg.delete()
                except:
                    pass
                main_msg = await callback.message.answer(f"{base_text}\n\n{thinking_text}")
        await asyncio.sleep(1.5)
    
    # Создаем обычную клавиатуру с кнопкой для запроса контакта
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅Узнать стоимость", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    # Удаляем старое сообщение с анимацией и отправляем новое с клавиатурой
    # Примечание: нельзя редактировать сообщение с ReplyKeyboardMarkup, поэтому удаляем старое и отправляем новое
    try:
        await main_msg.delete()
    except Exception as e:
        logging.error(f"Failed to delete old message: {e}")
    
    # Отправляем новое сообщение с клавиатурой
    new_msg = await callback.message.answer(base_text, reply_markup=keyboard)
    await state.update_data(last_message_id=new_msg.message_id)
    
    await state.set_state(Form.phone)
    await callback.answer()

@dp.callback_query(Form.consent, F.data == "consent_yes")
async def process_consent(callback: types.CallbackQuery, state: FSMContext):
    # Получаем имя пользователя
    user_name = callback.from_user.first_name or "Пользователь"
    
    # Вычисляем дату через 3 дня
    future_date = datetime.now() + timedelta(days=3)
    date_str = future_date.strftime("%d.%m.%Y")
    
    text = (
        f"{user_name},\n\n"
        f"Ваш расчет стоимости почти готов!\n\n"
        f"Закрепим за номером стоимость, бесплатную консультацию и разбор планировки дизайнером. "
        f"Разбор с дизайнером действителен до {date_str}."
    )
    
    # Создаем обычную клавиатуру с кнопкой для запроса контакта
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅Узнать стоимость", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    msg = await callback.message.answer(text, reply_markup=keyboard)
    await state.update_data(last_message_id=msg.message_id, user_name=user_name)
    await state.set_state(Form.phone)
    await callback.answer()

@dp.message(Form.phone, F.contact)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    
    # Собираем все данные
    data = await state.get_data()
    user_name = data.get('user_name', message.from_user.first_name or 'Пользователь')
    
    # Финальное сообщение
    final_text = (
        f"{user_name}, наш менеджер может связаться для уточнения деталей.\n\n"
        "Чтобы предоставить более точный расчет.\n\n"
        "Пожалуйста, оставайтесь на связи 😊"
    )
    
    await message.answer(final_text, reply_markup=ReplyKeyboardRemove())
    username = f"@{message.from_user.username}" if message.from_user.username else "Не указан"
    
    # Формируем сообщение для админского чата
    admin_message = (
        "✨ Получена новая заявка\n"
        f"Имя: {user_name}\n"
        f"Телефон: {phone}\n"
        f"Username: {username}\n"
        f"Недвижимость: {data.get('property_type', 'Не указано')}\n"
        f"Ремонт: {data.get('repair_type', 'Не указано')}\n"
        f"Тип ремонта: {data.get('style_type', 'Не указано')}\n"
        f"Метраж: {data.get('square_meters', 'Не указано')} м²\n"
        f"Сроки: {data.get('deadline', 'Не указано')}"
    )
    
    # Отправляем в админский чат
    await bot.send_message(CHAT_ID, admin_message)
    
    # Очищаем состояние
    await state.clear()
    # Отменяем напоминания, так как пользователь завершил опрос
    cancel_reminders(message.from_user.id)

# Запуск бота
async def main():
    logging.info("Starting bot...")
    logging.info(f"Bot token: {BOT_TOKEN[:10]}...")
    logging.info(f"Chat ID: {CHAT_ID}")
    logging.info(f"Admin IDs: {ADMIN_IDS}")
    logging.info("Telegram API proxy: enabled" if _proxy else "Telegram API proxy: disabled")
    
    # Проверяем регистрацию обработчиков
    try:
        # Получаем количество зарегистрированных обработчиков
        message_handlers = [h for h in dp.message.handlers]
        callback_handlers = [h for h in dp.callback_query.handlers]
        total_handlers = len(message_handlers) + len(callback_handlers)
        logging.info(f"Registered handlers: {total_handlers} (messages: {len(message_handlers)}, callbacks: {len(callback_handlers)})")
    except Exception as e:
        logging.error(f"Error checking handlers: {e}")
    
    # Очищаем старые обновления и получаем информацию о боте
    try:
        bot_info = await bot.get_me()
        logging.info(f"Bot info: @{bot_info.username} ({bot_info.id}) - {bot_info.first_name}")
        
        # Очищаем pending updates
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Webhook deleted and pending updates dropped")
    except Exception as e:
        logging.error(f"Error getting bot info or clearing updates: {e}")
    
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())

