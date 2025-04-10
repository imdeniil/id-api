"""
HTTP Client module with support for JWT and OAuth2 authentication.
Provides both synchronous and asynchronous implementations.
"""

import json
import time
import logging
from abc import ABC, abstractmethod
import requests
import asyncio
import aiohttp
from typing import Dict, Any, Optional, Union, Callable, List, Type, Tuple
from dataclasses import dataclass
from enum import Enum, auto

class AuthType(Enum):
    """Тип аутентификации."""
    JWT = auto()
    OAUTH2 = auto()


@dataclass
class Response:
    """Класс для унифицированного представления ответа API."""
    status_code: int
    headers: Dict[str, str]
    data: Any
    raw_response: Any


@dataclass
class AuthConfig:
    """Конфигурация аутентификации."""
    type: AuthType = AuthType.JWT
    
    # Общие параметры
    token_header: str = "Authorization"
    token_prefix: str = "Bearer "
    
    # Данные токенов
    token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None
    
    # OAuth2 параметры
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_url: Optional[str] = None


class BaseHttpClient(ABC):
    """
    Базовый абстрактный класс для HTTP клиентов.
    Содержит общую логику и определяет интерфейс для конкретных реализаций.
    """
    
    def __init__(
        self,
        base_url: str = "",
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        
        # Параметры аутентификации
        auth_type: Optional[AuthType] = None,
        token: Optional[str] = None,
        token_header: str = "Authorization",
        token_prefix: str = "Bearer ",
        
        # OAuth2 параметры
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        token_url: Optional[str] = None,
        refresh_token: Optional[str] = None,
        
        # Обработчики
        request_interceptor: Optional[Callable] = None,
        response_interceptor: Optional[Callable] = None,
        error_interceptor: Optional[Callable] = None,
        
        # Настройки повторных попыток
        max_retries: int = 0,
        retry_delay: float = 0.1,
        retry_backoff: float = 2.0,
        retry_status_codes: Optional[List[int]] = None,
        retry_exceptions: Optional[List[Type[Exception]]] = None,
        
        # Настройки логирования
        logger: Optional[logging.Logger] = None,
        log_level: int = logging.INFO,
        log_request_body: bool = False,
        log_response_body: bool = False
    ):
        """
        Инициализация базового клиента.
        
        Args:
            base_url: Базовый URL для всех запросов
            headers: Заголовки по умолчанию
            timeout: Таймаут по умолчанию в секундах
            
            auth_type: Тип аутентификации (если указан явно)
            token: Токен для аутентификации (JWT или OAuth2 access_token)
            token_header: Имя заголовка для токена (по умолчанию 'Authorization')
            token_prefix: Префикс для токена в заголовке (по умолчанию 'Bearer ')
            query_param: Имя параметра запроса для токена (если None, будет использоваться заголовок)
            
            client_id: Идентификатор клиента для OAuth2
            client_secret: Секрет клиента для OAuth2
            token_url: URL для получения/обновления токена OAuth2
            refresh_token: Токен обновления для OAuth2
            
            request_interceptor: Функция для обработки запроса перед отправкой
            response_interceptor: Функция для обработки ответа
            error_interceptor: Функция для обработки ошибок
            
            max_retries: Максимальное количество повторных попыток при ошибках
            retry_delay: Начальная задержка между повторными попытками (в секундах)
            retry_backoff: Множитель для экспоненциальной задержки
            retry_status_codes: Список HTTP-кодов, при которых нужно повторять запрос
            retry_exceptions: Список исключений, при которых нужно повторять запрос
            
            logger: Логгер для записи информации о запросах и ответах
            log_level: Уровень логирования
            log_request_body: Флаг для логирования тела запроса
            log_response_body: Флаг для логирования тела ответа
        """
        self.base_url = base_url
        self.default_headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout
        
        # Инициализация конфигурации аутентификации
        self.auth = self._setup_auth_config(
            auth_type=auth_type,
            token=token,
            token_header=token_header,
            token_prefix=token_prefix,
            client_id=client_id,
            client_secret=client_secret,
            token_url=token_url,
            refresh_token=refresh_token
        )
        
        # Интерцепторы
        self.request_interceptor = request_interceptor or (lambda config: config)
        self.response_interceptor = response_interceptor or (lambda response: response)
        self.error_interceptor = error_interceptor or (lambda error: raise_error(error))
        
        # Настройки повторных попыток
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self.retry_status_codes = retry_status_codes or [429, 500, 502, 503, 504]
        self.retry_exceptions = retry_exceptions or []
        
        # Настройки логирования
        self.logger = logger or logging.getLogger(__name__)
        self.log_level = log_level
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
    
    def _setup_auth_config(
        self,
        auth_type: Optional[AuthType],
        token: Optional[str],
        token_header: str,
        token_prefix: str,
        client_id: Optional[str],
        client_secret: Optional[str],
        token_url: Optional[str],
        refresh_token: Optional[str]
    ) -> AuthConfig:
        """
        Настройка конфигурации аутентификации.
        
        Определяет тип аутентификации на основе предоставленных параметров.
        """
        auth = AuthConfig(
            token_header=token_header,
            token_prefix=token_prefix,
            token=token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_url=token_url
        )
        
        # Если тип аутентификации указан явно
        if auth_type:
            auth.type = auth_type
        # Иначе определяем тип на основе предоставленных параметров
        elif token and (client_id and client_secret and token_url):
            auth.type = AuthType.OAUTH2
        else:
            auth.type = AuthType.JWT
            
        return auth
    
    def prepare_request(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Подготовка конфигурации запроса.
        
        Args:
            config: Исходная конфигурация запроса
            
        Returns:
            Подготовленная конфигурация запроса
        """
        url = f"{self.base_url}{config.get('url', '')}"
        method = config.get("method", "GET")
        headers = {**self.default_headers, **(config.get("headers") or {})}
        timeout = config.get("timeout", self.timeout)
        data = config.get("data")
        params = config.get("params", {}) or {}
        
        # Применяем аутентификацию, если токен доступен
        if self.auth.token:
            # Обновляем токен OAuth2, если он истёк и есть возможность обновить
            if (self.auth.type == AuthType.OAUTH2 and 
                self.auth.expires_at and 
                time.time() > self.auth.expires_at and 
                self.auth.refresh_token):
                self._refresh_oauth2_token()
            
            # Добавляем токен в заголовок
            headers[self.auth.token_header] = f"{self.auth.token_prefix}{self.auth.token}"
        
        # Преобразуем данные в JSON, если это словарь или список и заголовок соответствующий
        if isinstance(data, (dict, list)) and headers.get("Content-Type") == "application/json":
            data = json.dumps(data)
        
        prepared_config = {
            "url": url,
            "method": method,
            "headers": headers,
            "timeout": timeout,
            "data": data,
            "params": params
        }
        
        # Применяем интерцептор запроса
        return self.request_interceptor(prepared_config)
    
    def _log_request(self, method: str, url: str, headers: Dict[str, str], data=None, params=None) -> None:
        """
        Логирование запроса.
        
        Args:
            method: HTTP метод
            url: URL запроса
            headers: Заголовки запроса
            data: Данные запроса
            params: Параметры запроса
        """
        if not self.logger:
            return
        
        # Логируем базовую информацию о запросе
        log_message = f">>> Request: {method} {url}"
        if params:
            log_message += f" params={params}"
        
        self.logger.log(self.log_level, log_message)
        
        # Логируем заголовки на уровне DEBUG
        if self.logger.isEnabledFor(logging.DEBUG):
            # Маскируем чувствительные данные в заголовках
            safe_headers = self._mask_sensitive_headers(headers)
            self.logger.debug(f">>> Request headers: {safe_headers}")
        
        # Логируем тело запроса, если включено
        if self.log_request_body and data and self.logger.isEnabledFor(logging.DEBUG):
            try:
                # Пытаемся отформатировать JSON для лучшей читаемости
                if isinstance(data, str) and data.startswith('{'):
                    body = json.dumps(json.loads(data), indent=2)
                    self.logger.debug(f">>> Request body:\n{body}")
                else:
                    # Ограничиваем длину тела для не-JSON данных
                    body_str = str(data)
                    if len(body_str) > 1000:
                        body_str = f"{body_str[:997]}..."
                    self.logger.debug(f">>> Request body: {body_str}")
            except Exception:
                # Если не получилось отформатировать, логируем как есть
                self.logger.debug(f">>> Request body: {data}")
    
    def _log_response(self, response, elapsed_time: float = None) -> None:
        """
        Логирование ответа.
        
        Args:
            response: Ответ от сервера
            elapsed_time: Время выполнения запроса в секундах
        """
        if not self.logger:
            return
        
        # Получаем статус и URL из ответа (с поддержкой разных форматов)
        status = getattr(response, 'status_code', getattr(response, 'status', 0))
        url = str(getattr(response, 'url', 'unknown'))
        
        # Формируем сообщение для лога
        log_message = f"<<< Response: {status} from {url}"
        if elapsed_time is not None:
            log_message += f" in {elapsed_time:.3f}s"
        
        # Выбираем уровень логирования на основе статус-кода
        log_level = self.log_level
        if status >= 500:
            log_level = logging.ERROR
        elif status >= 400:
            log_level = logging.WARNING
        
        self.logger.log(log_level, log_message)
        
        # Логируем заголовки ответа на уровне DEBUG
        if self.logger.isEnabledFor(logging.DEBUG):
            headers = dict(getattr(response, 'headers', {}))
            self.logger.debug(f"<<< Response headers: {headers}")
        
        # Логируем тело ответа, если включено
        if self.log_response_body and self.logger.isEnabledFor(logging.DEBUG):
            try:
                data = getattr(response, 'data', None)
                if data:
                    if isinstance(data, dict):
                        body = json.dumps(data, indent=2)
                        self.logger.debug(f"<<< Response body:\n{body}")
                    else:
                        # Ограничиваем длину для не-JSON данных
                        body_str = str(data)
                        if len(body_str) > 1000:
                            body_str = f"{body_str[:997]}..."
                        self.logger.debug(f"<<< Response body: {body_str}")
            except Exception as e:
                self.logger.debug(f"Failed to log response body: {e}")
    
    def _log_error(self, error, request_info: Dict[str, Any] = None) -> None:
        """
        Логирование ошибки.
        
        Args:
            error: Исключение, которое произошло
            request_info: Информация о запросе, во время которого произошла ошибка
        """
        if not self.logger:
            return
        
        if request_info:
            method = request_info.get('method', 'unknown')
            url = request_info.get('url', 'unknown')
            retry = request_info.get('retry', 0)
            
            log_message = f"!!! Error during {method} {url} (retry #{retry}): {error}"
        else:
            log_message = f"!!! Request error: {error}"
        
        self.logger.error(log_message, exc_info=True)
    
    def _mask_sensitive_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Маскирует чувствительные данные в заголовках для безопасного логирования.
        
        Args:
            headers: Исходные заголовки
            
        Returns:
            Заголовки с замаскированными чувствительными данными
        """
        if not headers:
            return {}
        
        sensitive_headers = [
            'authorization', 'x-api-key', 'api-key', 'apikey',
            'password', 'token', 'access-token', 'refresh-token', 
            'secret', 'client-secret', 'key'
        ]
        
        safe_headers = headers.copy()
        
        for header, value in safe_headers.items():
            header_lower = header.lower()
            if any(sensitive in header_lower for sensitive in sensitive_headers):
                # Если заголовок содержит префикс (например, Bearer), сохраняем его
                if isinstance(value, str) and ' ' in value:
                    prefix, _ = value.split(' ', 1)
                    safe_headers[header] = f"{prefix} ***masked***"
                else:
                    safe_headers[header] = "***masked***"
        
        return safe_headers
    
    def _refresh_oauth2_token(self) -> bool:
        """
        Обновление OAuth 2.0 токена.
        Базовая реализация - должна быть переопределена в конкретных классах.
        
        Returns:
            True если обновление успешно, False в противном случае
        """
        self.logger.warning("OAuth 2.0 token refresh not implemented in the base class.")
        return False
    
    @abstractmethod
    def request(self, config: Dict[str, Any]) -> Response:
        """
        Выполнение HTTP запроса.
        
        Args:
            config: Конфигурация запроса
            
        Returns:
            Объект ответа
        """
        pass
    
    @abstractmethod
    def get(self, url: str, **kwargs) -> Response:
        """Выполнение GET запроса."""
        pass
    
    @abstractmethod
    def post(self, url: str, data=None, **kwargs) -> Response:
        """Выполнение POST запроса."""
        pass
    
    @abstractmethod
    def put(self, url: str, data=None, **kwargs) -> Response:
        """Выполнение PUT запроса."""
        pass
    
    @abstractmethod
    def delete(self, url: str, **kwargs) -> Response:
        """Выполнение DELETE запроса."""
        pass
    
    @abstractmethod
    def patch(self, url: str, data=None, **kwargs) -> Response:
        """Выполнение PATCH запроса."""
        pass
    
    @abstractmethod
    def close(self):
        """Закрытие сессии."""
        pass
    
    def __enter__(self):
        """Поддержка контекстного менеджера."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Закрытие при выходе из контекстного менеджера."""
        self.close()


class SyncHttpClient(BaseHttpClient):
    """
    Синхронный HTTP клиент.
    Использует библиотеку requests для выполнения запросов.
    """
    
    def __init__(self, session=None, **kwargs):
        """
        Инициализация синхронного клиента.
        
        Args:
            session: Сессия requests (опционально)
            **kwargs: Аргументы для базового класса
        """
        super().__init__(**kwargs)
        self.session = session or requests.Session()
        
        # Добавляем стандартные исключения для повторных попыток
        if not self.retry_exceptions:
            self.retry_exceptions = [
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout
            ]
    
    def _refresh_oauth2_token(self) -> bool:
        """
        Обновление OAuth 2.0 токена с помощью refresh_token.
        
        Returns:
            True если обновление успешно, False в противном случае
        """
        if not all([
            self.auth.token_url,
            self.auth.client_id,
            self.auth.client_secret,
            self.auth.refresh_token
        ]):
            self.logger.error("Missing required OAuth2 parameters for token refresh")
            return False
        
        self.logger.info("Refreshing OAuth2 token")
        
        try:
            response = requests.post(
                self.auth.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.auth.refresh_token,
                    "client_id": self.auth.client_id,
                    "client_secret": self.auth.client_secret
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.auth.token = token_data.get("access_token")
                
                # Обновляем refresh_token, если он предоставлен
                if "refresh_token" in token_data:
                    self.auth.refresh_token = token_data.get("refresh_token")
                
                # Устанавливаем время истечения токена
                if "expires_in" in token_data:
                    expires_in = token_data.get("expires_in", 3600)
                    self.auth.expires_at = time.time() + expires_in
                
                self.logger.info("OAuth2 token refreshed successfully")
                return True
            else:
                self.logger.error(f"Failed to refresh OAuth2 token: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error refreshing OAuth2 token: {e}")
            return False
    
    def request(self, config: Dict[str, Any]) -> Response:
        """
        Выполнение HTTP запроса с возможностью автоматического повтора.
        
        Args:
            config: Конфигурация запроса
            
        Returns:
            Объект ответа
        """
        prepared_config = self.prepare_request(config)
        
        # Логируем запрос
        self._log_request(
            prepared_config["method"],
            prepared_config["url"],
            prepared_config["headers"],
            prepared_config.get("data"),
            prepared_config.get("params")
        )
        
        retry_count = 0
        last_exception = None
        
        while retry_count <= self.max_retries:
            try:
                # Засекаем время начала запроса
                start_time = time.time()
                
                # Извлекаем параметры запроса
                url = prepared_config["url"]
                method = prepared_config["method"]
                timeout = prepared_config["timeout"]
                
                # Параметры для requests
                request_kwargs = {
                    "headers": prepared_config["headers"],
                    "timeout": timeout,
                    "params": prepared_config.get("params")
                }
                
                # Добавляем данные для методов, которые их поддерживают
                if method in ["POST", "PUT", "PATCH"]:
                    request_kwargs["data"] = prepared_config.get("data")
                
                # Выполняем запрос
                raw_response = self.session.request(method, url, **request_kwargs)
                
                # Вычисляем время выполнения
                elapsed_time = time.time() - start_time
                
                # Логируем ответ
                self._log_response(raw_response, elapsed_time)
                
                # Если получили статус код для повтора и не превысили лимит попыток
                if raw_response.status_code in self.retry_status_codes and retry_count < self.max_retries:
                    retry_count += 1
                    retry_delay = self.retry_delay * (self.retry_backoff ** retry_count)
                    
                    self.logger.warning(
                        f"Retrying {method} {url} due to status code {raw_response.status_code} "
                        f"(retry #{retry_count} after {retry_delay:.2f}s)"
                    )
                    
                    time.sleep(retry_delay)
                    continue
                
                # Обрабатываем ответ
                try:
                    if "application/json" in raw_response.headers.get("Content-Type", ""):
                        response_data = raw_response.json()
                    else:
                        response_data = raw_response.text
                except ValueError:
                    response_data = raw_response.text
                
                # Создаем объект ответа
                response_obj = Response(
                    status_code=raw_response.status_code,
                    headers=dict(raw_response.headers),
                    data=response_data,
                    raw_response=raw_response
                )
                
                # Проверяем статус ответа
                if raw_response.status_code >= 400:
                    error = Exception(f"HTTP Error: {raw_response.status_code}")
                    error.response = response_obj
                    return self.error_interceptor(error)
                
                # Применяем интерцептор ответа
                return self.response_interceptor(response_obj)
                
            except Exception as e:
                # Сохраняем последнюю ошибку
                last_exception = e
                
                # Логируем ошибку
                self._log_error(e, {
                    "method": prepared_config["method"],
                    "url": prepared_config["url"],
                    "retry": retry_count
                })
                
                # Проверяем, нужно ли повторять запрос для этого типа исключения
                should_retry = any(isinstance(e, exc_type) for exc_type in self.retry_exceptions)
                
                if should_retry and retry_count < self.max_retries:
                    retry_count += 1
                    retry_delay = self.retry_delay * (self.retry_backoff ** retry_count)
                    
                    self.logger.warning(
                        f"Retrying {prepared_config['method']} {prepared_config['url']} due to error: {e} "
                        f"(retry #{retry_count} after {retry_delay:.2f}s)"
                    )
                    
                    time.sleep(retry_delay)
                else:
                    return self.error_interceptor(e)
        
        # Если мы дошли сюда, значит, все попытки завершились неудачей
        return self.error_interceptor(last_exception)
    
    def get(self, url: str, **kwargs) -> Response:
        """Выполнение GET запроса."""
        return self.request({"url": url, "method": "GET", **kwargs})
    
    def post(self, url: str, data=None, **kwargs) -> Response:
        """Выполнение POST запроса."""
        return self.request({"url": url, "method": "POST", "data": data, **kwargs})
    
    def put(self, url: str, data=None, **kwargs) -> Response:
        """Выполнение PUT запроса."""
        return self.request({"url": url, "method": "PUT", "data": data, **kwargs})
    
    def delete(self, url: str, **kwargs) -> Response:
        """Выполнение DELETE запроса."""
        return self.request({"url": url, "method": "DELETE", **kwargs})
    
    def patch(self, url: str, data=None, **kwargs) -> Response:
        """Выполнение PATCH запроса."""
        return self.request({"url": url, "method": "PATCH", "data": data, **kwargs})
    
    def close(self):
        """Закрытие сессии."""
        self.session.close()


class AsyncHttpClient(BaseHttpClient):
    """
    Асинхронный HTTP клиент.
    Использует библиотеку aiohttp для выполнения запросов.
    """
    
    def __init__(self, session=None, **kwargs):
        """
        Инициализация асинхронного клиента.
        
        Args:
            session: Сессия aiohttp (опционально)
            **kwargs: Аргументы для базового класса
        """
        super().__init__(**kwargs)
        self._session = session
        self._own_session = False
        
        # Добавляем стандартные исключения для повторных попыток
        if not self.retry_exceptions:
            self.retry_exceptions = [
                aiohttp.ClientError,
                aiohttp.ClientConnectionError,
                aiohttp.ClientConnectorError,
                aiohttp.ClientOSError,
                aiohttp.ServerTimeoutError,
                aiohttp.ServerDisconnectedError,
                asyncio.TimeoutError
            ]
    
    async def _ensure_session(self):
        """Гарантирует наличие активной сессии."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
    
    async def _refresh_oauth2_token(self) -> bool:
        """
        Асинхронное обновление OAuth 2.0 токена с помощью refresh_token.
        
        Returns:
            True если обновление успешно, False в противном случае
        """
        if not all([
            self.auth.token_url,
            self.auth.client_id,
            self.auth.client_secret,
            self.auth.refresh_token
        ]):
            self.logger.error("Missing required OAuth2 parameters for token refresh")
            return False
        
        self.logger.info("Refreshing OAuth2 token")
        
        try:
            # Гарантируем наличие сессии
            await self._ensure_session()
            
            async with self._session.post(
                self.auth.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.auth.refresh_token,
                    "client_id": self.auth.client_id,
                    "client_secret": self.auth.client_secret
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.auth.token = token_data.get("access_token")
                    
                    # Обновляем refresh_token, если он предоставлен
                    if "refresh_token" in token_data:
                        self.auth.refresh_token = token_data.get("refresh_token")
                    
                    # Устанавливаем время истечения токена
                    if "expires_in" in token_data:
                        expires_in = token_data.get("expires_in", 3600)
                        self.auth.expires_at = time.time() + expires_in
                    
                    self.logger.info("OAuth2 token refreshed successfully")
                    return True
                else:
                    response_text = await response.text()
                    self.logger.error(f"Failed to refresh OAuth2 token: {response_text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error refreshing OAuth2 token: {e}")
            return False
    
    async def request(self, config: Dict[str, Any]) -> Response:
        """
        Выполнение асинхронного HTTP запроса с возможностью автоматического повтора.
        
        Args:
            config: Конфигурация запроса
            
        Returns:
            Объект ответа
        """
        prepared_config = self.prepare_request(config)
        
        # Логируем запрос
        self._log_request(
            prepared_config["method"],
            prepared_config["url"],
            prepared_config["headers"],
            prepared_config.get("data"),
            prepared_config.get("params")
        )
        
        # Гарантируем наличие сессии
        await self._ensure_session()
        
        retry_count = 0
        last_exception = None
        
        while retry_count <= self.max_retries:
            try:
                # Засекаем время начала запроса
                start_time = time.time()
                
                # Извлекаем параметры запроса
                url = prepared_config["url"]
                method = prepared_config["method"]
                timeout = aiohttp.ClientTimeout(total=prepared_config["timeout"])
                
                # Параметры для aiohttp
                request_kwargs = {
                    "headers": prepared_config["headers"],
                    "timeout": timeout,
                    "params": prepared_config.get("params")
                }
                
                # Добавляем данные для методов, которые их поддерживают
                if method in ["POST", "PUT", "PATCH"]:
                    request_kwargs["data"] = prepared_config.get("data")
                
                # Выполняем запрос
                async with self._session.request(method, url, **request_kwargs) as raw_response:
                    # Вычисляем время выполнения
                    elapsed_time = time.time() - start_time
                    
                    # Логируем ответ
                    self._log_response(raw_response, elapsed_time)
                    
                    # Если получили статус код для повтора и не превысили лимит попыток
                    if raw_response.status in self.retry_status_codes and retry_count < self.max_retries:
                        retry_count += 1
                        retry_delay = self.retry_delay * (self.retry_backoff ** retry_count)
                        
                        self.logger.warning(
                            f"Retrying {method} {url} due to status code {raw_response.status} "
                            f"(retry #{retry_count} after {retry_delay:.2f}s)"
                        )
                        
                        await asyncio.sleep(retry_delay)
                        continue
                    
                    # Обрабатываем ответ
                    content_type = raw_response.headers.get("Content-Type", "")
                    
                    if "application/json" in content_type:
                        response_data = await raw_response.json()
                    else:
                        response_data = await raw_response.text()
                    
                    # Создаем объект ответа
                    response_obj = Response(
                        status_code=raw_response.status,
                        headers=dict(raw_response.headers),
                        data=response_data,
                        raw_response=raw_response
                    )
                    
                    # Проверяем статус ответа
                    if raw_response.status >= 400:
                        error = Exception(f"HTTP Error: {raw_response.status}")
                        error.response = response_obj
                        return self.error_interceptor(error)
                    
                    # Применяем интерцептор ответа
                    return self.response_interceptor(response_obj)
                    
            except Exception as e:
                # Сохраняем последнюю ошибку
                last_exception = e
                
                # Логируем ошибку
                self._log_error(e, {
                    "method": prepared_config["method"],
                    "url": prepared_config["url"],
                    "retry": retry_count
                })
                
                # Проверяем, нужно ли повторять запрос для этого типа исключения
                should_retry = any(isinstance(e, exc_type) for exc_type in self.retry_exceptions)
                
                if should_retry and retry_count < self.max_retries:
                    retry_count += 1
                    retry_delay = self.retry_delay * (self.retry_backoff ** retry_count)
                    
                    self.logger.warning(
                        f"Retrying {prepared_config['method']} {prepared_config['url']} due to error: {e} "
                        f"(retry #{retry_count} after {retry_delay:.2f}s)"
                    )
                    
                    await asyncio.sleep(retry_delay)
                else:
                    return self.error_interceptor(e)
        
        # Если мы дошли сюда, значит, все попытки завершились неудачей
        return self.error_interceptor(last_exception)
    
    async def get(self, url: str, **kwargs) -> Response:
        """Выполнение асинхронного GET запроса."""
        return await self.request({"url": url, "method": "GET", **kwargs})
    
    async def post(self, url: str, data=None, **kwargs) -> Response:
        """Выполнение асинхронного POST запроса."""
        return await self.request({"url": url, "method": "POST", "data": data, **kwargs})
    
    async def put(self, url: str, data=None, **kwargs) -> Response:
        """Выполнение асинхронного PUT запроса."""
        return await self.request({"url": url, "method": "PUT", "data": data, **kwargs})
    
    async def delete(self, url: str, **kwargs) -> Response:
        """Выполнение асинхронного DELETE запроса."""
        return await self.request({"url": url, "method": "DELETE", **kwargs})
    
    async def patch(self, url: str, data=None, **kwargs) -> Response:
        """Выполнение асинхронного PATCH запроса."""
        return await self.request({"url": url, "method": "PATCH", "data": data, **kwargs})
    
    async def close(self):
        """Закрытие асинхронной сессии."""
        if self._session and self._own_session:
            await self._session.close()
            self._session = None
    
    def close(self):
        """Реализация метода close из базового класса."""
        # Для совместимости с синхронным интерфейсом
        pass
    
    async def __aenter__(self):
        """Поддержка асинхронного контекстного менеджера."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие при выходе из асинхронного контекстного менеджера."""
        await self.close()


def create_http_client(
    async_mode: bool = False,
    
    # Общие параметры
    base_url: str = "",
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    
    # Параметры аутентификации
    auth_type: Optional[str] = None,
    token: Optional[str] = None,
    token_header: str = "Authorization",
    token_prefix: str = "Bearer ",
    
    # OAuth2 параметры
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    token_url: Optional[str] = None,
    refresh_token: Optional[str] = None,
    
    # Интерцепторы
    request_interceptor: Optional[Callable] = None,
    response_interceptor: Optional[Callable] = None,
    error_interceptor: Optional[Callable] = None,
    
    # Настройки повторных попыток
    max_retries: int = 0,
    retry_delay: float = 0.1,
    retry_backoff: float = 2.0,
    retry_status_codes: Optional[List[int]] = None,
    retry_exceptions: Optional[List[Type[Exception]]] = None,
    
    # Другие параметры
    session = None,
    logger: Optional[logging.Logger] = None,
    log_level: int = logging.INFO,
    log_request_body: bool = False,
    log_response_body: bool = False
) -> Union[SyncHttpClient, AsyncHttpClient]:
    """
    Создает и возвращает HTTP клиент нужного типа.
    
    Args:
        async_mode: Флаг для создания асинхронного клиента (True) или синхронного (False)
        
        base_url: Базовый URL для всех запросов
        headers: Заголовки по умолчанию
        timeout: Таймаут по умолчанию в секундах
        
        auth_type: Тип аутентификации ("jwt" или "oauth2")
        token: Токен для аутентификации (JWT или OAuth2 access_token)
        token_header: Имя заголовка для токена (по умолчанию "Authorization")
        token_prefix: Префикс для токена в заголовке (по умолчанию "Bearer ")
        
        client_id: Идентификатор клиента для OAuth2
        client_secret: Секрет клиента для OAuth2
        token_url: URL для получения/обновления токена OAuth2
        refresh_token: Токен обновления для OAuth2
        
        request_interceptor: Функция для обработки запроса перед отправкой
        response_interceptor: Функция для обработки ответа
        error_interceptor: Функция для обработки ошибок
        
        max_retries: Максимальное количество повторных попыток при ошибках
        retry_delay: Начальная задержка между повторными попытками (в секундах)
        retry_backoff: Множитель для экспоненциальной задержки
        retry_status_codes: Список HTTP-кодов, при которых нужно повторять запрос
        retry_exceptions: Список исключений, при которых нужно повторять запрос
        
        session: Сессия для клиента (опционально)
        logger: Логгер для записи информации о запросах и ответах
        log_level: Уровень логирования
        log_request_body: Флаг для логирования тела запроса
        log_response_body: Флаг для логирования тела ответа
        
    Returns:
        Синхронный или асинхронный HTTP клиент
    """
    # Преобразуем строковый auth_type в перечисление, если нужно
    enum_auth_type = None
    if auth_type:
        try:
            enum_auth_type = AuthType[auth_type.upper()]
        except (KeyError, AttributeError):
            pass
    
    common_args = {
        "base_url": base_url,
        "headers": headers,
        "timeout": timeout,
        "auth_type": enum_auth_type,
        "token": token,
        "token_header": token_header,
        "token_prefix": token_prefix,
        "client_id": client_id,
        "client_secret": client_secret,
        "token_url": token_url,
        "refresh_token": refresh_token,
        "request_interceptor": request_interceptor,
        "response_interceptor": response_interceptor,
        "error_interceptor": error_interceptor,
        "max_retries": max_retries,
        "retry_delay": retry_delay,
        "retry_backoff": retry_backoff,
        "retry_status_codes": retry_status_codes,
        "retry_exceptions": retry_exceptions,
        "session": session,
        "logger": logger,
        "log_level": log_level,
        "log_request_body": log_request_body,
        "log_response_body": log_response_body
    }
    
    if async_mode:
        return AsyncHttpClient(**common_args)
    else:
        return SyncHttpClient(**common_args)


def raise_error(error):
    """
    Хелпер-функция для повторного возбуждения исключения.
    
    Args:
        error: Исключение для возбуждения
        
    Raises:
        Exception: Исходное исключение
    """
    raise error


# Классы-наследники для удобного использования различных типов аутентификации

class JwtHttpClient(SyncHttpClient):
    """HTTP клиент с JWT аутентификацией."""
    
    def __init__(self, base_url: str, jwt_token: str, **kwargs):
        """
        Инициализация JWT клиента.
        
        Args:
            base_url: Базовый URL
            jwt_token: JWT токен
            **kwargs: Дополнительные параметры
        """
        super().__init__(
            base_url=base_url,
            auth_type=AuthType.JWT,
            token=jwt_token,
            **kwargs
        )


class OAuth2HttpClient(SyncHttpClient):
    """HTTP клиент с OAuth 2.0 аутентификацией."""
    
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        token_url: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        **kwargs
    ):
        """
        Инициализация OAuth2 клиента.
        
        Args:
            base_url: Базовый URL
            client_id: Идентификатор клиента
            client_secret: Секрет клиента
            token_url: URL для получения/обновления токена
            access_token: Начальный токен доступа (опционально)
            refresh_token: Токен обновления (опционально)
            **kwargs: Дополнительные параметры
        """
        super().__init__(
            base_url=base_url,
            auth_type=AuthType.OAUTH2,
            token=access_token,
            client_id=client_id,
            client_secret=client_secret,
            token_url=token_url,
            refresh_token=refresh_token,
            **kwargs
        )
    
    def authenticate(self, username: str, password: str) -> bool:
        """
        Аутентификация с использованием учетных данных пользователя (Resource Owner Password Grant).
        
        Args:
            username: Имя пользователя
            password: Пароль
            
        Returns:
            True при успешной аутентификации, False при ошибке
        """
        try:
            response = requests.post(
                self.auth.token_url,
                data={
                    "grant_type": "password",
                    "username": username,
                    "password": password,
                    "client_id": self.auth.client_id,
                    "client_secret": self.auth.client_secret
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.auth.token = token_data.get("access_token")
                self.auth.refresh_token = token_data.get("refresh_token")
                
                if "expires_in" in token_data:
                    expires_in = token_data.get("expires_in", 3600)
                    self.auth.expires_at = time.time() + expires_in
                
                return True
            else:
                self.logger.error(f"Authentication failed: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during authentication: {e}")
            return False


class AsyncJwtHttpClient(AsyncHttpClient):
    """Асинхронный HTTP клиент с JWT аутентификацией."""
    
    def __init__(self, base_url: str, jwt_token: str, **kwargs):
        """
        Инициализация асинхронного JWT клиента.
        
        Args:
            base_url: Базовый URL
            jwt_token: JWT токен
            **kwargs: Дополнительные параметры
        """
        super().__init__(
            base_url=base_url,
            auth_type=AuthType.JWT,
            token=jwt_token,
            **kwargs
        )


class AsyncOAuth2HttpClient(AsyncHttpClient):
    """Асинхронный HTTP клиент с OAuth 2.0 аутентификацией."""
    
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        token_url: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        **kwargs
    ):
        """
        Инициализация асинхронного OAuth2 клиента.
        
        Args:
            base_url: Базовый URL
            client_id: Идентификатор клиента
            client_secret: Секрет клиента
            token_url: URL для получения/обновления токена
            access_token: Начальный токен доступа (опционально)
            refresh_token: Токен обновления (опционально)
            **kwargs: Дополнительные параметры
        """
        super().__init__(
            base_url=base_url,
            auth_type=AuthType.OAUTH2,
            token=access_token,
            client_id=client_id,
            client_secret=client_secret,
            token_url=token_url,
            refresh_token=refresh_token,
            **kwargs
        )
    
    async def authenticate(self, username: str, password: str) -> bool:
        """
        Асинхронная аутентификация с использованием учетных данных пользователя.
        
        Args:
            username: Имя пользователя
            password: Пароль
            
        Returns:
            True при успешной аутентификации, False при ошибке
        """
        try:
            # Гарантируем наличие сессии
            await self._ensure_session()
            
            async with self._session.post(
                self.auth.token_url,
                data={
                    "grant_type": "password",
                    "username": username,
                    "password": password,
                    "client_id": self.auth.client_id,
                    "client_secret": self.auth.client_secret
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.auth.token = token_data.get("access_token")
                    self.auth.refresh_token = token_data.get("refresh_token")
                    
                    if "expires_in" in token_data:
                        expires_in = token_data.get("expires_in", 3600)
                        self.auth.expires_at = time.time() + expires_in
                    
                    return True
                else:
                    response_text = await response.text()
                    self.logger.error(f"Authentication failed: {response_text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error during authentication: {e}")
            return False