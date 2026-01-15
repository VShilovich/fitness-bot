import aiohttp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
from config import WEATHER_API_KEY, SPOONACULAR_API_KEY

# глобальное хранилище данных пользователей
users = {}

# получает текущую температуру в городе через OpenWeatherMap
async def get_temperature(city: str) -> float:

    if not WEATHER_API_KEY:
        return 20.0 # 20 просто как заглушка, если ключа нет
    
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["main"]["temp"]
        except Exception as e:
            print(f"Weather API Error: {e}")
    return 20.0

# ищет калорийность продукта через Spoonacular API
async def get_food_info(product_name: str):

    if not SPOONACULAR_API_KEY:
        print("Spoonacular API Key не найден!")
        return None

    # поиск ID продукта
    search_url = "https://api.spoonacular.com/food/ingredients/search"
    params = {
        "query": product_name,
        "apiKey": SPOONACULAR_API_KEY,
        "number": 1  # ищем только лучший результат
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(search_url, params=params) as response:
                if response.status != 200:
                    print(f"Spoonacular Search Error: {response.status}")
                    return None
                
                search_data = await response.json()
                results = search_data.get("results", [])
                
                if not results:
                    return None
                
                product_id = results[0]["id"]
                product_title = results[0]["name"]

            # получение нутриентов для найденного ID для 100 грамм
            info_url = f"https://api.spoonacular.com/food/ingredients/{product_id}/information"
            info_params = {
                "amount": 100,
                "unit": "grams",
                "apiKey": SPOONACULAR_API_KEY
            }

            async with session.get(info_url, params=info_params) as response:
                if response.status != 200:
                    print(f"Spoonacular Info Error: {response.status}")
                    return None
                
                info_data = await response.json()
                
                # ищем калории в списке нутриентов
                calories = 0
                for nutrient in info_data.get("nutrition", {}).get("nutrients", []):
                    if nutrient["name"] == "Calories":
                        calories = nutrient["amount"]
                        break
                
                return {
                    "name": product_title,
                    "calories": calories
                }

        except Exception as e:
            print(f"Spoonacular API Exception: {e}")
            return None

# рассчитывает нормы воды и калорий на основе профиля
def calculate_goals(user_id):
    user = users[user_id]
    weight = user['weight']
    height = user['height']
    age = user['age']
    activity = user['activity']
    temp = user.get('temp', 20)

    # 30 мл на кг + 500 мл за каждые 30 мин активности
    water_goal = weight * 30 + (activity // 30 * 500)
    # добавляем за жару
    if temp > 25:
        water_goal += 500
    
    # 10 * вес + 6.25 * рост - 5 * возраст
    calorie_goal = (10 * weight) + (6.25 * height) - (5 * age)
    # добавляем калории за активность
    # допустим, коэффициент активности: 1 мин = 5 ккал
    activity_bonus = activity * 3 
    calorie_goal += activity_bonus

    return int(water_goal), int(calorie_goal)

# генерирует график прогресса
def generate_progress_chart(user_id):
    user = users[user_id]
    
    # данные для воды
    water_goal = user['water_goal']
    logged_water = user['logged_water']
    
    # данные для калорий
    calorie_goal = user['calorie_goal']
    logged_calories = user['logged_calories']
    burned_calories = user['burned_calories']
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))
    
    # график воды
    ax1.bar(['Выпито', 'Цель'], [logged_water, water_goal], color=['blue', 'lightblue'])
    ax1.set_title('Вода (мл)')
    ax1.set_ylabel('Объем (мл)')
    
    # график калорий
    net_calories = max(0, logged_calories - burned_calories)
    
    ax2.bar(['Потреблено', 'Сожжено', 'Цель'], 
            [logged_calories, burned_calories, calorie_goal], 
            color=['red', 'orange', 'green'])
    ax2.set_title('Калории (ккал)')
    ax2.set_ylabel('ккал')
    
    for ax in (ax1, ax2):
        for container in ax.containers:
            ax.bar_label(container)

    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    
    return buf