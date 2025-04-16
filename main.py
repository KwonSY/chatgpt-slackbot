import os
import time
import base64
import requests
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

# 사용자별 스레드 저장용 딕셔너리
user_threads = {}
threads_file = "threads.json"

# 서버 시작 시 스레드 복원
if os.path.exists(threads_file):
    with open(threads_file, "r") as f:
        user_threads = json.load(f)

# 저장 함수
def save_threads():
    with open(threads_file, "w") as f:
        json.dump(user_threads, f)

# 메시지 핸들러
@app.message(".*")
def handle_message_or_image(message, say, logger):
    logger.warning("message = " + str(message))
    user_id = message['user']
    text = message['text']
    files = event.get("files", [])
    logger.info(f"User ({user_id}) said: {text}")

    # 유저 스레드 초기화
    if text.strip().lower() == "/reset":
        thread = client.beta.threads.create()
        user_threads[user_id] = thread.id
        save_threads()
        say(f"<@{user_id}> 대화가 초기화되었어요! 새로 시작해볼까요?")
        return

    # 이미지가 있는 경우 GPT-4-Vision 사용
    if files:
        for file_info in files:
            if file_info.get("mimetype", "").startswith("image"):
                try:
                    image_url = file_info.get("url_private_download")
                    mime_type = file_info.get("mimetype", "image/jpeg")
                    headers = {"Authorization": f"Bearer {bot_token}"}
                    response = requests.get(image_url, headers=headers)

                    if response.status_code == 200:
                        image_base64 = base64.b64encode(response.content).decode("utf-8")

                        # 이미지 + 텍스트로 vision 모델 호출
                        result = client.chat.completions.create(
                            model="gpt-4-vision-preview",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": text or "이 이미지를 설명해줘."},
                                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}}
                                    ]
                                }
                            ],
                            max_tokens=1000
                        )
                        result_text = result.choices[0].message.content.strip()
                        say(f"<@{user_id}> {result_text}")
                        return
                    else:
                        say(f"<@{user_id}> 이미지를 불러오지 못했어요 😥")
                        return

                except Exception as e:
                    logger.error(f"이미지 처리 오류: {e}")
                    say(f"<@{user_id}> 이미지를 처리하는 중 문제가 발생했어요 😥")
                    return

    # 이미지 없고 텍스트만 있는 경우: 어시스턴트 thread 사용
    try:
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

        # 완료 대기
        max_wait = 15
        waited = 0
        while waited < max_wait:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            if run_status.status == "completed":
                break
            time.sleep(1)
            waited += 1
        else:
            say(f"<@{user_id}> GPT 응답 시간이 너무 오래 걸려서 중단했어요 😥")
            return

        messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc")
        assistant_messages = [m for m in messages.data if m.role == "assistant"]
        last_message = assistant_messages[0].content[0].text.value if assistant_messages else "(응답 없음)"
        logger.warning("last_message = " + str(last_message))
        say(f"<@{user_id}> {last_message}")

    except Exception as e:
        logger.error(f"텍스트 처리 오류: {e}")
        say(f"<@{user_id}> GPT 응답 중 오류가 발생했어요. 잠시 후 다시 시도해 주세요.")

#앱 실행
if __name__ == "__main__":
    SocketModeHandler(app, app_token).start()
