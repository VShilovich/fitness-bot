from aiogram.fsm.state import State, StatesGroup

class Profile(StatesGroup):
    weight = State()
    height = State()
    age = State()
    activity = State()
    city = State()
    calorie_goal = State()

class FoodLog(StatesGroup):
    waiting_for_food_amount = State()