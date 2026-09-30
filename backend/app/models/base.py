from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: DateTime(timezone=True)}  # noqa: RUF012


def str_enum(enum_cls: type[PyEnum], length: int = 24) -> Enum:
    """Enum, хранимый в БД как VARCHAR со значениями (а не именами) членов перечисления."""
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda members: [member.value for member in members],
    )
