import random
from aiogram import Router
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from states import Profile, FoodLog
from utils import users, get_temperature, get_food_info, calculate_goals, generate_progress_chart

router = Router()

# обработчик команды /start
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "Привет! Я помогу тебе следить за водой и калориями.\n"
        "Сначала заполни профиль: /set_profile"
    )

# обработчик команды /help
@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.reply(
        "/set_profile - Настроить профиль\n"
        "/log_water <мл> - Записать воду\n"
        "/log_food <продукт> - Записать еду\n"
        "/log_workout <тип> <минуты> - Записать тренировку\n"
        "/check_progress - Посмотреть прогресс\n"
        "/recommend - Получить рекомендации"
    )

# настройка профиля
@router.message(Command("set_profile"))
async def start_profile(message: Message, state: FSMContext):
    await message.reply("Введите ваш вес (в кг):")
    await state.set_state(Profile.weight)

@router.message(Profile.weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        weight = int(message.text)
        await state.update_data(weight=weight)
        await message.reply("Введите ваш рост (в см):")
        await state.set_state(Profile.height)
    except ValueError:
        await message.reply("Пожалуйста, введите число.")

@router.message(Profile.height)
async def process_height(message: Message, state: FSMContext):
    try:
        height = int(message.text)
        await state.update_data(height=height)
        await message.reply("Введите ваш возраст:")
        await state.set_state(Profile.age)
    except ValueError:
        await message.reply("Введите число.")

@router.message(Profile.age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        await state.update_data(age=age)
        await message.reply("Сколько минут активности у вас в день?")
        await state.set_state(Profile.activity)
    except ValueError:
        await message.reply("Введите число.")

@router.message(Profile.activity)
async def process_activity(message: Message, state: FSMContext):
    try:
        activity = int(message.text)
        await state.update_data(activity=activity)
        await message.reply("В каком городе вы находитесь?")
        await state.set_state(Profile.city)
    except ValueError:
        await message.reply("Введите число.")

@router.message(Profile.city)
async def process_city(message: Message, state: FSMContext):
    city = message.text
    data = await state.get_data()
    temp = await get_temperature(city)
    
    # инициализируем пользователя в словаре
    user_id = message.from_user.id
    users[user_id] = {
        "weight": data['weight'],
        "height": data['height'],
        "age": data['age'],
        "activity": data['activity'],
        "city": city,
        "temp": temp,
        "logged_water": 0,
        "logged_calories": 0,
        "burned_calories": 0
    }
    
    # рассчитываем цели
    water_goal, calorie_goal = calculate_goals(user_id)
    users[user_id]["water_goal"] = water_goal
    users[user_id]["calorie_goal"] = calorie_goal
    
    await state.clear()
    await message.reply(
        f"Профиль сохранен!\n"
        f"Погода в {city}: {temp}C\n"
        f"Цель воды: {water_goal} мл\n"
        f"Цель калорий: {calorie_goal} ккал"
    )

# логирование воды
@router.message(Command("log_water"))
async def log_water(message: Message, command: CommandObject):
    user_id = message.from_user.id
    if user_id not in users:
        await message.reply("Сначала настройте профиль: /set_profile")
        return

    if command.args is None:
        await message.reply("Пример использования: /log_water 52")
        return

    try:
        amount = int(command.args)
        users[user_id]["logged_water"] += amount
        remains = max(0, users[user_id]["water_goal"] - users[user_id]["logged_water"])
        await message.reply(f"Записано: {amount} мл. Осталось: {remains} мл.")
    except ValueError:
        await message.reply("Введите число.")

# логирование еды
@router.message(Command("log_food"))
async def log_food_start(message: Message, command: CommandObject, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users:
        await message.reply("Сначала настройте профиль!")
        return

    if command.args is None:
        await message.reply("Пример: /log_food банан")
        return

    product_name = command.args
    food_info = await get_food_info(product_name)
    
    if not food_info or food_info['calories'] == 0:
        await message.reply("Не удалось найти продукт или калорийность неизвестна.")
        return

    # сохранение информации о продукте
    await state.update_data(food_name=food_info['name'], food_calories=food_info['calories'])
    
    await message.reply(f"{food_info['name']} — {food_info['calories']} ккал на 100г.\nСколько грамм вы съели?")
    await state.set_state(FoodLog.waiting_for_food_amount)

@router.message(FoodLog.waiting_for_food_amount)
async def log_food_finish(message: Message, state: FSMContext):
    try:
        grams = int(message.text)
        data = await state.get_data()
        kcal_100g = data['food_calories']
        
        consumed_kcal = (kcal_100g * grams) / 100
        
        user_id = message.from_user.id
        users[user_id]["logged_calories"] += consumed_kcal
        
        await message.reply(f"Записано: {consumed_kcal:.1f} ккал.")
        await state.clear()
    except ValueError:
        await message.reply("Введите число (граммы).")

# логирование тренировок
@router.message(Command("log_workout"))
async def log_workout(message: Message, command: CommandObject):
    user_id = message.from_user.id
    if user_id not in users:
        await message.reply("Сначала профиль!")
        return
        
    args = command.args.split() if command.args else []
    if len(args) < 2:
        await message.reply("Пример: /log_workout бег 30")
        return
    
    workout_type = args[0]
    try:
        minutes = int(args[1])
        # формула расхода: 10 ккал в минуту
        burned = minutes * 10 
        # доп вода: 200 мл за 30 мин
        extra_water = (minutes // 30) * 200
        
        users[user_id]["burned_calories"] += burned
        users[user_id]["water_goal"] += extra_water
        
        await message.reply(
            f"{workout_type} {minutes} мин — {burned} ккал.\n"
            f"Дополнительно: выпейте {extra_water} мл воды."
        )
    except ValueError:
        await message.reply("Время должно быть числом.")

# прогресс
@router.message(Command("check_progress"))
async def check_progress(message: Message):
    user_id = message.from_user.id
    if user_id not in users:
        await message.reply("Сначала настройте профиль!")
        return
        
    user = users[user_id]
    
    water_remains = max(0, user["water_goal"] - user["logged_water"])
    calorie_balance = user["logged_calories"] - user["burned_calories"]
    
    text_report = (
        f"Прогресс:\n\n"
        f"Вода:\n"
        f"Выпито: {user['logged_water']} мл из {user['water_goal']} мл\n"
        f"Осталось: {water_remains} мл\n\n"
        f"Калории:\n"
        f"Потреблено: {user['logged_calories']:.1f} ккал\n"
        f"Сожжено: {user['burned_calories']} ккал\n"
        f"Баланс: {calorie_balance:.1f} / {user['calorie_goal']} ккал"
    )

    # получаем байты картинки из функции и создаем объект файла для tg
    image_buffer = generate_progress_chart(user_id)
    photo = BufferedInputFile(image_buffer.read(), filename="progress.png")
    
    await message.reply_photo(photo=photo, caption=text_report)

# личные рекомендации
@router.message(Command("recommend"))
async def cmd_recommend(message: Message):
    user_id = message.from_user.id
    if user_id not in users:
        await message.reply("Сначала настройте профиль: /set_profile")
        return

    user = users[user_id]
    
    # считаем текущие показатели
    water_remains = user["water_goal"] - user["logged_water"]
    calorie_balance = user["logged_calories"] - user["burned_calories"]
    calorie_remains = user["calorie_goal"] - calorie_balance

    recommendations = []

    # проверка воды
    if water_remains > 500:
        recommendations.append(
            f"Вы отстаете по воде на {water_remains} мл."
        )

    # проверка калорий
    if calorie_remains < 0:
        # если калорий перебор, то советуется рандомная кардио-тренировка
        workouts = [
            "быструю прогулку (30 мин)",
            "легкий бег (20 мин)",
            "йогу или растяжку",
            "приседания (3 подхода по 15 раз)"
        ]
        advice = random.choice(workouts)
        recommendations.append(
            f"Вы превысили норму калорий на {abs(int(calorie_remains))} ккал.\n"
            f"Рекомендую сделать {advice}, чтобы сжечь лишнее."
        )
    
    elif calorie_remains < 300:
        # если осталось мало калорий, то советуем низкокалорийные продукты
        low_cal_foods = [
            "Огурец",
            "Сельдерей",
            "Листовой салат",
            "Зеленое яблоко"
        ]
        food = random.choice(low_cal_foods)
        recommendations.append(
            f"Вы почти у цели. Если голодны, перекусите чем-то легким:\n"
            f"Например: {food}."
        )
    
    else:
        # если калорий много, то можно поесть нормально
        recommendations.append(
            f"У вас хороший запас калорий ({int(calorie_remains)} ккал).\n"
            "Можете позволить себе полноценный обед с белками и сложными углеводами."
        )

    if not recommendations:
        await message.reply("У вас всё отлично! Продолжайте в том же духе.")
    else:
        await message.reply("\n\n".join(recommendations))

def setup_handlers(dp):
    dp.include_router(router)