import asyncio
import logging
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, FSInputFile

# Загружаем переменные окружения
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN", "7884349748:AAEZC82Nd72L1eR1rhupuDWihjWdEKG4bd8")
CHAT_ID = int(os.getenv("CHAT_ID", "-1003650005079"))
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "765740972,6933111964").split(",")]

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния FSM
class Form(StatesGroup):
    property_type = State()
    repair_type = State()
    style_type = State()
    square_meters = State()
    deadline = State()
    consent = State()
    phone = State()

class AdminStates(StatesGroup):
    waiting_for_pd_document = State()

# Хранилище для документа о ПД (в продакшене использовать БД)
# type может быть "photo" или "document"
pd_document = {"file_id": None, "type": None}

# ============= АДМИНСКИЕ КОМАНДЫ =============

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return
    
    # Формируем клавиатуру в зависимости от наличия документа
    keyboard_buttons = [
        [InlineKeyboardButton(text="📎 Загрузить документ ПД", callback_data="admin_upload_pd")]
    ]
    
    if pd_document["file_id"]:
        status_text = f"📄 Документ ПД загружен ({pd_document['type']})"
        keyboard_buttons.append([InlineKeyboardButton(text="🗑️ Удалить документ ПД", callback_data="admin_delete_pd")])
    else:
        status_text = "📄 Документ ПД не загружен"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    text = f"🔐 <b>Админ-панель</b>\n\n{status_text}\n\nВыберите действие:"
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data == "admin_upload_pd")
async def admin_upload_pd_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📎 Отправьте фото или PDF документ для согласия на обработку ПД.\n\n"
        "Этот файл будет прикреплен к сообщению о согласии."
    )
    await state.set_state(AdminStates.waiting_for_pd_document)
    await callback.answer()

@dp.message(AdminStates.waiting_for_pd_document, F.photo | F.document)
async def handle_admin_upload(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    
    if message.photo:
        pd_document["file_id"] = message.photo[-1].file_id
        pd_document["type"] = "photo"
        await message.answer("✅ Фото успешно загружено и будет прикреплено к сообщению о ПД.")
    elif message.document:
        if message.document.mime_type == "application/pdf":
            pd_document["file_id"] = message.document.file_id
            pd_document["type"] = "document"
            await message.answer("✅ PDF документ успешно загружен и будет прикреплен к сообщению о ПД.")
        else:
            await message.answer("❌ Поддерживаются только PDF документы.")
    
    await state.clear()

@dp.callback_query(F.data == "admin_delete_pd")
async def admin_delete_pd_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    if pd_document["file_id"]:
        pd_document["file_id"] = None
        pd_document["type"] = None
        
        # Обновляем админ-панель
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📎 Загрузить документ ПД", callback_data="admin_upload_pd")]
        ])
        text = "🔐 <b>Админ-панель</b>\n\n✅ Документ ПД успешно удален.\n\n📄 Документ ПД не загружен\n\nВыберите действие:"
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("Документ удален", show_alert=True)
    else:
        await callback.answer("❌ Документ ПД не загружен.", show_alert=True)

# ============= ОСНОВНОЙ СЦЕНАРИЙ БОТА =============

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Рассчитать стоимость", callback_data="start_calc")]
    ])
    
    welcome_text = (
        "Привет! Я бот компании Domastroi — мы разрабатываем качественные проекты и делаем ремонт под ключ.\n\n"
        "Репутация: 15 лет, 8 стран, 2000+ проектов, формат «под ключ в одной компании» и очень качественные чертежи без ошибок. Мы сделаем такой интерьер, которым вы будете гордиться, ваши друзья - завидовать, а ваши дети будут расти жизнерадостными и здоровыми.\n\n"
        "Сделаем рассчет?\n"
        "Это займет всего несколько минут, и вы получите:\n\n"
        "🏆 Расчет стоимости ремонта\n"
        "🏆 Пошаговый план ремонта от А до Я\n"
        "🏆 Консультацию дизайнера по вашей планировке\n\n"
        "Готовы начать?"
    )
    
    # Отправляем фото с текстом
    photo_path = "images/dfegvjedrfgvf.jpg"
    try:
        await message.answer_photo(
            photo=FSInputFile(photo_path),
            caption=welcome_text,
            reply_markup=keyboard
        )
    except FileNotFoundError:
        # Если файл не найден, отправляем только текст
        await message.answer(welcome_text, reply_markup=keyboard)

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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅Согласие на обработку ПД", callback_data="consent_yes")]
    ])
    
    text = "Кстати, продолжая, вы даёте согласие на обработку персональных данных. 🤝"
    
    # Проверяем, есть ли загруженный документ
    if pd_document["file_id"]:
        if pd_document["type"] == "photo":
            msg = await callback.message.answer_photo(
                photo=pd_document["file_id"],
                caption=text,
                reply_markup=keyboard
            )
        else:  # document
            msg = await callback.message.answer_document(
                document=pd_document["file_id"],
                caption=text,
                reply_markup=keyboard
            )
    else:
        msg = await callback.message.answer(text, reply_markup=keyboard)
    
    await state.update_data(last_message_id=msg.message_id)
    await state.set_state(Form.consent)
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
        "💬 Начинаю анализ ваших критериев\n💬 Делаю расчет по вашим критериям",
        "💬 Сравниваю цены на материалы",
        "💬 Сверяю объем работ со сроками",
        "💬 Все внимательно проверяю, оптимизирую ✅"
    ]
    
    # Отправляем первое сообщение с базовым текстом и первой анимацией
    main_msg = await message.answer(f"{base_text}\n\n{thinking_messages[0]}")
    await asyncio.sleep(1.5)
    
    # Редактируем сообщение, меняя только нижнюю часть с анимацией
    for thinking_text in thinking_messages[1:]:
        await main_msg.edit_text(f"{base_text}\n\n{thinking_text}")
        await asyncio.sleep(1.5)
    
    # Финальное сообщение без анимации
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

# Запуск бота
async def main():
    logging.info("Starting bot...")
    logging.info(f"Bot token: {BOT_TOKEN[:10]}...")
    logging.info(f"Chat ID: {CHAT_ID}")
    logging.info(f"Admin IDs: {ADMIN_IDS}")
    
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

