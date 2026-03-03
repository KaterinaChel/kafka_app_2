import faust
import re
import json

app = faust.App(
    "filtered-app",
    broker="kafka-0:9092,kafka-1:9092,kafka-2:9092",
    value_serializer="json",
    producer_acks="all",
    producer_max_retries=5
)

class UserMessage(faust.Record):

    """Модель сообщения чата"""

    user_id: str
    message: str

class UserBlock(faust.Record):

    """Управление блокировками пользователя"""

    block_id: str
    action: str

class WordBlock(faust.Record):

    """Управление списком плохих слов"""

    word: str
    action: str

# Таблицы
user_blocked = app.Table('user_blocked', default=set,partitions=3)
bad_words = app.Table('bad_words', default=set,partitions=1)

# Топики kraft
input_topic = app.topic("messages", key_type=str, value_type=UserMessage,partitions=4)
blocked_users = app.topic('blocks-topic', key_type=str, value_type=UserBlock,partitions=3)
bad_words_topic = app.topic('bad-words-topic', key_type=str, value_type=WordBlock,partitions=1)
output_topic = app.topic("filtered_messages", key_type=str, value_type=UserMessage,partitions=4)

@app.agent(blocked_users)
async def update_blocks(stream) -> None:

    """Обновляет таблицу блокировок пользователей из blocks-topic.

    Args:
        stream: Поток сообщений блокировок (key=receiver_id)

    Пример:
        send blocks-topic '{"block_id": "user1", "action": "block"}' -k receiver4
        user_blocked['receiver4'] = {'user1'}
    """

    async for receiver_id, event in stream.items():
        blocks_set = user_blocked[receiver_id]
        if event.action == 'block':
            blocks_set.add(event.block_id)
        elif event.action == 'unblock':
            blocks_set.discard(event.block_id)
        user_blocked[receiver_id] = blocks_set

@app.agent(bad_words_topic)
async def update_bad_words(stream) -> None:

    """Динамически обновляет список плохих слов.

    Args:
        stream: Поток команд (key=global)

    Примеры:
         add: '{"word": "ass", "action": "add"}' -k global
         remove: '{"word": "ass", "action": "remove"}' -k global
    """

    async for _, event in stream.items():
        bad_set = set(bad_words['global'])
        if event.action == 'add' and event.word.lower() not in bad_set:
            bad_set.add(event.word.lower())
        elif event.action == 'remove' and event.word.lower() in bad_set:
            bad_set.discard(event.word.lower())
        bad_words['global'] = bad_set

@app.agent(input_topic)  
async def process_messages(stream) -> None:

    """Основной агент: 
        - Блокирует сообщения от пользователей из user_blocked
        - Очищает сообщения от плохих слов из bad_words
    Отправляет сообщения в топик filtered_messages

    Args:
        stream: Входящие сообщения чата
    """

    async for key,msg in stream.items():
        # Фильтр 1: БЛОКИРОВКИ
        blocked_senders = user_blocked[key]
        if msg.user_id in blocked_senders:
            app.log.info(f"BLOCKED: '{msg.user_id}")
            continue

        original_text = msg.message
        cleaned_text = original_text
            
        # Фильтр 2: ПЛОХИЕ СЛОВА
        bad_words_set = bad_words['global']
        for bad_word in bad_words_set:
            if not bad_word:
                continue
            
            pattern = re.compile(rf'\b{re.escape(bad_word)}\b', re.IGNORECASE)

            if pattern.search(cleaned_text):
                cleaned_text = pattern.sub('*' * len(bad_word), cleaned_text)
        
        if cleaned_text != original_text:
            app.log.info(f"CLEANED: '{original_text}' → '{cleaned_text}'")
        
        key_cleaned=key
        cleaned_msg = UserMessage(
            user_id=msg.user_id,
            message=cleaned_text
        )
        await output_topic.send(value=cleaned_msg,key=key_cleaned)
            

            

