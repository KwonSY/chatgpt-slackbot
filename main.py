import os
import dotenv
import pip
from subprocess import call
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from openai import OpenAI
from config import OPENAI_API_KEY

#환경변수 불러오기
dotenv.load_dotenv()

#API 키 세팅
app_token = os.environ.get("SLACK_APP_TOKEN")
bot_token = os.environ.get("SLACK_BOT_TOKEN")
open_api_key = os.environ.get("OPENAI_API_KEY")
assistant_id = os.environ.get("OPENAI_ASSISTANT_ID")

assert open_api_key and app_token and bot_token and assistant_id, "필요한 환경변소룰 설정해주세요."

#OpenAI 및 Slack 앱 초기화
client = OpenAI(api_key=open_api_key)
app = App(token=bot_token)

with open('requirements.txt', encoding='utf-8-sig',mode='r') as file:
    for library_name in file.readlines():
        call("pip install " + library_name, shell=True)


# 메시지 핸들러
@app.message(".*")
def handle_message(message, say, logger):
    user_message = message['text']
    thread = client.beta.threads.create()
    
    # 사용자 메시지 추가
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_message
    )

    # Assistant 실행
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id
    )

    # 실행 완료 대기
        while True:
            run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status == "completed":
            break
        elif run_status.status == "failed":
            say("어시스턴트 실행 실패")
            return
        time.sleep(1)

    # 응답 가져오기
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    latest_message = messages.data[0].content[0].text.value
    say(latest_message)

    # 실행
if __name__ == "__main__":
    SocketModeHandler(app, app_token).start()
