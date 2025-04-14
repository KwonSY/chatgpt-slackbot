import os
import requests
import base64
from PIL import Image, UnidentifiedImageError
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

            if response.status_code != 200:
                logger.error(f"이미지 다운로드 실패: {response.status_code}")
                say(f"<@{user}> 이미지를 불러오지 못했어요 😥")
                return

            try:
                image_bytes = response.content
                image_format = None
                image = None

                try:
                    # 일반 이미지 열기 시도
                    image = Image.open(BytesIO(image_bytes))
                    image_format = image.format
                except UnidentifiedImageError:
                    try:
                        # HEIC라면 변환 시도
                        heif_file = pyheif.read_heif(image_bytes)
                        image = Image.frombytes(
                            heif_file.mode, 
                            heif_file.size, 
                            heif_file.data,
                            "raw"
                        )
                        image_format = "HEIC"
                        logger.info("HEIC 이미지를 JPEG로 변환할 준비 완료")
                    except Exception as e:
                        logger.error(f"이미지 열기 실패: {e}")
                        say(f"<@{user}> 이미지 형식을 인식하지 못했어요. PNG, JPEG, GIF, WEBP 형식을 사용해 주세요.")
                        return

                with BytesIO() as output:
                    image.convert("RGB").save(output, format="JPEG")
                    jpeg_bytes = output.getvalue()
                    image_base64 = base64.b64encode(jpeg_bytes).decode("utf-8")

                gpt_response = client.chat.completions.create(
                    model="gpt-4-turbo",
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

            except Exception as e:
                logger.exception("예외 발생")
                say(f"<@{user}> 오류가 발생했어요: {str(e)}")

#앱 실행
if __name__ == "__main__":
    SocketModeHandler(app, slack_app_token).start()
