from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, select

from .models import Base, User, Invoice, GiftDelivery
from src.utils import BalanceOperation


class Database:
    def __init__(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///src/data/database/database_file/database.sqlite",
            echo=False 
        )
        self.async_session = sessionmaker(
            self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def create_user(self, _id: int, initial_balance: float = 0.0) -> Optional[User]:
        async with self.async_session() as session:
            query = select(User).where(User.id == _id)
            result = await session.execute(query)
            existing_user = result.scalar_one_or_none()
            
            if not existing_user:
                user = User(id=_id, balance=initial_balance)
                session.add(user)
                await session.commit()

    async def update_balance(self, _id: int, amount: float, operation: BalanceOperation = BalanceOperation.SET) -> Optional[User]:
        async with self.async_session() as session:
            query = select(User).where(User.id == _id)
            result = await session.execute(query)
            user = result.scalar_one_or_none()
            
            if user:
                match operation:
                    case BalanceOperation.ADD:
                        user.balance += amount
                    case BalanceOperation.SUBTRACT:
                        user.balance -= amount
                    case BalanceOperation.SET:
                        user.balance = amount
                
                await session.commit()
                return user
            return None

    async def get_user(self, _id: int) -> Optional[User]:
        async with self.async_session() as session:
            query = select(User).where(User.id == _id)
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def get_user_count(self) -> int:
        async with self.async_session() as session:
            query = select(func.count()).select_from(User)
            result = await session.execute(query)
            return result.scalar_one()

    async def get_total_balance(self) -> float:
        async with self.async_session() as session:
            query = select(func.sum(User.balance)).select_from(User)
            result = await session.execute(query)
            return result.scalar_one() or 0.0
    
    async def grant_vip(self, _id: int, vip_value: bool) -> Optional[User]:
        async with self.async_session() as session:
            query = select(User).where(User.id == _id)
            result = await session.execute(query)
            user = result.scalar_one_or_none()
            
            if user:
                user.vip = vip_value
                await session.commit()
                return user
            return None
    
    async def create_invoice(self, amount: int) -> int:
        async with self.async_session() as session:
            invoice = Invoice(amount=amount)
            session.add(invoice)

            await session.commit()
            await session.refresh(invoice)
            return invoice.invoice_id
    
    async def additional_message_id_invoice(self, invoice_id: int, message_id: int):
        async with self.async_session() as session:
            query = select(Invoice).where(Invoice.invoice_id == invoice_id)
            result = (await session.execute(query)).scalar_one_or_none()
            
            result.message_id = message_id
            await session.commit()

    async def is_invoice_pending(self, invoice_id: int) -> bool:
        async with self.async_session() as session:
            query = select(Invoice).where(Invoice.invoice_id == invoice_id)
            result = (await session.execute(query)).scalar_one_or_none()
            
            if result and not result.status:
                return True
            return False

    async def get_invoice_message_id(self, invoice_id: int, status: bool) -> int:
        async with self.async_session() as session:
            query = select(Invoice).where(Invoice.invoice_id == invoice_id)
            result = (await session.execute(query)).scalar_one_or_none()

            if result:
                result.status = status
                await session.commit()

                return result.message_id
    
    async def get_user_updator(self, only_vip: bool = False) -> list[User]:
        async with self.async_session() as session:
            if only_vip:
                query = select(User).where(User.vip == True)
            else:
                query = select(User)
                
            result = await session.execute(query)
            return result.scalars().all()

    async def create_gift_delivery(self, gift_id: int, user_id: int) -> GiftDelivery:
        async with self.async_session() as session:
            delivery = GiftDelivery(gift_id=gift_id, user_id=user_id)
            session.add(delivery)
            await session.commit()
            return delivery

    async def get_gift_delivery(self, gift_id: int, user_id: int) -> Optional[bool]:
        async with self.async_session() as session:
            query = select(GiftDelivery).where(
                GiftDelivery.gift_id == gift_id,
                GiftDelivery.user_id == user_id
            )
            result = await session.execute(query)
            delivery = result.scalar_one_or_none()
            
            if delivery:
                return delivery.delivered
            return None

    async def mark_gift_delivered(self, delivery_id: int) -> None:
        async with self.async_session() as session:
            query = select(GiftDelivery).where(GiftDelivery.id == delivery_id)
            result = await session.execute(query)
            delivery = result.scalar_one_or_none()
            if delivery:
                delivery.delivered = True
                await session.commit()

    async def user_buy_gift(self, amount: int, user_id: int) -> bool:
        async with self.async_session() as session:
            query = select(User).where(User.id == user_id)
            result = await session.execute(query)
            user = result.scalar_one_or_none()
            
            if user and user.balance >= amount:
                user.balance -= amount
                await session.commit()
                return True
            
            return False
    
    async def get_total_gifts(self) -> int:
        async with self.async_session() as session:
            query = select(func.count()).select_from(GiftDelivery).where(GiftDelivery.delivered == True)
            result = await session.execute(query)
            return result.scalar() or 0