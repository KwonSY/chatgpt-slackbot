import os
import time
import base64
import requests
import json
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI

# API 키 세팅
app_token = os.environ.get("SLACK_APP_TOKEN")
bot_token = os.environ.get("SLACK_BOT_TOKEN")
open_api_key = os.environ.get("OPENAI_API_KEY")
assistant_id = os.environ.get("OPENAI_ASSISTANT_ID")

# 클라이언트 초기화
client = OpenAI(api_key=open_api_key)
app = App(token=bot_token)

# 유저별 thread_id 저장
user_threads = {}
threads_file = "threads.json"

# 서버 시작 시 스레드 복원
if os.path.exists(threads_file):
    with open(threads_file, "r") as f:
        user_threads = json.load(f)

def save_threads():
    with open(threads_file, "w") as f:
        json.dump(user_threads, f)

@app.event("message")
def handle_message_or_image(event, say, logger):
    # 메시지 전송자가 봇인지 확인 (자기 자신 메시지 무시)
    if "subtype" in event and event["subtype"] == "bot_message":
        return
        
    logger.warning("event = " + str(event))
    user_id = event.get("user")
    text = event.get("text", "")
    files = event.get("files", [])

    # 유저 스레드 초기화
    if text.strip().lower() == "/reset":
        thread = client.beta.threads.create()
        user_threads[user_id] = thread.id
        save_threads()
        say(f"<@{user_id}> 대화가 초기화되었어요! 새로 시작해볼까요?")
        return

    try:
        #이미지 처리 코드 잠시삭제
        
        # 이미지 없고 텍스트만 있는 경우: 어시스턴트 thread 사용
        if user_id not in user_threads:
            thread = client.beta.threads.create()
            user_threads[user_id] = thread.id
            save_threads()

        thread_id = user_threads[user_id]

        # 메시지 추가
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=text
        )

        # 실행
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )

        # 최대 15초 기다리기
        for _ in range(15):
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            if run_status.status == "completed":
                break
            time.sleep(1)
        else:
            say(f"<@{user_id}> GPT 응답 시간이 너무 오래 걸려서 중단했어요 😥")
            return

        messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc")
        assistant_messages = [m for m in messages.data if m.role == "assistant"]
        last_message = assistant_messages[0].content[0].text.value if assistant_messages else "(응답 없음)"
        
        say(f"<@{user_id}> {last_message}")

    except Exception as e:
        logger.error(f"텍스트 처리 오류: {e}")
        say(f"<@{user_id}> GPT 응답 중 오류가 발생했어요. 잠시 후 다시 시도해 주세요.")

if __name__ == "__main__":
    SocketModeHandler(app, app_token).start()
