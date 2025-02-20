import telebot
from telebot import types
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import os

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
ACCESS_CODE = os.getenv('ACCESS_CODE')
bot = telebot.TeleBot(API_TOKEN)

# Store authenticated users
authenticated_users = set()

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)
sheet = client.open("MamiBioMed_bot")

def fetch_products():
    product_sheet = client.open("MamiBioMed_bot").worksheet("Препараты")
    return product_sheet.get_all_records()

def generate_doctor_markup():
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add('Mamibiomed', 'Регина Аян', 'Азиза А')
    return markup

def show_payment_options(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Полная оплата", "Предоплата", "Доплата предоплаты")
    bot.send_message(chat_id, "Выберите тип платежа:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.id in authenticated_users:
        show_payment_options(message.chat.id)
    else:
        bot.send_message(message.chat.id, "Введите код доступа:")
        bot.register_next_step_handler(message, check_access_code)

def check_access_code(message):
    access_code = message.text
    if access_code != ACCESS_CODE:
        bot.send_message(message.chat.id, "Код доступа не правильный, попробуйте заново.")
        bot.register_next_step_handler(message, check_access_code)
    else:
        authenticated_users.add(message.chat.id)
        bot.send_message(message.chat.id, "Здравствуйте, доступ открыт.")
        show_payment_options(message.chat.id)

@bot.message_handler(func=lambda message: message.text == "Полная оплата")
def full_payment(message):
    if message.chat.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, введите код доступа сначала: /start")
        return
    bot.send_message(message.chat.id, "Введите имя клиента:")
    bot.register_next_step_handler(message, process_client_name)

def process_client_name(message):
    client_name = message.text
    bot.send_message(message.chat.id, "Введите номер телефона:")
    bot.register_next_step_handler(message, process_phone_number, client_name)

def process_phone_number(message, client_name):
    phone_number = message.text
    bot.send_message(message.chat.id, "Введите город:")
    bot.register_next_step_handler(message, process_city, client_name, phone_number)

def process_city(message, client_name, phone_number):
    city = message.text
    bot.send_message(message.chat.id, "Введите количество наименований:")
    bot.register_next_step_handler(message, process_item_count, client_name, phone_number, city)

def process_item_count(message, client_name, phone_number, city):
    item_count = int(message.text)
    items = []
    products = fetch_products()
    product_names = [product['Имя препарата'] for product in products]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(*product_names)
    bot.send_message(message.chat.id, "Выберите наименование (имя препарата):", reply_markup=markup)
    bot.register_next_step_handler(message, process_item_name, client_name, phone_number, city, items, item_count)

def process_item_name(message, client_name, phone_number, city, items, item_count):
    item_name = message.text
    bot.send_message(message.chat.id, "Введите количество препарата:")
    bot.register_next_step_handler(message, process_item_quantity, client_name, phone_number, city, items, item_name, item_count)

def process_item_quantity(message, client_name, phone_number, city, items, item_name, item_count):
    try:
        item_quantity = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректное количество (число).")
        bot.register_next_step_handler(message, process_item_quantity, client_name, phone_number, city, items, item_name, item_count)
        return

    items.append((item_name, item_quantity))
    
    if len(items) < item_count:
        bot.send_message(message.chat.id, "Введите имя следующего препарата:")
        bot.register_next_step_handler(message, process_item_name, client_name, phone_number, city, items, item_count)
    else:
        bot.send_message(message.chat.id, "Введите процент скидки:")
        bot.register_next_step_handler(message, process_discount, client_name, phone_number, city, items)

def process_discount(message, client_name, phone_number, city, items):
    try:
        discount = float(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный процент скидки (число).")
        bot.register_next_step_handler(message, process_discount, client_name, phone_number, city, items)
        return

    bot.send_message(message.chat.id, "Выберите врача:", reply_markup=generate_doctor_markup())
    bot.register_next_step_handler(message, process_doctor, client_name, phone_number, city, items, discount)

def process_doctor(message, client_name, phone_number, city, items, discount):
    doctor = message.text
    sale_date = datetime.now().strftime('%Y-%m-%d')
    summary_message = f"Продажа:\nДата: {sale_date}\nИмя клиента: {client_name}\nНомер телефона: {phone_number}\nГород: {city}\nНаименование и количество:\n"
    for item in items:
        product_name, quantity = item
        summary_message += f"- {product_name}: {quantity} шт\n"
    summary_message += f"Процент скидки: {discount}\nВрач: {doctor}"
    
    bot.send_message(message.chat.id, summary_message)
    
    sales_sheet = client.open("MamiBioMed_bot").worksheet("Продажи")
    for item in items:
        product_name, quantity = item
        product_info = next((product for product in fetch_products() if product['Имя препарата'] == product_name), None)
        if product_info:
            price_without_discount = product_info['Цена без скидки (тг)']
            supplier = product_info['Поставщик']
            total_price_with_discount = (quantity * price_without_discount) * (1 - discount / 100)
            sales_sheet.append_row([client_name, phone_number, city, product_name, quantity, price_without_discount, discount, total_price_with_discount, supplier, doctor, sale_date, sale_date])
    
    show_payment_options(message.chat.id)

@bot.message_handler(func=lambda message: message.text == "Предоплата")
def prepayment(message):
    if message.chat.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, введите код доступа сначала: /start")
        return
    bot.send_message(message.chat.id, "Введите имя клиента:")
    bot.register_next_step_handler(message, process_prepayment_client_name)

def process_prepayment_client_name(message):
    client_name = message.text
    bot.send_message(message.chat.id, "Введите номер телефона:")
    bot.register_next_step_handler(message, process_prepayment_phone_number, client_name)

def process_prepayment_phone_number(message, client_name):
    phone_number = message.text
    bot.send_message(message.chat.id, "Введите город:")
    bot.register_next_step_handler(message, process_prepayment_city, client_name, phone_number)

def process_prepayment_city(message, client_name, phone_number):
    city = message.text
    bot.send_message(message.chat.id, "Введите количество наименований:")
    bot.register_next_step_handler(message, process_prepayment_item_count, client_name, phone_number, city)

def process_prepayment_item_count(message, client_name, phone_number, city):
    try:
        item_count = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректное количество наименований (число).")
        bot.register_next_step_handler(message, process_prepayment_item_count, client_name, phone_number, city)
        return

    items = []
    products = fetch_products()
    product_names = [product['Имя препарата'] for product in products]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(*product_names)
    bot.send_message(message.chat.id, "Выберите наименование (имя препарата):", reply_markup=markup)
    bot.register_next_step_handler(message, process_prepayment_item_name, client_name, phone_number, city, items, item_count)

def process_prepayment_item_name(message, client_name, phone_number, city, items, item_count):
    item_name = message.text
    bot.send_message(message.chat.id, "Введите количество препарата:")
    bot.register_next_step_handler(message, process_prepayment_item_quantity, client_name, phone_number, city, items, item_name, item_count)

def process_prepayment_item_quantity(message, client_name, phone_number, city, items, item_name, item_count):
    try:
        item_quantity = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректное количество (число).")
        bot.register_next_step_handler(message, process_prepayment_item_quantity, client_name, phone_number, city, items, item_name, item_count)
        return

    bot.send_message(message.chat.id, "Введите сумму предоплаты:")
    bot.register_next_step_handler(message, process_prepayment_amount, client_name, phone_number, city, items, item_name, item_quantity, item_count)

def process_prepayment_amount(message, client_name, phone_number, city, items, item_name, item_quantity, item_count):
    try:
        prepayment_amount = float(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректную сумму предоплаты (число).")
        bot.register_next_step_handler(message, process_prepayment_amount, client_name, phone_number, city, items, item_name, item_quantity, item_count)
        return

    items.append((item_name, item_quantity, prepayment_amount))
    
    if len(items) < item_count:
        products = fetch_products()
        product_names = [product['Имя препарата'] for product in products]
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(*product_names)
        bot.send_message(message.chat.id, "Выберите наименование следующего препарата:", reply_markup=markup)
        bot.register_next_step_handler(message, process_prepayment_item_name, client_name, phone_number, city, items, item_count)
    else:
        bot.send_message(message.chat.id, "Введите процент скидки:")
        bot.register_next_step_handler(message, process_prepayment_discount, client_name, phone_number, city, items)

def process_prepayment_discount(message, client_name, phone_number, city, items):
    try:
        discount = float(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный процент скидки (число).")
        bot.register_next_step_handler(message, process_prepayment_discount, client_name, phone_number, city, items)
        return

    bot.send_message(message.chat.id, "Введите имя врача:", reply_markup=generate_doctor_markup())
    bot.register_next_step_handler(message, process_prepayment_doctor, client_name, phone_number, city, items, discount)

def process_prepayment_doctor(message, client_name, phone_number, city, items, discount):
    doctor = message.text
    prepayment_date = datetime.now().strftime('%Y-%m-%d')
    
    debug_items = []
    for item in items:
        item_name, item_quantity, prepayment_amount = item
        product_info = next((product for product in fetch_products() if product['Имя препарата'] == item_name), None)
        if product_info:
            price = product_info['Цена без скидки (тг)']
            supplier = product_info['Поставщик']
            debug_items.append(f"- {item_name}: {item_quantity} шт\n  Цена: {price} тг\n  Поставщик: {supplier}\n  Предоплата: {prepayment_amount} тг")
        else:
            debug_items.append(f"- {item_name}: {item_quantity} шт\n  ❌ Информация о товаре не найдена\n  Предоплата: {prepayment_amount} тг")
    
    debug_message = "\n".join(debug_items)
    bot.send_message(message.chat.id, f"Предоплата:\nДата: {prepayment_date}\nИмя клиента: {client_name}\nНомер телефона: {phone_number}\nГород: {city}\nТовары:\n{debug_message}\nПроцент скидки: {discount}\nВрач: {doctor}")
    
    try:
        prepayment_sheet = client.open("MamiBioMed_bot").worksheet("Предоплата")
        for item in items:
            item_name, item_quantity, prepayment_amount = item
            product_info = next((product for product in fetch_products() if product['Имя препарата'] == item_name), None)
            if product_info:
                price_without_discount = product_info['Цена без скидки (тг)']
                supplier = product_info['Поставщик']
                row_data = [client_name, phone_number, city, item_name, item_quantity, price_without_discount, supplier, prepayment_amount, prepayment_date, doctor]
            else:
                bot.send_message(message.chat.id, f"❌ Не найдена информация о товаре: {item_name}")
                continue
            prepayment_sheet.append_row(row_data)
            bot.send_message(message.chat.id, f"✅ Добавлена запись для {item_name}")
        
        show_payment_options(message.chat.id)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при сохранении данных: {str(e)}")
        show_payment_options(message.chat.id)

@bot.message_handler(func=lambda message: message.text == "Доплата предоплаты")
def prepayment_surcharge(message):
    if message.chat.id not in authenticated_users:
        bot.send_message(message.chat.id, "Пожалуйста, введите код доступа сначала: /start")
        return
        
    prepayment_sheet = client.open("MamiBioMed_bot").worksheet("Предоплата")
    prepayment_data = prepayment_sheet.get_all_records()
    
    if not prepayment_data:
        bot.send_message(message.chat.id, "Нет записей о предоплатах.")
        show_payment_options(message.chat.id)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for idx, entry in enumerate(prepayment_data):
        button_text = f"{entry['Имя клиента']} - {entry['Препарат']} - {entry['Сумма предоплаты']}тг - {entry['Дата']}"
        callback_data = f"prepayment_{idx}"
        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=callback_data))

    bot.send_message(message.chat.id, "Выберите предоплату:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('prepayment_'))
def handle_prepayment_selection(call):
    try:
        idx = int(call.data.split('_')[1])
        
        prepayment_sheet = client.open("MamiBioMed_bot").worksheet("Предоплата")
        prepayment_data = prepayment_sheet.get_all_records()
        
        if idx >= len(prepayment_data):
            bot.answer_callback_query(call.id, "Ошибка: запись не найдена")
            return
            
        selected_entry = prepayment_data[idx]
        
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"Выбрана запись:\n"
            f"Клиент: {selected_entry['Имя клиента']}\n"
            f"Препарат: {selected_entry['Препарат']}\n"
            f"Сумма предоплаты: {selected_entry['Сумма предоплаты']}тг\n"
            f"Дата: {selected_entry['Дата']}\n\n"
            f"Введите сумму доплаты:"
        )
        
        bot.register_next_step_handler(call.message, process_surcharge_amount_new, idx)
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"Произошла ошибка: {str(e)}")

def process_surcharge_amount_new(message, idx):
    try:
        surcharge_amount = float(message.text)
        
        prepayment_sheet = client.open("MamiBioMed_bot").worksheet("Предоплата")
        prepayment_data = prepayment_sheet.get_all_records()
        
        if idx >= len(prepayment_data):
            bot.send_message(message.chat.id, "❌ Ошибка: запись не найдена")
            show_payment_options(message.chat.id)
            return
            
        entry = prepayment_data[idx]
        
        sales_sheet = client.open("MamiBioMed_bot").worksheet("Продажи")
        current_date = datetime.now().strftime('%Y-%m-%d')
        sales_sheet.append_row([
            entry['Имя клиента'],
            entry['Номер телефона'],
            entry['Город'],
            entry['Препарат'],
            entry['Количество'],
            entry['Цена без скидки (тг)'],
            0,  # discount
            float(entry['Цена без скидки (тг)']) * float(entry['Количество']),  # total price
            entry['Поставщик'],
            entry['Врач'],
            entry['Дата'],  # Original sale date
            current_date  # Date of full payment
        ])
        
        row_index = idx + 2
        prepayment_sheet.delete_rows(row_index)
        
        bot.send_message(
            message.chat.id,
            f"✅ Доплата успешно обработана\n"
            f"Клиент: {entry['Имя клиента']}\n"
            f"Препарат: {entry['Препарат']}\n"
            f"Сумма доплаты: {surcharge_amount}тг\n"
            f"Запись перемещена в таблицу продаж"
        )
        
        show_payment_options(message.chat.id)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректную сумму доплаты (число)")
        bot.register_next_step_handler(message, process_surcharge_amount_new, idx)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка: {str(e)}")
        show_payment_options(message.chat.id)

bot.polling()
