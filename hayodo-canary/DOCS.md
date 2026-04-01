# Документация аддона Ayodo для Home Assistant

## Описание

Аддон Ayodo создает защищенный туннель к вашему Home Assistant, позволяя получить к нему доступ через домен ayodo.ru с использованием SSL-сертификата Let's Encrypt.

## Установка

Добавьте репозиторий и установите аддон в ваш Home Assistant.

### Добавление репозитория

Для добавленя репозитория:

1. Нажмите на кнопку и перейдите в ваш Home Assistant по локальному адресу.

[![Установить аддон в Home Assistant.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fayodoru%2Fha-addon)

2. Далее нажмите `+ Добавить`

![img.png](./assets/add-repo-button.png)

Если не получается автоматически через кнопку, то добавьте репозиторай вручную:
1. Перейдите в раздел  Settings > Add-ons (Настройки > Дополнения) в вашем Home Assistant.
2. Нажмите на кнопку в правом нижнем углу Add-on store (Магазин дополнений) 
3. Нажмите на три точки и там на Репозитории

 ![img.png](./assets/add-repo-menu.png)

4. В поле `Добавить` вставьте URL репозитория: `https://github.com/ayodo/ha-addon`

![img.png](./assets/add-repo-button.png)

5. Нажмите на кнопку `+ Добавить`

### Установка аддона

1. Найдите аддон "Ayodo add-on" в Настройки -> Дополнениях и нажмите на него.
2. Нажмите "Install" для установки аддона.

## Конфигурация

После установки аддона перейдите на вкладку "Configuration" (Конфигурация) и заполните необходимые параметры:
1. Укажите Token дома из личного кабинета Ayodo.
2. Укажите Email, с которым регистрировались в Ayodo.
3. Установите флажок "Принять условия использования Let's Encrypt" (если хотите автоматически сгенерировать SSL-сертификат).

Остальные параметры можно оставить по умолчанию. 
Подробнее все параметры описаны ниже.

## Параметры

### Основные параметры

| Параметр       | Тип     | Обязательный                                              | Описание                                                                  |
|----------------|---------|-----------------------------------------------------------|---------------------------------------------------------------------------|
| `token`        | string  | Да                                                        | Токен доступа к сервису Ayodo (можно скопировать в личном кабинете Ayodo) |
| `email`        | string  | Да                                                        | Email для регистрации в Let's Encrypt                                     |
| `accept_terms` | boolean | Да (если хотите автоматичеки сгенерировать SSL-сертификат | Принятие условий использования Let's Encrypt                              |
| `local_host`   | string  | Нет (по умолчанию: "homeassistant")                       | Локальный хост для туннелирования                                         |
| `local_port`   | integer | Нет (по умолчанию: 8123)                                  | Локальный порт для туннелирования                                         |

### Параметры Let's Encrypt

| Параметр                  | Тип     | Обязательный                        | Описание                                                                               |
|---------------------------|---------|-------------------------------------|----------------------------------------------------------------------------------------|
| `lets_encrypt.algo`       | string  | Нет (по умолчанию: "secp384r1")     | Алгоритм шифрования (возможные значения: "rsa", "prime256v1", "secp384r1")             |
| `lets_encrypt.certfile`   | string  | Нет (по умолчанию: "fullchain.pem") | Имя файла сертификата                                                                  |
| `lets_encrypt.keyfile`    | string  | Нет (по умолчанию: "privkey.pem")   | Имя файла приватного ключа                                                             |
| `lets_encrypt.renew_days` | integer | Нет (по умолчанию: 30)              | Количество дней до истечения срока действия сертификата для автоматического обновления |

## Настройка

1. После настройки параметров нажмите "Save".
2. Перейдите на вкладку "Info" (Информация) и нажмите "Start" (Запустить) для запуска аддона.
3. После старта аддон автоматически автоматически сгенерирует SSL-сертификат от Let's Encrypt и создаст туннель к вашему Home Assistant.
4. Далее нужно настроить конфигурацию Home Assistant для подключения через SSL-сертификат.

### Конфигурация Home Assistant

В файл `configuration.yaml` в раздел `http` нужно добавить следующие строки:

```yaml
http:
  ssl_certificate: /ssl/fullchain.pem
  ssl_key: /ssl/privkey.pem
```
Если раздела `http` нет, нужно его добавить.
Редактировать `configuration.yaml` можно с помощью аддона File Editor [Настройки → Дополнения](https://my.home-assistant.io/create-link/?redirect=supervisor_store).

Для активации SSL-сертификата нужно перезапустить Home Assistant.

**!ВНИМАНИЕ!** 

После перезапуска для доступа к Home Assistant по локальному адресу нужно использовать https протокол. 
Т.е. в строке браузера нужно поменять http на https - `https://homeassistant.local:8123`.
После этого нужно разрешить доступ по непроверенному для локального адреса сертификату.

Но сертификат действителен для внешнего адреса. По нему можно будет настроить доступ к Home Assistant из внешней сети.

## Веб-интерфейс

На вкладке "Certificates" можно увидеть статус и срок действия сертификата.

## Поддерживаемые архитектуры

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg