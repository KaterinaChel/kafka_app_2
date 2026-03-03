# kafka_app_2
Назначение приложения: потоковая обработка сообщений Kafka с фильтрацией сообщений от заблокированных пользователей и плохих слов

Технологии: Faust (Python Stream Processing) + Kafka KRAFT (3 брокера)

Вход: сырые сообщения → фильтрация → выход в filtered_messages

3 класса:UserMassage(Модель сообщения чата), UserBlock(Управление блокировками пользователя), WordBlock(Управление списком плохих слов)

3 агента: Обновление списка заблокированных юзеров, Обновление списка плохих слов, Фильтрация сообщений

Инструкция по запуску и тестированию

# 1 Поднимаем контейнеры
docker-compose up -d

# 2 Создание топиков
docker exec kafka_study-kafka-0-1 kafka-topics.sh --create --topic messages --partitions 4 --replication-factor 3 --bootstrap-server localhost:9092

docker exec kafka_study-kafka-0-1 kafka-topics.sh --create --topic blocks-topic --partitions 3 --replication-factor 3 --bootstrap-server localhost:9092

docker exec kafka_study-kafka-0-1 kafka-topics.sh --create --topic bad-words-topic --partitions 1 --replication-factor 3 --bootstrap-server localhost:9092

docker exec kafka_study-kafka-0-1 kafka-topics.sh --create --topic filtered_messages --partitions 4 --replication-factor 3 --bootstrap-server localhost:9092


# 3 Тест (из докер контейнера)
docker exec -it kafka_study-faust-1 bash

faust -A agent_filter send blocks-topic '{"block_id": "user1", "action": "block"}' -k receiver4 #добавляем заблокированного

faust -A agent_filter send bad-words-topic '{"word": "ass", "action": "add"}' -k global #добавляем плохое слово

faust -A agent_filter send bad-words-topic '{"word": "spam", "action": "add"}' -k global #добавляем плохое слово

faust -A agent_filter send messages '{"user_id": "user2", "message": "hello spam"}' -k receiver4 #фильтрация перед filtered_messages

faust -A agent_filter send messages '{"user_id": "user2", "message": "hello ass"}' -k receiver4 #фильтрация перед filtered_messages

faust -A agent_filter send messages '{"user_id": "user2", "message": "hello"}' -k receiver4 #проходит целиком

exit
