# Документация аддона Ayodo для Home Assistant

## Описание

Этот вариант аддона Ayodo устанавливается из заранее опубликованного образа `ghcr.io/ayodoru/hayodo` и не требует локальной сборки в Home Assistant.

Аддон создает защищенный туннель к вашему Home Assistant, позволяя получить к нему доступ через домен ayodo.ru с использованием SSL-сертификата Let's Encrypt.

## Установка

Добавьте репозиторий и установите аддон в ваш Home Assistant.

### Добавление репозитория

1. Нажмите на кнопку и перейдите в ваш Home Assistant по локальному адресу.

[![Установить аддон в Home Assistant.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fayodoru%2Fha-addon)

2. Если кнопка не сработала, добавьте репозиторий вручную через `Settings > Add-ons > Add-on store > ⋮ > Repositories`.
3. Вставьте URL репозитория: `https://github.com/ayodoru/ha-addon`

### Установка аддона

1. Найдите аддон `Ayodo add-on (prebuilt)` в списке дополнений.
2. Нажмите `Install` для установки аддона.
3. Home Assistant скачает готовый образ из `ghcr.io`, а не будет собирать его локально.

## Конфигурация

После установки аддона перейдите на вкладку `Configuration` и заполните необходимые параметры:

1. Укажите token дома из личного кабинета Ayodo.
2. Укажите email, с которым регистрировались в Ayodo.
3. Установите флажок принятия условий Let's Encrypt, если хотите автоматически сгенерировать SSL-сертификат.

## Параметры

### Основные параметры

| Параметр       | Тип     | Обязательный | Описание                                                                  |
|----------------|---------|--------------|---------------------------------------------------------------------------|
| `token`        | string  | Да           | Токен доступа к сервису Ayodo                                             |
| `email`        | string  | Да           | Email для регистрации в Let's Encrypt                                     |
| `accept_terms` | boolean | Нет          | Принятие условий использования Let's Encrypt                              |
| `local_host`   | string  | Нет          | Локальный хост для туннелирования, по умолчанию `homeassistant`           |
| `local_port`   | integer | Нет          | Локальный порт для туннелирования, по умолчанию `8123`                    |

### Параметры Let's Encrypt

| Параметр                  | Тип     | Обязательный | Описание                                                                  |
|---------------------------|---------|--------------|---------------------------------------------------------------------------|
| `lets_encrypt.algo`       | string  | Нет          | Алгоритм шифрования: `rsa`, `prime256v1` или `secp384r1`                  |
| `lets_encrypt.certfile`   | string  | Нет          | Имя файла сертификата                                                     |
| `lets_encrypt.keyfile`    | string  | Нет          | Имя файла приватного ключа                                                |
| `lets_encrypt.renew_days` | integer | Нет          | Количество дней до истечения срока действия для автоматического обновления |

## Настройка Home Assistant

После первого успешного запуска добавьте в `configuration.yaml`:

```yaml
http:
  ssl_certificate: /ssl/fullchain.pem
  ssl_key: /ssl/privkey.pem
```

Если раздела `http` нет, его нужно добавить. После этого перезапустите Home Assistant.

Для локального доступа используйте `https`, например: `https://homeassistant.local:8123`.
