from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class Repository[ModelT]:
    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id_: Any) -> ModelT | None:
        return await self.session.get(self.model, id_)

    def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
