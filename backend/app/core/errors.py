class DomainError(Exception):
    """Ошибка бизнес-логики, текст которой можно показать пользователю."""


class NotFoundError(DomainError):
    """Запрошенная сущность не найдена."""


class AuthError(Exception):
    """Не удалось аутентифицировать пользователя."""
