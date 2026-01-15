from aiogram import BaseMiddleware
from aiogram.types import Message

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        if isinstance(event, Message):
            print(f"Пользователь {event.from_user.id} отправил: {event.text}")
        return await handler(event, data)