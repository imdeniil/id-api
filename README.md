# ID API

Гибкая и многофункциональная HTTP-клиентская библиотека с поддержкой аутентификации JWT и OAuth2, предоставляющая как синхронную, так и асинхронную реализации.

## Возможности

- **Двойная реализация**: Синхронные (с использованием `requests`) и асинхронные (с использованием `aiohttp`) HTTP-клиенты
- **Аутентификация**:
  - JWT аутентификация
  - OAuth2 аутентификация с автоматическим обновлением токена
- **Надежная обработка ошибок**:
  - Настраиваемый механизм автоматических повторных попыток
  - Пользовательские обработчики ошибок
- **Обработка запросов/ответов**:
  - Интерцепторы запросов и ответов
  - Автоматическая сериализация/десериализация JSON
- **Логирование и мониторинг**:
  - Комплексное логирование запросов/ответов
  - Маскирование конфиденциальных данных
- **Удобство использования**:
  - Поддержка контекстных менеджеров
  - Унифицированные объекты ответов

## Установка

```bash
pip install id-api
```

## Основное использование

### Создание клиентов

```python
from id_api import create_http_client, SyncHttpClient, AsyncHttpClient

# Использование фабричной функции
sync_client = create_http_client(
    base_url="https://api.example.com",
    timeout=10
)

# Для асинхронного использования
async_client = create_http_client(
    async_mode=True,
    base_url="https://api.example.com",
    timeout=10
)

# Или инстанцирование напрямую
sync_client = SyncHttpClient(base_url="https://api.example.com")
async_client = AsyncHttpClient(base_url="https://api.example.com")
```

### Выполнение запросов

#### Синхронные запросы

```python
# Простой GET запрос
response = sync_client.get("/users")
print(f"Код статуса: {response.status_code}")
print(f"Данные: {response.data}")

# POST запрос с JSON данными
response = sync_client.post(
    "/users",
    data={"name": "Иван Петров", "email": "ivan@example.com"}
)

# Использование контекстного менеджера
with SyncHttpClient(base_url="https://api.example.com") as client:
    response = client.get("/users")
    # Сессия клиента будет автоматически закрыта
```

#### Асинхронные запросы

```python
import asyncio

async def fetch_data():
    # Простой GET запрос
    response = await async_client.get("/users")
    print(f"Код статуса: {response.status_code}")
    print(f"Данные: {response.data}")
    
    # POST запрос с JSON данными
    response = await async_client.post(
        "/users",
        data={"name": "Иван Петров", "email": "ivan@example.com"}
    )
    
    # Использование асинхронного контекстного менеджера
    async with AsyncHttpClient(base_url="https://api.example.com") as client:
        response = await client.get("/users")
        # Сессия клиента будет автоматически закрыта

# Запуск асинхронной функции
asyncio.run(fetch_data())
```

## Аутентификация

### JWT аутентификация

```python
from id_api import JwtHttpClient, AsyncJwtHttpClient

# Синхронный JWT клиент
jwt_client = JwtHttpClient(
    base_url="https://api.example.com",
    jwt_token="ваш.jwt.токен"
)

# Асинхронный JWT клиент
async_jwt_client = AsyncJwtHttpClient(
    base_url="https://api.example.com",
    jwt_token="ваш.jwt.токен"
)
```

### OAuth2 аутентификация

```python
from id_api import OAuth2HttpClient, AsyncOAuth2HttpClient

# Синхронный OAuth2 клиент
oauth2_client = OAuth2HttpClient(
    base_url="https://api.example.com",
    client_id="ваш_client_id",
    client_secret="ваш_client_secret",
    token_url="https://auth.example.com/token"
)

# Аутентификация с помощью имени пользователя и пароля
success = oauth2_client.authenticate("имя_пользователя", "пароль")
if success:
    # Теперь можно делать аутентифицированные запросы
    response = oauth2_client.get("/protected-resource")

# Асинхронный OAuth2 клиент
async_oauth2_client = AsyncOAuth2HttpClient(
    base_url="https://api.example.com",
    client_id="ваш_client_id",
    client_secret="ваш_client_secret",
    token_url="https://auth.example.com/token"
)

# Асинхронная аутентификация с помощью имени пользователя и пароля
async def authenticate_and_fetch():
    success = await async_oauth2_client.authenticate("имя_пользователя", "пароль")
    if success:
        # Теперь можно делать аутентифицированные запросы
        response = await async_oauth2_client.get("/protected-resource")

# С существующими токенами
oauth2_client = OAuth2HttpClient(
    base_url="https://api.example.com",
    client_id="ваш_client_id",
    client_secret="ваш_client_secret",
    token_url="https://auth.example.com/token",
    access_token="существующий_access_token",
    refresh_token="существующий_refresh_token"
)
```

## Расширенные возможности

### Интерцепторы запросов и ответов

```python
def request_interceptor(config):
    # Добавление пользовательского заголовка ко всем запросам
    config["headers"]["X-Custom-Header"] = "custom-value"
    return config

def response_interceptor(response):
    # Обработка всех ответов
    if hasattr(response, "data") and isinstance(response.data, dict):
        response.data["processed"] = True
    return response

client = SyncHttpClient(
    base_url="https://api.example.com",
    request_interceptor=request_interceptor,
    response_interceptor=response_interceptor
)
```

### Обработка ошибок

```python
def error_interceptor(error):
    # Логирование ошибки
    print(f"Произошла ошибка: {error}")
    
    # Возврат стандартного ответа вместо генерации исключения
    if hasattr(error, "response"):
        return error.response
    else:
        from id_api import Response
        return Response(
            status_code=500,
            headers={},
            data={"error": str(error)},
            raw_response=None
        )

client = SyncHttpClient(
    base_url="https://api.example.com",
    error_interceptor=error_interceptor
)
```

### Автоматические повторные попытки

```python
import requests

client = SyncHttpClient(
    base_url="https://api.example.com",
    max_retries=3,
    retry_delay=0.5,
    retry_backoff=2.0,
    retry_status_codes=[429, 500, 502, 503, 504],
    retry_exceptions=[
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout
    ]
)
```

### Логирование

```python
import logging

# Настройка логгера
logger = logging.getLogger("api_client")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Использование логгера в клиенте
client = SyncHttpClient(
    base_url="https://api.example.com",
    logger=logger,
    log_level=logging.INFO,
    log_request_body=True,
    log_response_body=True
)
```

## Справочник по API

### Основные классы

- `BaseHttpClient`: Абстрактный базовый класс, определяющий интерфейс для HTTP-клиентов
- `SyncHttpClient`: Реализация синхронного HTTP-клиента с использованием `requests`
- `AsyncHttpClient`: Реализация асинхронного HTTP-клиента с использованием `aiohttp`
- `JwtHttpClient`: Специализированный синхронный клиент для JWT аутентификации
- `OAuth2HttpClient`: Специализированный синхронный клиент для OAuth2 аутентификации
- `AsyncJwtHttpClient`: Специализированный асинхронный клиент для JWT аутентификации
- `AsyncOAuth2HttpClient`: Специализированный асинхронный клиент для OAuth2 аутентификации

### Вспомогательные классы

- `AuthType`: Перечисление, определяющее типы аутентификации (JWT, OAUTH2)
- `Response`: Унифицированный объект ответа для синхронных и асинхронных клиентов
- `AuthConfig`: Класс конфигурации для настроек аутентификации

### Фабричная функция

- `create_http_client()`: Вспомогательная функция для создания клиентов с заданной конфигурацией

## Полный пример

```python
import logging
from id_api import create_http_client

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_client")

# Определение интерцепторов
def request_interceptor(config):
    config["headers"]["X-App-Version"] = "1.0.0"
    return config

def response_interceptor(response):
    if response.status_code == 200 and hasattr(response.data, "get"):
        print(f"Успешно обработано: {response.data.get('title', 'Неизвестно')}")
    return response

def error_interceptor(error):
    print(f"Произошла ошибка: {error}")
    raise error  # Повторная генерация ошибки

# Создание клиента
client = create_http_client(
    base_url="https://jsonplaceholder.typicode.com",
    timeout=10,
    max_retries=2,
    retry_delay=0.5,
    retry_backoff=2.0,
    request_interceptor=request_interceptor,
    response_interceptor=response_interceptor,
    error_interceptor=error_interceptor,
    logger=logger,
    log_level=logging.INFO
)

# Использование клиента
with client:
    # GET запрос
    response = client.get("/posts/1")
    print(f"GET ответ: {response.data}")
    
    # POST запрос
    response = client.post(
        "/posts",
        data={
            "title": "Новый пост",
            "body": "Это новый пост",
            "userId": 1
        }
    )
    print(f"POST ответ: {response.data}")
```

## Лицензия

MIT