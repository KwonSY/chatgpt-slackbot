import os
import dotenv
import time
from subprocess import call
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI

#환경변수 불러오기
dotenv.load_dotenv()

#API 키 세팅
app_token = os.environ.get("SLACK_APP_TOKEN")
bot_token = os.environ.get("SLACK_BOT_TOKEN")
open_api_key = os.environ.get("OPENAI_API_KEY")
assistant_id = os.environ.get("OPENAI_ASSISTANT_ID")

assert open_api_key and app_token and bot_token and assistant_id, "필요한 환경변수를 설정해주세요."

#OpenAI 및 Slack 앱 초기화
client = OpenAI(api_key=open_api_key)
app = App(token=bot_token)

with open('requirements.txt', encoding='utf-8-sig',mode='r') as file:
    for library_name in file.readlines():
        call("pip install " + library_name, shell=True)


# 메시지 핸들러
@app.message(".*")
def handle_message(message, say, logger):
    user = message['user']
    user_message = message['text']
    logger.info(f"User ({user}) said: {user_message}")
    
    try:
        # GPT-4에게 질문 보내기
        response = client.chat.completions.create(
            model="gpt-4",  # 또는 "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message}
            ]
        )

        # 응답 텍스트 추출
        answer = response.choices[0].message.content.strip()

        # Slack에 응답
        say(f"<@{user}> {answer}")

    except OpenAIError as e:
        logger.error(f"OpenAI API 오류: {e}")
        say("⚠️ GPT 응답 중 문제가 발생했어요. 나중에 다시 시도해 주세요.")

#앱 실행
if __name__ == "__main__":
    SocketModeHandler(app, app_token).start()
