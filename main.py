import os
import requests
import base64
import dotenv
import time
from PIL import Image
from io import BytesIO
from subprocess import call
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI

#환경변수 불러오기
dotenv.load_dotenv()

#API 키 세팅
slack_app_token = os.environ.get("SLACK_APP_TOKEN")
slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
open_api_key = os.environ.get("OPENAI_API_KEY")
assistant_id = os.environ.get("OPENAI_ASSISTANT_ID")

assert open_api_key and slack_app_token and slack_bot_token and assistant_id, "필요한 환경변수를 설정해주세요."

#OpenAI 및 Slack 앱 초기화
app = App(token=slack_bot_token)
client = OpenAI(api_key=open_api_key)

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
                # 이미지 파일 처리
                image = Image.open(BytesIO(response.content))

                # 이미지 포맷 확인 및 변환
                if image.format not in ['JPEG', 'PNG', 'GIF', 'WEBP']:
                    logger.info(f"지원되지 않는 형식({image.format})을 JPEG로 변환합니다.")
                    # JPEG로 변환
                    with BytesIO() as output:
                        image.convert('RGB').save(output, format="JPEG")
                        image_bytes = output.getvalue()
                else:
                    image_bytes = response.content  # 이미 지원되는 형식이면 그대로 사용

                # base64 인코딩
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                logger.info("이미지 base64 인코딩 완료")

                gpt_response = client.chat.completions.create(
                    model="gpt-4-turbo",  # 최신 Vision 모델
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
    SocketModeHandler(app, slack_app_token).start()
