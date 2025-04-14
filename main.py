import os
import requests
import base64
from PIL import Image, UnidentifiedImageError
import pyheif
from io import BytesIO
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI

#API 키 세팅
slack_app_token = os.environ.get("SLACK_APP_TOKEN")
slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
open_api_key = os.environ.get("OPENAI_API_KEY")
assistant_id = os.environ.get("OPENAI_ASSISTANT_ID")

#OpenAI 및 Slack 앱 초기화
app = App(token=slack_bot_token)
client = OpenAI(api_key=open_api_key)

# 이미지 메시지 처리
@app.event("message")
def handle_image_message(event, say, logger):
    files = event.get("files", [])
    text = event.get("text", "")
    user = event.get("user", "")

    if not files:
        return  # 이미지가 없으면 무시

    supported_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"]
    
    for file_info in files:
        if file_info["mimetype"].startswith("image/"):
            file_name = file_info.get("name", "")
            image_url = file_info["url_private_download"]
            headers = {"Authorization": f"Bearer {slack_bot_token}"}
            response = requests.get(image_url, headers=headers)

            if response.status_code != 200:
                logger.error(f"이미지 다운로드 실패: {response.status_code}")
                say(f"<@{user}> 이미지를 불러오지 못했어요 😥")
                return

            try:
                image_bytes = response.content
                image = None

                # 이미지 MIME 타입 확인
                mime_type, _ = mimetypes.guess_type(file_name)
                logger.info(f"파일 MIME 타입: {mime_type}")

                # 1차 시도: PIL
                try:
                    image = Image.open(BytesIO(image_bytes))
                    logger.info("PIL로 이미지 열기 성공")
                except Exception as e1:
                    logger.warning(f"PIL 실패: {e1}")

                    # 2차 시도: JPEG로 강제 로딩
                    try:
                        image = Image.open(BytesIO(image_bytes))
                        image = image.convert("RGB")
                        logger.info("JPEG 강제 로딩 성공")
                    except Exception as e2:
                        logger.warning(f"JPEG 강제 시도 실패: {e2}")

                        # 3차 시도: HEIC 처리
                        try:
                            heif_file = pyheif.read_heif(image_bytes)
                            image = Image.frombytes(
                                heif_file.mode,
                                heif_file.size,
                                heif_file.data,
                                "raw"
                            )
                            logger.info("HEIC 이미지 처리 성공")
                        except Exception as e3:
                            logger.error(f"HEIC 처리 실패: {e3}")
                            say(f"<@{user}> 이미지를 열 수 없어요. PNG, JPEG, GIF, WEBP 형식을 사용해 주세요.")
                            return

                # JPEG로 변환 + base64 인코딩
                with BytesIO() as output:
                    image.convert("RGB").save(output, format="JPEG")
                    jpeg_bytes = output.getvalue()
                    image_base64 = base64.b64encode(jpeg_bytes).decode("utf-8")

                # GPT에 요청
                gpt_response = client.chat.completions.create(
                    model="gpt-4.5-preview",
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
