import os
import time
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI

#API 키 세팅
app_token = os.environ.get("SLACK_APP_TOKEN")
bot_token = os.environ.get("SLACK_BOT_TOKEN")
open_api_key = os.environ.get("OPENAI_API_KEY")
assistant_id = os.environ.get("OPENAI_ASSISTANT_ID")

#OpenAI 및 Slack 앱 초기화
client = OpenAI(api_key=open_api_key)
app = App(token=bot_token)

# 사용자별 스레드 저장용 딕셔너리 (간단한 메모리 저장, 서버 재시작 시 초기화됨)
user_threads = {}

# 메시지 핸들러
@app.message(".*")
def handle_message(message, say, logger):
    logger.warning("message = " + str(message))
    user_id = message['user']
    user_message = message['text']
    logger.warning(f"User ({user_id}) said: {user_message}")
    
    try:
        # 사용자 스레드가 없다면 생성
        if user_id not in user_threads:
            thread = client.beta.threads.create()
            user_threads[user_id] = thread.id
            logger.info(f"Created new thread for user {user_id}: {thread.id}")

        thread_id = user_threads[user_id]
        
        # 메시지를 스레드에 추가
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_message
        )

        # 어시스턴트 실행
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        logger.warning(run)
        
        # 응답 대기 (간단히 폴링)
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            
            if run_status.status == "completed":
                break

        # 응답 메시지 가져오기
        messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc")
        logger.warning("messages = " + str(messages))
        assistant_messages = [m for m in messages.data if m.role == "assistant"]
        last_message = assistant_messages[0].content[0].text.value if assistant_messages else "(응답 없음)"
        logger.warning("last_message = " + str(last_message))
        
        say(f"<@{user_id}> {last_message}")

    except Exception as e:
        logger.exception("Assistant API 오류 발생")
        say(f"<@{user_id}> GPT 응답 중 오류가 발생했어요. 잠시 후 다시 시도해 주세요.")

#앱 실행
if __name__ == "__main__":
    SocketModeHandler(app, app_token).start()
