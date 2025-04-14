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


# 이미지 메시지 처리
@app.event("message")
def handle_image_message(event, say, logger):
    files = event.get("files", [])
    text = event.get("text", "")
    user = event.get("user", "")

    if not files:
        return  # 이미지가 없으면 무시

    for file_info in files:
        if file_info["mimetype"].startswith("image/"):
            image_url = file_info["url_private_download"]
            headers = {"Authorization": f"Bearer {slack_bot_token}"}
            response = requests.get(image_url, headers=headers)

            if response.status_code == 200:
                image_bytes = response.content
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")

                logger.info("이미지 base64 인코딩 완료")

                gpt_response = client.chat.completions.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": text or "이 이미지를 설명해줘.",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_base64}"
                                    },
                                },
                            ],
                        }
                    ],
                    max_tokens=1000,
                )

                result_text = gpt_response.choices[0].message.content
                say(f"<@{user}> GPT의 응답입니다:\n{result_text}")
            else:
                logger.error("이미지 다운로드 실패")
                say(f"<@{user}> 이미지를 불러오지 못했어요 😥")

#앱 실행
if __name__ == "__main__":
    SocketModeHandler(app, app_token).start()
