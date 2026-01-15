import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from handlers import setup_handlers
from middlewares import LoggingMiddleware

# настройка логирования
logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # подключаем middleware
    dp.message.middleware(LoggingMiddleware())
    
    # регистрируем роутеры
    setup_handlers(dp)
    
    print("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")