# tg_vpn

VPN сервис бот на базе tg-core.
Поддерживает 3x-ui, легко переключается на другой провайдер.
Pre-action хук — гибкая воронка перед выдачей VPN.

## Что включено

- Выдача VPN подключения (новый аккаунт или существующий)
- Триальный период — бесплатные N дней для новых пользователей
- Продление подписки
- Статус подписки и данные подключения
- QR-код для быстрого подключения
- Pre-action хук — реклама, подписка на канал, оплата Stars
- Уведомления об истечении подписки через планировщик
- Инструкции по подключению для Android, iOS, Windows, macOS
- Полная админка из ядра + VPN команды

## Быстрый старт

### 1. Клонируй репозиторий

    git clone https://github.com/you/tg_vpn.git
    cd tg_vpn

### 2. Создай виртуальное окружение

    python -m venv .venv
    source .venv/bin/activate      # Linux/macOS
    .venv\Scripts\activate         # Windows

### 3. Экспортируй токен и установи зависимости

    export GITHUB_TOKEN=ghp_yourtoken
    pip install -r requirements.txt

### 4. Настрой окружение

    cp .env.example .env

Минимальный .env для запуска:

    BOT_TOKEN=123456:ABC...
    ADMIN_IDS=123456789
    DATABASE_URL=sqlite+aiosqlite:///vpn.db
    VPN_PROVIDER=xui
    XUI_PANEL_URL=https://your-panel.com:54321
    XUI_USERNAME=admin
    XUI_PASSWORD=your_password
    XUI_EXTERNAL_IP=1.2.3.4
    DEBUG=true

### 5. Создай схему БД

    # продакшн
    python create_schema.py

    # разработка — автосоздание при старте (DEBUG=true)

### 6. Запусти бота

    python main.py

---

## Структура проекта

    tg_vpn/
    ├── handlers/
    │   ├── start.py            — /start, /help
    │   ├── subscription.py     — получить, продлить, статус, подключение
    │   ├── profile.py          — личный кабинет
    │   └── instructions.py     — инструкции по платформам
    ├── services/
    │   ├── vpn_base.py         — абстрактный провайдер (контракт)
    │   ├── vpn_xui.py          — реализация для 3x-ui
    │   ├── vpn_service.py      — фабрика провайдеров
    │   ├── pre_action.py       — хук перед выдачей VPN
    │   └── scheduler.py        — уведомления об истечении
    ├── db/
    │   └── models.py           — User, Subscription, PreActionLog
    ├── admin.py                — /vpn_stats, /vpn_delete, /vpn_info
    ├── config.py               — VpnSettings
    ├── main.py                 — точка входа
    ├── create_schema.py        — создание схемы БД
    ├── requirements.txt
    ├── .env.example
    └── .gitignore

---

## Pre-action хук

Универсальная воронка которая выполняется перед выдачей или
продлением VPN. Шаги настраиваются в config.py:

    PRE_ACTION_STEPS = [
        {
            "type": "ad",
            "enabled": True,
            "text": "Наш партнёр — SuperVPN Pro",
            "duration": 5,
        },
        {
            "type": "channel",
            "enabled": True,
            "channel": "@my_channel",
            "message": "Подпишитесь на наш канал",
        },
        {
            "type": "stars_payment",
            "enabled": True,
            "amount": 50,
            "description": "VPN подписка на 30 дней",
        },
    ]

Каждый шаг независим — включай и выключай через enabled.
Порядок шагов = порядок в списке.
Пройденные шаги логируются — реклама не показывается повторно в тот же день.

Типы шагов:

    ad              — показывает текст, ждёт N секунд, продолжает автоматически
    channel         — проверяет подписку на канал, ждёт нажатия "Проверить"
    stars_payment   — создаёт инвойс Telegram Stars, ждёт successful_payment

---

## Переключение VPN провайдера

Чтобы переключиться на другой провайдер — одна строка в .env:

    VPN_PROVIDER=outline

Бот не замечает разницы — все провайдеры реализуют одинаковый контракт.

Чтобы добавить новый провайдер:

    1. Создай services/vpn_outline.py
    2. Унаследуй от BaseVpnProvider
    3. Реализуй 4 метода: create_account, renew_account, get_status, delete_account
    4. Добавь в фабрику в services/vpn_service.py
    5. Добавь настройки в config.py и .env.example

Контракт BaseVpnProvider:

    create_account(telegram_id, expiry_days, data_limit_gb, is_trial) -> VpnAccount
    renew_account(telegram_id, expiry_days, data_limit_gb)             -> VpnAccount
    get_status(telegram_id)                                            -> VpnStatus
    delete_account(telegram_id)                                        -> VpnDeleteResult

Правила контракта:
    — методы никогда не бросают исключения наружу
    — при ошибке возвращают dataclass с success=False и error=str
    — telegram_id используется как уникальный идентификатор клиента

---

## Админ команды

Базовые (из tg-core):

    /stats      — статистика пользователей + VPN статистика
    /broadcast  — рассылка всем пользователям
    /ban        — заблокировать пользователя
    /unban      — разблокировать пользователя
    /user       — информация о пользователе

VPN специфичные:

    /vpn_stats              — статистика подписок по провайдерам
    /vpn_info <telegram_id> — VPN аккаунт конкретного пользователя
    /vpn_delete <telegram_id> — удалить VPN аккаунт пользователя

---

## Переменные окружения

    Переменная              Обязательная    Дефолт          Описание
    BOT_TOKEN               да              —               Токен от @BotFather
    ADMIN_IDS               да              —               Telegram ID администраторов
    DATABASE_URL            да              sqlite://...    URL подключения к БД
    VPN_PROVIDER            нет             xui             Провайдер: xui|outline|amnezia
    XUI_PANEL_URL           да (для xui)    —               URL панели 3x-ui
    XUI_USERNAME            да (для xui)    —               Логин панели
    XUI_PASSWORD            да (для xui)    —               Пароль панели
    XUI_EXTERNAL_IP         да (для xui)    —               Внешний IP сервера
    XUI_SERVER_PORT         нет             443             Порт сервера
    XUI_INBOUND_ID          нет             1               ID inbound в панели
    EXPIRY_DAYS             нет             30              Срок подписки в днях
    DATA_LIMIT_GB           нет             0               Лимит трафика (0=безлимит)
    TRIAL_ENABLED           нет             true            Включить триал
    TRIAL_DAYS              нет             3               Длительность триала
    PAYMENT_ENABLED         нет             false           Включить оплату Stars
    PAYMENT_AMOUNT          нет             50              Стоимость в Stars
    NOTIFY_DAYS_BEFORE      нет             [3,1]           За сколько дней уведомлять
    DEBUG                   нет             false           Режим отладки
    GITHUB_TOKEN            да              —               Токен для установки tg-core

---

## Зависимости

Все базовые зависимости подтягиваются автоматически из tg-core.
Дополнительные зависимости специфичные для VPN:

    py3xui        — клиент для 3x-ui API
    qrcode[pil]   — генерация QR-кодов
    pillow        — обработка изображений
    apscheduler   — планировщик задач
