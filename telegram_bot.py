from datetime import datetime
import telebot
import time
from sqlite_database import db
from categories import CATEGORIES, detect_category
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import API_TOKEN
import charts  # Для визуальной статистики

# Отключаем предупреждения matplotlib
import warnings
warnings.filterwarnings("ignore")

bot = telebot.TeleBot(API_TOKEN)

# === ДОБАВЛЕНО: Константы для редактирования операций ===
EDIT_OPERATION_PREFIX = "edit_op_"
DELETE_OPERATION_PREFIX = "delete_op_"
CONFIRM_DELETE_PREFIX = "confirm_delete_"
EDIT_AMOUNT_PREFIX = "edit_amount_"
EDIT_DESC_PREFIX = "edit_desc_"
EDIT_TYPE_PREFIX = "edit_type_"
EDIT_CATEGORY_PREFIX = "edit_category_"
SET_CATEGORY_PREFIX = "set_category_"

# === ДОБАВЛЕНО: Система состояний для редактирования ===
edit_states = {}
EDIT_STATE_TIMEOUT = 300  # 5 минут

def set_edit_state(user_id, action, operation_id):
    """Устанавливает состояние редактирования для пользователя"""
    edit_states[user_id] = {
        'action': action,
        'operation_id': operation_id,
        'timestamp': time.time()
    }

def clear_edit_state(user_id):
    """Очищает состояние редактирования"""
    if user_id in edit_states:
        del edit_states[user_id]

def get_edit_state(user_id):
    """Возвращает состояние редактирования пользователя"""
    # Очищаем устаревшие состояния
    current_time = time.time()
    expired_users = [uid for uid, state in edit_states.items() 
                    if current_time - state['timestamp'] > EDIT_STATE_TIMEOUT]
    for uid in expired_users:
        del edit_states[uid]
    
    return edit_states.get(user_id)

# Создаем клавиатуру с кнопками для главного меню
def create_main_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("📋 Список операций", callback_data="list_operations"),
        InlineKeyboardButton("📊 Статистика", callback_data="show_stats")
    )
    keyboard.row(
        InlineKeyboardButton("💰 Баланс", callback_data="show_balance"),
        InlineKeyboardButton("📅 За месяц", callback_data="show_month")
    )
    keyboard.row(
        InlineKeyboardButton("📂 Категории", callback_data="show_categories")
    )
    return keyboard

# Создаем клавиатуру для быстрых действий после операций
def create_quick_actions_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("📋 Список", callback_data="list_operations"),
        InlineKeyboardButton("📊 Статистика", callback_data="show_stats")
    )
    keyboard.row(
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )
    return keyboard

# Клавиатура для управления категориями
def create_categories_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("➕ Добавить категорию", callback_data="add_category"),
        InlineKeyboardButton("📋 Мои категории", callback_data="my_categories")
    )
    keyboard.row(
        InlineKeyboardButton("🗑 Удалить категорию", callback_data="delete_category"),
        InlineKeyboardButton("📖 Стандартные", callback_data="standard_categories")
    )
    keyboard.row(
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )
    return keyboard

# Клавиатура для статистики и отчетов
def create_stats_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("📅 За месяц", callback_data="show_month"),
        InlineKeyboardButton("📊 Общая", callback_data="show_stats")
    )
    keyboard.row(
        InlineKeyboardButton("📈 Диаграмма", callback_data="show_chart"),
        InlineKeyboardButton("📋 История", callback_data="show_history")
    )
    keyboard.row(
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )
    return keyboard

# === ДОБАВЛЕНО: Клавиатура для списка операций с редактированием ===
def create_operations_keyboard(operations, page=0, operations_per_page=10):
    """Создает клавиатуру для списка операций с пагинацией и действиями"""
    keyboard = InlineKeyboardMarkup()
    
    # Показываем операции для текущей страницы
    start_idx = page * operations_per_page
    end_idx = start_idx + operations_per_page
    current_ops = operations[start_idx:end_idx]
    
    for i, op in enumerate(current_ops):
        op_index = start_idx + i
        op_type_icon = "✅" if op['type'] == 'income' else "🔴"
        category_info = f" [{op['category']}]" if op['type'] == 'expense' else ""
        btn_text = f"{op_type_icon} {op['amount']} руб. - {op['description'][:20]}{category_info}"
        
        keyboard.row(
            InlineKeyboardButton(
                btn_text, 
                callback_data=f"{EDIT_OPERATION_PREFIX}{op['id']}"
            )
        )
    
    # Кнопки пагинации
    pagination_row = []
    if page > 0:
        pagination_row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"list_page_{page-1}"))
    
    if end_idx < len(operations):
        pagination_row.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"list_page_{page+1}"))
    
    if pagination_row:
        keyboard.row(*pagination_row)
    
    # Кнопка возврата
    keyboard.row(InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
    return keyboard

# === ДОБАВЛЕНО: Клавиатура для редактирования операции ===
def create_edit_operation_keyboard(operation_id):
    """Создает клавиатуру для редактирования операции"""
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("✏️ Изменить сумму", callback_data=f"{EDIT_AMOUNT_PREFIX}{operation_id}"),
        InlineKeyboardButton("📝 Изменить описание", callback_data=f"{EDIT_DESC_PREFIX}{operation_id}")
    )
    keyboard.row(
        InlineKeyboardButton("🔄 Изменить тип", callback_data=f"{EDIT_TYPE_PREFIX}{operation_id}"),
        InlineKeyboardButton("📂 Изменить категорию", callback_data=f"{EDIT_CATEGORY_PREFIX}{operation_id}")
    )
    keyboard.row(
        InlineKeyboardButton("🗑 Удалить операцию", callback_data=f"{DELETE_OPERATION_PREFIX}{operation_id}"),
    )
    keyboard.row(
        InlineKeyboardButton("📋 Назад к списку", callback_data="list_operations"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )
    return keyboard

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = """
💼 <b>Бот для учета финансов</b>

<b>Добавить трату:</b>
<code>500 еда</code>
<code>1500 бензин</code>

<b>Добавить доход:</b>
<code>+50000 зарплата</code>

<b>📂 Персональные категории:</b>
<code>/add_category Еда продукты,магазин</code>
<code>/my_categories</code>
<code>/delete_category Еда</code>

<b>📊 Визуальная статистика:</b>
<code>/chart</code> - диаграмма расходов
<code>/history</code> - история по месяцам

<b>📈 Команды:</b>
/list - все операции
/balance - баланс  
/stats - статистика
/month - за месяц
/categories - все категории
/clear - очистить историю
    """
    bot.reply_to(message, welcome_text, parse_mode='HTML', reply_markup=create_main_keyboard())

# Обработчик нажатий на кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    
    try:
        if call.data == "list_operations":
            operations = db.get_operations(user_id)
            
            if not operations:
                bot.answer_callback_query(call.id, "У вас пока нет операций.")
                return
            
            operations_list = "📊 <b>Ваши операции:</b>\n\n"
            operations_list += "Нажмите на операцию для редактирования:\n\n"
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text=operations_list,
                parse_mode='HTML',
                reply_markup=create_operations_keyboard(operations)
            )
            bot.answer_callback_query(call.id)
        
        elif call.data.startswith("list_page_"):
            # Обработка пагинации
            page = int(call.data.replace("list_page_", ""))
            operations = db.get_operations(user_id)
            
            operations_list = "📊 <b>Ваши операции:</b>\n\n"
            operations_list += "Нажмите на операцию для редактирования:\n\n"
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=operations_list,
                parse_mode='HTML',
                reply_markup=create_operations_keyboard(operations, page)
            )
            bot.answer_callback_query(call.id)
        
        # === ДОБАВЛЕНО: Обработчики редактирования операций ===
        elif call.data.startswith(EDIT_OPERATION_PREFIX):
            # Редактирование операции - показываем меню действий
            operation_id = int(call.data.replace(EDIT_OPERATION_PREFIX, ""))
            operation = db.get_operation_by_id(operation_id)
            
            if not operation:
                bot.answer_callback_query(call.id, "❌ Операция не найдена")
                return
            
            show_operation_edit_menu(call, operation)
        
        elif call.data.startswith(EDIT_AMOUNT_PREFIX):
            # Изменение суммы
            operation_id = int(call.data.replace(EDIT_AMOUNT_PREFIX, ""))
            set_edit_state(user_id, 'edit_amount', operation_id)
            
            bot.answer_callback_query(call.id)
            bot.send_message(
                chat_id=call.message.chat.id,
                text="💵 <b>Введите новую сумму:</b>\n\nПример: <code>1500</code> или <code>+5000</code>",
                parse_mode='HTML'
            )
        
        elif call.data.startswith(EDIT_DESC_PREFIX):
            # Изменение описания
            operation_id = int(call.data.replace(EDIT_DESC_PREFIX, ""))
            set_edit_state(user_id, 'edit_desc', operation_id)
            
            bot.answer_callback_query(call.id)
            bot.send_message(
                chat_id=call.message.chat.id,
                text="📝 <b>Введите новое описание:</b>\n\nПример: <code>продукты в Пятерочке</code>",
                parse_mode='HTML'
            )
        
        elif call.data.startswith(EDIT_TYPE_PREFIX):
            # Изменение типа операции (доход/расход)
            operation_id = int(call.data.replace(EDIT_TYPE_PREFIX, ""))
            operation = db.get_operation_by_id(operation_id)
            
            if not operation:
                bot.answer_callback_query(call.id, "❌ Операция не найдена")
                return
            
            new_type = 'income' if operation['type'] == 'expense' else 'expense'
            if db.update_operation(operation_id, operation_type=new_type):
                # Обновляем категорию при смене типа
                new_category = 'доход' if new_type == 'income' else db.detect_category(user_id, operation['description'])
                db.update_operation(operation_id, category=new_category)
                
                bot.answer_callback_query(call.id, "✅ Тип операции изменен!")
                
                # Показываем обновленную операцию
                updated_op = db.get_operation_by_id(operation_id)
                show_operation_edit_menu(call, updated_op)
            else:
                bot.answer_callback_query(call.id, "❌ Ошибка при изменении типа")
        
        elif call.data.startswith(EDIT_CATEGORY_PREFIX):
            # Изменение категории
            operation_id = int(call.data.replace(EDIT_CATEGORY_PREFIX, ""))
            operation = db.get_operation_by_id(operation_id)
            
            if not operation or operation['type'] == 'income':
                bot.answer_callback_query(call.id, "❌ Нельзя изменить категорию для доходов")
                return
            
            # Показываем доступные категории
            categories = db.get_all_categories(user_id)
            categories_text = "📂 <b>Выберите новую категорию:</b>\n\n"
            
            keyboard = InlineKeyboardMarkup()
            for category_name in categories.keys():
                keyboard.row(InlineKeyboardButton(
                    f"📁 {category_name}", 
                    callback_data=f"{SET_CATEGORY_PREFIX}{operation_id}_{category_name}"
                ))
            
            keyboard.row(InlineKeyboardButton("↩️ Назад", callback_data=f"{EDIT_OPERATION_PREFIX}{operation_id}"))
            
            bot.answer_callback_query(call.id)
            bot.send_message(
                chat_id=call.message.chat.id,
                text=categories_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        
        elif call.data.startswith(SET_CATEGORY_PREFIX):
            # Установка новой категории
            parts = call.data.replace(SET_CATEGORY_PREFIX, "").split("_")
            operation_id = int(parts[0])
            category_name = parts[1]
            
            if db.update_operation(operation_id, category=category_name):
                bot.answer_callback_query(call.id, f"✅ Категория изменена на: {category_name}")
                
                # Возвращаем к редактированию операции
                operation = db.get_operation_by_id(operation_id)
                show_operation_edit_menu(call, operation)
            else:
                bot.answer_callback_query(call.id, "❌ Ошибка при изменении категории")
        
        elif call.data.startswith(DELETE_OPERATION_PREFIX):
            # Подтверждение удаления
            operation_id = int(call.data.replace(DELETE_OPERATION_PREFIX, ""))
            operation = db.get_operation_by_id(operation_id)
            
            if not operation:
                bot.answer_callback_query(call.id, "❌ Операция не найдена")
                return
            
            confirm_keyboard = InlineKeyboardMarkup()
            confirm_keyboard.row(
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"{CONFIRM_DELETE_PREFIX}{operation_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"{EDIT_OPERATION_PREFIX}{operation_id}")
            )
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"🗑 <b>Подтвердите удаление:</b>\n\n{operation['amount']} руб. - {operation['description']}",
                parse_mode='HTML',
                reply_markup=confirm_keyboard
            )
            bot.answer_callback_query(call.id)
        
        elif call.data.startswith(CONFIRM_DELETE_PREFIX):
            # Удаление операции
            operation_id = int(call.data.replace(CONFIRM_DELETE_PREFIX, ""))
            
            if db.delete_operation(operation_id):
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="✅ Операция удалена!",
                    reply_markup=create_main_keyboard()
                )
            else:
                bot.answer_callback_query(call.id, "❌ Ошибка при удалении")
        
        # === КОНЕЦ ДОБАВЛЕННЫХ ОБРАБОТЧИКОВ ===
        
        elif call.data == "show_stats":
            operations = db.get_operations(user_id)
            
            expenses_by_category = {}
            for op in operations:
                if op['type'] == 'expense':
                    category = op.get('category', 'другое')
                    amount = op.get('amount', 0)
                    
                    if category not in expenses_by_category:
                        expenses_by_category[category] = 0
                    expenses_by_category[category] += amount
            
            if not expenses_by_category:
                bot.answer_callback_query(call.id, "У вас пока нет расходов для статистики.")
                return
            
            sorted_categories = sorted(expenses_by_category.items(), key=lambda x: x[1], reverse=True)
            
            stats_text = "📊 <b>Статистика по категориям:</b>\n\n"
            total_expenses = sum(expenses_by_category.values())
            
            for category, amount in sorted_categories:
                percentage = (amount / total_expenses) * 100 if total_expenses > 0 else 0
                stats_text += f"• {category}: <b>{amount:,} руб.</b> ({percentage:.1f}%)\n"
            
            stats_text += f"\n💵 <b>Всего расходов: {total_expenses:,} руб.</b>"
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text=stats_text,
                parse_mode='HTML',
                reply_markup=create_stats_keyboard()
            )
            bot.answer_callback_query(call.id)
        
        elif call.data == "show_balance":
            operations = db.get_operations(user_id)
            
            total_income = sum(op['amount'] for op in operations if op['type'] == 'income')
            total_expenses = sum(op['amount'] for op in operations if op['type'] == 'expense')
            balance = total_income - total_expenses
            
            balance_text = f"""
💰 <b>Ваш финансовый баланс</b>

📈 Доходы: <b>+{total_income:,} руб.</b>
📉 Расходы: <b>-{total_expenses:,} руб.</b>
———————————————
💵 Баланс: <b>{balance:,} руб.</b>
            """
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text=balance_text,
                parse_mode='HTML',
                reply_markup=create_main_keyboard()
            )
            bot.answer_callback_query(call.id)
        
        elif call.data == "show_month":  
            monthly_ops = db.get_monthly_operations(user_id)
            
            if not monthly_ops:
                bot.answer_callback_query(call.id, "За текущий месяц операций нет.")
                return
            
            expenses_by_category = {}
            monthly_income = 0
            monthly_expenses = 0
            
            for op in monthly_ops:
                if op['type'] == 'income':
                    monthly_income += op['amount']
                else:
                    monthly_expenses += op['amount']
                    category = op.get('category', 'другое')
                    if category not in expenses_by_category:
                        expenses_by_category[category] = 0
                    expenses_by_category[category] += op['amount']
            
            now = datetime.now()
            month_name = now.strftime("%B %Y")
            
            stats_text = f"📅 <b>Статистика за {month_name}:</b>\n\n"
            stats_text += f"📈 Доходы: <b>+{monthly_income:,} руб.</b>\n"
            stats_text += f"📉 Расходы: <b>-{monthly_expenses:,} руб.</b>\n"
            stats_text += f"💵 Баланс: <b>{monthly_income - monthly_expenses:,} руб.</b>\n\n"
            
            if expenses_by_category:
                stats_text += "<b>Расходы по категориям:</b>\n"
                sorted_categories = sorted(expenses_by_category.items(), key=lambda x: x[1], reverse=True)
                
                for category, amount in sorted_categories:
                    percentage = (amount / monthly_expenses) * 100 if monthly_expenses > 0 else 0
                    stats_text += f"• {category}: <b>{amount:,} руб.</b> ({percentage:.1f}%)\n"
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text=stats_text,
                parse_mode='HTML',
                reply_markup=create_stats_keyboard()
            )
            bot.answer_callback_query(call.id)
        
        elif call.data == "show_categories":
            categories_text = "📂 <b>Управление категориями</b>\n\n"
            categories_text += "Здесь вы можете настроить свои персональные категории для автоматического определения трат."
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text=categories_text,
                parse_mode='HTML',
                reply_markup=create_categories_keyboard()
            )
            bot.answer_callback_query(call.id)
        
        elif call.data == "add_category":
            help_text = """
<b>Добавление категории</b>

Используйте команду:
<code>/add_category Название ключевые,слова,через,запятую</code>

<b>Пример:</b>
<code>/add_category Фриланс заказ,проект,удаленка</code>
<code>/add_category Еда продукты,магазин,молоко,хлеб</code>

После добавления категории, при вводе траты содержащей ключевые слова, будет автоматически определяться ваша категория.
            """
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text=help_text,
                parse_mode='HTML',
                reply_markup=create_categories_keyboard()
            )
            bot.answer_callback_query(call.id)
        
        elif call.data == "my_categories":
            categories = db.get_user_categories(user_id)
            
            if not categories:
                categories_text = "📂 <b>Ваши персональные категории</b>\n\n"
                categories_text += "У вас пока нет персональных категорий.\n\n"
                categories_text += "Добавьте их через меню или командой /add_category"
            else:
                categories_text = "📂 <b>Ваши персональные категории:</b>\n\n"
                
                for category_name, keywords in categories.items():
                    categories_text += f"• <b>{category_name}</b>: {', '.join(keywords)}\n"
                
                categories_text += f"\n📊 Всего категорий: {len(categories)}"
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text=categories_text,
                parse_mode='HTML',
                reply_markup=create_categories_keyboard()
            )
            bot.answer_callback_query(call.id)
        
        elif call.data == "delete_category":
            help_text = """
<b>Удаление категории</b>

Используйте команду:
<code>/delete_category Название_категории</code>

<b>Пример:</b>
<code>/delete_category Фриланс</code>

Чтобы посмотреть список ваших категорий, нажмите «Мои категории».
            """
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text=help_text,
                parse_mode='HTML',
                reply_markup=create_categories_keyboard()
            )
            bot.answer_callback_query(call.id)
        
        elif call.data == "standard_categories":
            categories_text = "📖 <b>Стандартные категории:</b>\n\n"
            
            for category, keywords in CATEGORIES.items():
                categories_text += f"• <b>{category}</b>: {', '.join(keywords[:3])}...\n"
            
            categories_text += "\nℹ️ Эти категории используются, если не найдено совпадение в ваших персональных категориях."
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text=categories_text,
                parse_mode='HTML',
                reply_markup=create_categories_keyboard()
            )
            bot.answer_callback_query(call.id)
        
        elif call.data == "show_chart":
            bot.answer_callback_query(call.id, "🔄 Создаю диаграмму...")
            
            class FakeMessage:
                def __init__(self, chat_id, user_id):
                    self.chat = type('Chat', (), {'id': chat_id})()
                    self.from_user = type('User', (), {'id': user_id})()
            
            fake_msg = FakeMessage(call.message.chat.id, user_id)
            show_chart(fake_msg)
        
        elif call.data == "show_history":
            bot.answer_callback_query(call.id, "🔄 Создаю график истории...")
            
            class FakeMessage:
                def __init__(self, chat_id, user_id):
                    self.chat = type('Chat', (), {'id': chat_id})()
                    self.from_user = type('User', (), {'id': user_id})()
            
            fake_msg = FakeMessage(call.message.chat.id, user_id)
            show_history_chart(fake_msg)
        
        elif call.data == "main_menu":
            welcome_text = """
💼 <b>Бот для учета финансов</b>

<b>Добавить трату:</b>
<code>500 еда</code>
<code>1500 бензин</code>

<b>Добавить доход:</b>
<code>+50000 зарплата</code>

<b>📂 Персональные категории:</b>
<code>/add_category Еда продукты,магазин</code>
<code>/my_categories</code>
<code>/delete_category Еда</code>

<b>📊 Визуальная статистика:</b>
<code>/chart</code> - диаграмма расходов
<code>/history</code> - история по месяцам

<b>📈 Команды:</b>
/list - все операции
/balance - баланс  
/stats - статистика
/month - за месяц
/categories - все категории
/clear - очистить историю
            """
            
            bot.send_message(
                chat_id=call.message.chat.id,
                text=welcome_text,
                parse_mode='HTML',
                reply_markup=create_main_keyboard()
            )
            bot.answer_callback_query(call.id)
    
    except Exception as e:
        print(f"Ошибка в callback: {e}")
        import traceback
        traceback.print_exc()
        bot.answer_callback_query(call.id, "❌ Произошла ошибка")

# === ДОБАВЛЕНО: Вспомогательные функции для редактирования ===
def show_operation_edit_menu(call, operation):
    """Показывает меню редактирования операции"""
    op_type_icon = "✅" if operation['type'] == 'income' else "🔴"
    category_info = f" [{operation['category']}]" if operation['type'] == 'expense' else ""
    
    operation_text = f"""
✏️ <b>Редактирование операции:</b>

{op_type_icon} <b>{operation['amount']} руб.</b> - {operation['description']}{category_info}

📅 <i>{operation['created_at']}</i>

Выберите действие:
    """
    
    if hasattr(call.message, 'message_id'):
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=operation_text,
            parse_mode='HTML',
            reply_markup=create_edit_operation_keyboard(operation['id'])
        )
    else:
        bot.send_message(
            chat_id=call.message.chat.id,
            text=operation_text,
            parse_mode='HTML',
            reply_markup=create_edit_operation_keyboard(operation['id'])
        )

def show_updated_operation(chat_id, operation):
    """Показывает обновленную операцию с кнопками редактирования"""
    op_type_icon = "✅" if operation['type'] == 'income' else "🔴"
    category_info = f" [{operation['category']}]" if operation['type'] == 'expense' else ""
    
    operation_text = f"""
✏️ <b>Операция обновлена:</b>

{op_type_icon} <b>{operation['amount']} руб.</b> - {operation['description']}{category_info}

📅 <i>{operation['created_at']}</i>

Выберите действие:
    """
    
    bot.send_message(
        chat_id=chat_id,
        text=operation_text,
        parse_mode='HTML',
        reply_markup=create_edit_operation_keyboard(operation['id'])
    )

# === ДОБАВЛЕНО: Обработчик всех сообщений с поддержкой редактирования ===
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()

    # Проверяем, есть ли активное состояние редактирования
    edit_state = get_edit_state(user_id)
    if edit_state:
        handle_edit_input(message, edit_state)
        return

    # Если нет состояния редактирования, обрабатываем как новую операцию
    add_operation_cmd(message)

def handle_edit_input(message, edit_state):
    """Обрабатывает ввод данных для редактирования операции"""
    user_id = message.from_user.id
    text = message.text.strip()
    operation_id = edit_state['operation_id']
    action = edit_state['action']
    
    try:
        if action == 'edit_amount':
            # Обрабатываем ввод суммы
            if text.startswith('+'):
                new_amount = int(text[1:])
                operation_type = 'income'
            else:
                new_amount = int(text)
                operation_type = 'expense'
            
            if new_amount <= 0:
                bot.reply_to(message, "❌ Сумма должна быть положительной")
                return
            
            # Получаем текущую операцию для сохранения описания
            operation = db.get_operation_by_id(operation_id)
            if not operation:
                bot.reply_to(message, "❌ Операция не найдена")
                clear_edit_state(user_id)
                return
            
            # Обновляем операцию
            if db.update_operation(operation_id, amount=new_amount, operation_type=operation_type):
                # Обновляем категорию если тип изменился
                if operation_type != operation['type']:
                    new_category = 'доход' if operation_type == 'income' else db.detect_category(user_id, operation['description'])
                    db.update_operation(operation_id, category=new_category)
                
                clear_edit_state(user_id)
                bot.reply_to(message, f"✅ Сумма изменена на: {new_amount} руб.")
                
                # Показываем обновленную операцию
                updated_op = db.get_operation_by_id(operation_id)
                show_updated_operation(message.chat.id, updated_op)
            else:
                bot.reply_to(message, "❌ Ошибка при изменении суммы")
        
        elif action == 'edit_desc':
            # Обрабатываем ввод описания
            if len(text) == 0:
                bot.reply_to(message, "❌ Описание не может быть пустым")
                return
            
            # Получаем текущую операцию
            operation = db.get_operation_by_id(operation_id)
            if not operation:
                bot.reply_to(message, "❌ Операция не найдена")
                clear_edit_state(user_id)
                return
            
            # Обновляем описание и переопределяем категорию для расходов
            updates = {'description': text}
            if operation['type'] == 'expense':
                new_category = db.detect_category(user_id, text)
                updates['category'] = new_category
            
            if db.update_operation(operation_id, **updates):
                clear_edit_state(user_id)
                bot.reply_to(message, f"✅ Описание изменено на: {text}")
                
                # Показываем обновленную операцию
                updated_op = db.get_operation_by_id(operation_id)
                show_updated_operation(message.chat.id, updated_op)
            else:
                bot.reply_to(message, "❌ Ошибка при изменении описания")
    
    except ValueError:
        if action == 'edit_amount':
            bot.reply_to(message, "❌ Неверный формат суммы. Используйте: <code>500</code> или <code>+5000</code>", parse_mode='HTML')
        else:
            bot.reply_to(message, "❌ Произошла ошибка. Попробуйте еще раз.")
    except Exception as e:
        print(f"Ошибка при редактировании: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при обработке запроса")

def add_operation_cmd(message):
    """Добавляет новую операцию (оригинальная функция)"""
    user_id = message.from_user.id
    text = message.text.strip()

    try:
        if text.startswith('+'):
            operation_type = 'income'
            parts = text[1:].strip().split(' ', 1)
        else:
            operation_type = 'expense'
            parts = text.split(' ', 1)
        
        amount = int(parts[0])
        description = parts[1] if len(parts) > 1 else "без категории"

        db.add_operation(user_id, amount, description, operation_type)
        
        if operation_type == 'income':
            response = f"✅ Записал доход: {description} - +{amount} руб."
        else:
            # Используем новую функцию определения категории
            category = db.detect_category(user_id, description)
            response = f"🔴 Записал расход: {description} - {amount} руб. [{category}]"
        
        bot.reply_to(message, response, reply_markup=create_quick_actions_keyboard())

    except (ValueError, IndexError):
        bot.reply_to(message, '''Не понимаю формат. Используйте:
        
<b>Для расходов:</b> <code>500 еда</code>
<b>Для доходов:</b> <code>+50000 зарплата</code>''', parse_mode='HTML', reply_markup=create_main_keyboard())

# Остальные функции (команды) остаются без изменений...
# [Здесь должен быть остальной твой код: add_category_cmd, show_my_categories_cmd, и т.д.]
# Команды для работы с категориями
@bot.message_handler(commands=['add_category'])
def add_category_cmd(message):
    """Добавляет персональную категорию"""
    user_id = message.from_user.id
    text = message.text.strip()
    
    try:
        # Формат: /add_category Еда продукты,магазин,еда
        parts = text.split(' ', 2)
        if len(parts) < 3:
            raise ValueError
        
        category_name = parts[1]
        keywords = parts[2]
        
        if db.add_user_category(user_id, category_name, keywords):
            response = f"✅ Категория '{category_name}' добавлена!\n\n"
            response += f"Ключевые слова: {keywords}\n\n"
            response += "Теперь при добавлении трат с этими словами будет автоматически определяться ваша категория."
        else:
            response = f"❌ Категория '{category_name}' уже существует"
            
        bot.reply_to(message, response, reply_markup=create_categories_keyboard())
            
    except ValueError:
        bot.reply_to(message, '''<b>Неверный формат</b>

Используйте:
<code>/add_category Название ключевые,слова,через,запятую</code>

<b>Пример:</b>
<code>/add_category Фриланс заказ,проект,удаленка</code>
<code>/add_category Еда продукты,магазин,молоко,хлеб</code>''', parse_mode='HTML', reply_markup=create_categories_keyboard())

@bot.message_handler(commands=['my_categories'])
def show_my_categories_cmd(message):
    """Показывает персональные категории пользователя"""
    user_id = message.from_user.id
    categories = db.get_user_categories(user_id)
    
    if not categories:
        response = "📂 <b>Ваши персональные категории</b>\n\n"
        response += "У вас пока нет персональных категорий.\n\n"
        response += "Добавьте их через меню или командой:\n"
        response += "<code>/add_category Название ключевые,слова</code>"
    else:
        response = "📂 <b>Ваши персональные категории:</b>\n\n"
        
        for category_name, keywords in categories.items():
            response += f"• <b>{category_name}</b>: {', '.join(keywords)}\n"
        
        response += f"\n📊 Всего категорий: {len(categories)}"
        response += "\n\n⚙️ Управление: /add_category /delete_category"
    
    bot.reply_to(message, response, parse_mode='HTML', reply_markup=create_categories_keyboard())

@bot.message_handler(commands=['delete_category'])
def delete_category_cmd(message):
    """Удаляет персональную категорию"""
    user_id = message.from_user.id
    text = message.text.strip()
    
    try:
        # Формат: /delete_category Еда
        parts = text.split(' ', 1)
        if len(parts) < 2:
            raise ValueError
        
        category_name = parts[1]
        
        # Проверяем, существует ли категория
        user_categories = db.get_user_categories(user_id)
        if category_name not in user_categories:
            bot.reply_to(message, f"❌ Категория '{category_name}' не найдена.\n\nИспользуйте /my_categories чтобы посмотреть ваши категории.")
            return
            
        db.delete_user_category(user_id, category_name)
        response = f"🗑 Категория '{category_name}' удалена!"
        
        bot.reply_to(message, response, reply_markup=create_categories_keyboard())
            
    except ValueError:
        bot.reply_to(message, '''<b>Неверный формат</b>

Используйте:
<code>/delete_category Название_категории</code>

<b>Пример:</b>
<code>/delete_category Фриланс</code>

Посмотреть ваши категории: /my_categories''', parse_mode='HTML', reply_markup=create_categories_keyboard())

# Существующие команды
@bot.message_handler(commands=['categories'])
def show_categories_cmd(message):
    """Показывает меню управления категориями"""
    categories_text = "📂 <b>Управление категориями</b>\n\n"
    categories_text += "Здесь вы можете настроить свои персональные категории для автоматического определения трат."
    
    bot.reply_to(message, categories_text, parse_mode='HTML', reply_markup=create_categories_keyboard())

@bot.message_handler(commands=['stats'])
def show_stats_cmd(message):
    """Показывает статистику по категориям"""
    user_id = message.from_user.id
    operations = db.get_operations(user_id)
    
    expenses_by_category = {}
    
    for op in operations:
        if op['type'] == 'expense':
            category = op['category']
            amount = op['amount']
            
            if category not in expenses_by_category:
                expenses_by_category[category] = 0
            expenses_by_category[category] += amount
    
    if not expenses_by_category:
        bot.reply_to(message, "📊 У вас пока нет расходов для статистики.", reply_markup=create_main_keyboard())
        return
    
    sorted_categories = sorted(expenses_by_category.items(), key=lambda x: x[1], reverse=True)
    
    stats_text = "📊 <b>Статистика по категориям:</b>\n\n"
    total_expenses = sum(expenses_by_category.values())
    
    for category, amount in sorted_categories:
        percentage = (amount / total_expenses) * 100
        stats_text += f"• {category}: <b>{amount:,} руб.</b> ({percentage:.1f}%)\n"
    
    stats_text += f"\n💵 <b>Всего расходов: {total_expenses:,} руб.</b>"
    
    bot.reply_to(message, stats_text, parse_mode='HTML', reply_markup=create_stats_keyboard())

@bot.message_handler(commands=['list'])
def list_operations_cmd(message):
    user_id = message.from_user.id
    operations = db.get_operations(user_id)
    
    if not operations:
        bot.reply_to(message, "У вас пока нет операций.", reply_markup=create_main_keyboard())
        return
        
    operations_list = "📊 <b>Ваши операции:</b>\n\n"
    
    for op in operations:
        op_type = op.get('type', 'expense')
        category = op.get('category', 'другое')
        
        if op_type == 'income':
            operations_list += f"✅ +{op['amount']} руб. - {op['description']}\n"
        else:
            operations_list += f"🔴 {op['amount']} руб. - {op['description']} [{category}]\n"
    
    bot.reply_to(message, operations_list, parse_mode='HTML', reply_markup=create_main_keyboard())

@bot.message_handler(commands=['balance'])
def show_balance_cmd(message):
    user_id = message.from_user.id
    operations = db.get_operations(user_id)
    
    total_income = sum(op['amount'] for op in operations if op['type'] == 'income')
    total_expenses = sum(op['amount'] for op in operations if op['type'] == 'expense')
    balance = total_income - total_expenses
    
    balance_text = f"""
💰 <b>Ваш финансовый баланс</b>

📈 Доходы: <b>+{total_income:,} руб.</b>
📉 Расходы: <b>-{total_expenses:,} руб.</b>
———————————————
💵 Баланс: <b>{balance:,} руб.</b>
    """
    bot.reply_to(message, balance_text, parse_mode='HTML', reply_markup=create_main_keyboard())

@bot.message_handler(commands=['clear'])
def clear_operations_cmd(message):
    user_id = message.from_user.id
    db.clear_operations(user_id)
    bot.reply_to(message, "🗑 История операций очищена.", reply_markup=create_main_keyboard())

@bot.message_handler(commands=['myid'])
def show_my_id_cmd(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    bot.reply_to(message, f"🆔 Ваш user_id: {user_id}\n👤 Имя: {first_name}")

@bot.message_handler(commands=['debug'])
def debug_info_cmd(message):
    user_id = message.from_user.id
    operations = db.get_operations(user_id)
    
    debug_text = f"""
🔍 <b>Отладочная информация</b>

🆔 Ваш user_id: <code>{user_id}</code>
📊 Ваших операций: {len(operations)}
📂 Персональных категорий: {len(db.get_user_categories(user_id))}
    
Данные хранятся отдельно для каждого user_id.
Другие пользователи не видят ваши операции.
    """
    bot.reply_to(message, debug_text, parse_mode='HTML')

@bot.message_handler(commands=['month'])
def show_month_stats_cmd(message):
    """Показывает статистику за текущий месяц"""
    user_id = message.from_user.id
    monthly_ops = db.get_monthly_operations(user_id)
    
    if not monthly_ops:
        bot.reply_to(message, "📅 За текущий месяц операций нет.", reply_markup=create_main_keyboard())
        return
    
    expenses_by_category = {}
    monthly_income = 0
    monthly_expenses = 0
    
    for op in monthly_ops:
        if op['type'] == 'income':
            monthly_income += op['amount']
        else:
            monthly_expenses += op['amount']
            category = op['category']
            if category not in expenses_by_category:
                expenses_by_category[category] = 0
            expenses_by_category[category] += op['amount']
    
    now = datetime.now()
    month_name = now.strftime("%B %Y")
    
    stats_text = f"📅 <b>Статистика за {month_name}:</b>\n\n"
    stats_text += f"📈 Доходы: <b>+{monthly_income:,} руб.</b>\n"
    stats_text += f"📉 Расходы: <b>-{monthly_expenses:,} руб.</b>\n"
    stats_text += f"💵 Баланс: <b>{monthly_income - monthly_expenses:,} руб.</b>\n\n"
    
    if expenses_by_category:
        stats_text += "<b>Расходы по категориям:</b>\n"
        sorted_categories = sorted(expenses_by_category.items(), key=lambda x: x[1], reverse=True)
        
        for category, amount in sorted_categories:
            percentage = (amount / monthly_expenses) * 100 if monthly_expenses > 0 else 0
            stats_text += f"• {category}: <b>{amount:,} руб.</b> ({percentage:.1f}%)\n"
    
    bot.reply_to(message, stats_text, parse_mode='HTML', reply_markup=create_stats_keyboard())

# Визуальная статистика
@bot.message_handler(commands=['chart'])
def show_chart(message):
    """Показывает круговую диаграмму расходов"""
    user_id = message.from_user.id
    
    print(f"🔍 ДИАГНОСТИКА ДИАГРАММЫ:")
    print(f"👤 User ID: {user_id}")
    
    # Используем ТОЧНО ТОТ ЖЕ метод, что и в show_stats
    operations = db.get_operations(user_id)
    print(f"📊 Операций из db.get_operations(): {len(operations)}")
    
    # Собираем данные по категориям ТАК ЖЕ, как в show_stats
    expenses_by_category = {}
    
    for op in operations:
        print(f"  Операция: {op}")
        if op['type'] == 'expense':
            category = op.get('category', 'другое')
            amount = op['amount']
            
            if category not in expenses_by_category:
                expenses_by_category[category] = 0
            expenses_by_category[category] += amount
    
    print(f"💸 Найдено расходных операций: {len([op for op in operations if op['type'] == 'expense'])}")
    print(f"📂 Категории расходов: {expenses_by_category}")
    
    if not expenses_by_category:
        # Детальная диагностика почему нет расходов
        income_ops = [op for op in operations if op['type'] == 'income']
        expense_ops = [op for op in operations if op['type'] == 'expense']
        
        print(f"📈 Доходных операций: {len(income_ops)}")
        print(f"📉 Расходных операций: {len(expense_ops)}")
        
        if expense_ops:
            print("⚠️ Есть расходные операции, но категории пустые!")
            for op in expense_ops:
                print(f"  Расход: {op['amount']} - '{op['description']}' - категория: '{op.get('category', 'НЕТ КАТЕГОРИИ')}'")
        
        bot.reply_to(message, "📊 У вас пока нет расходов для построения диаграммы.")
        return
    
    # Создаем диаграмму
    try:
        print("🔄 Вызываем charts.create_expenses_chart...")
        chart_buffer = charts.create_expenses_chart(expenses_by_category, user_id)
        
        if chart_buffer:
            print("✅ Диаграмма создана успешно, отправляем...")
            # Формируем текстовую статистику
            total_expenses = sum(expenses_by_category.values())
            stats_text = "📊 <b>Статистика расходов:</b>\n\n"
            
            sorted_categories = sorted(expenses_by_category.items(), key=lambda x: x[1], reverse=True)
            for category, amount in sorted_categories:
                percentage = (amount / total_expenses) * 100
                stats_text += f"• {category}: <b>{amount:,} руб.</b> ({percentage:.1f}%)\n"
            
            stats_text += f"\n💵 <b>Всего расходов: {total_expenses:,} руб.</b>"
            
            # Отправляем изображение и текст
            bot.send_photo(
                chat_id=message.chat.id,
                photo=chart_buffer,
                caption=stats_text,
                parse_mode='HTML',
                reply_markup=create_stats_keyboard()
            )
            print("✅ Диаграмма отправлена пользователю")
        else:
            print("❌ charts.create_expenses_chart вернул None")
            # Показываем ту же статистику что и в show_stats
            show_stats_cmd(message)
    
    except Exception as e:
        print(f"❌ Ошибка при создании диаграммы: {e}")
        import traceback
        traceback.print_exc()
        # Показываем обычную статистику как fallback
        show_stats_cmd(message)

@bot.message_handler(commands=['history'])
def show_history_chart(message):
    """Показывает историю доходов/расходов за несколько месяцев"""
    user_id = message.from_user.id
    
    # Собираем данные за последние 6 месяцев
    monthly_data = {}
    now = datetime.now()
    
    for i in range(6):
        year = now.year
        month = now.month - i
        if month <= 0:
            month += 12
            year -= 1
        
        monthly_ops = db.get_monthly_operations(user_id, year, month)
        
        monthly_income = sum(op['amount'] for op in monthly_ops if op['type'] == 'income')
        monthly_expenses = sum(op['amount'] for op in monthly_ops if op['type'] == 'expense')
        
        month_name = datetime(year, month, 1).strftime("%b %Y")
        monthly_data[month_name] = {
            'income': monthly_income,
            'expenses': monthly_expenses
        }
    
    # Проверяем, есть ли данные
    total_income = sum(data['income'] for data in monthly_data.values())
    total_expenses = sum(data['expenses'] for data in monthly_data.values())
    
    if total_income == 0 and total_expenses == 0:
        bot.reply_to(message, "📅 Недостаточно данных для построения графика истории.")
        return
    
    # Создаем график
    try:
        chart_buffer = charts.create_monthly_stats_chart(monthly_data, user_id)
        
        if chart_buffer:
            # Текстовая информация
            history_text = "📈 <b>Динамика за 6 месяцев:</b>\n\n"
            
            for month_name, data in monthly_data.items():
                if data['income'] > 0 or data['expenses'] > 0:
                    balance = data['income'] - data['expenses']
                    history_text += f"• {month_name}: +{data['income']:,} / -{data['expenses']:,} руб. "
                    history_text += f"(баланс: {balance:,} руб.)\n"
            
            history_text += f"\n💰 <b>Итого за период:</b>"
            history_text += f"\nДоходы: +{total_income:,} руб."
            history_text += f"\nРасходы: -{total_expenses:,} руб."
            history_text += f"\nБаланс: {total_income - total_expenses:,} руб."
            
            bot.send_photo(
                chat_id=message.chat.id,
                photo=chart_buffer,
                caption=history_text,
                parse_mode='HTML',
                reply_markup=create_stats_keyboard()
            )
        else:
            bot.reply_to(message, "❌ Не удалось создать график.")
    
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при создании графика: {e}")

# Простой запуск для локальной разработки
if __name__ == "__main__":
    print("💰 Бот запущен! Для остановки нажмите Ctrl+C")
    
    try:
        bot.polling(none_stop=False, interval=0, timeout=20)
    except KeyboardInterrupt:
        print("\n\n🛑 Бот остановлен пользователем!")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")