import os
import time
import re
import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from openai import OpenAI
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

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

def parse_changed_shift(text: str):
    try:
        lines = text.strip().split('\n')
        
        for i, line in enumerate(lines):
            if line.strip() == "변경근무" and i + 1 < len(lines):
                schedule_line = lines[i + 1].strip()
                
                match = re.search(
                    r"(\d{1,2})/(\d{1,2})(?:\(.*\))?\s+(\d{1,2}):(\d{2})\s*~\s*(\d{1,2}):(\d{2})\s+(.+)",
                    schedule_line
                )
                if not match:
                    print("정규식 매칭 실패:", schedule_line)
                    return None
                
                month, day, sh, sm, eh, em, name = match.groups()
                year = datetime.datetime.now().year
                start_time = datetime.datetime(year, int(month), int(day), int(sh), int(sm))

                # 24:00은 다음 날 00:00으로 처리
                if int(eh) == 24:
                    end_time = datetime.datetime(year, int(month), int(day), 0, int(em)) + datetime.timedelta(days=1)
                else:
                    end_time = datetime.datetime(year, int(month), int(day), int(eh), int(em))

                if end_time <= start_time:
                    end_time += datetime.timedelta(days=1)

                logger.warning(end_time)

                return {
                    "summary": name.strip(),
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                }
        return None
    except Exception as e:
        print("Parsing Error:", e)
        return None

# 메시지 핸들러
@app.message(".*")
def handle_message(message, say, logger):
    user_id = message['user']
    text = message['text']
    #logger.warning(f"User ({user_id}) said: {text}")

    # 유저 스레드 초기화
    if text.strip().lower() == "/reset":
        thread = client.beta.threads.create()
        user_threads[user_id] = thread.id
        save_threads()
        say(f"<@{user_id}> 대화가 초기화되었어요! 새로 시작해볼까요?")
        return

    # 테스트
    if text.strip().lower() == "테스트":
        say(f"<@{user_id}> 테스트되었습니다😆")
        return

    # 구글 캘린더
    if "변경근무" in text:
        parsed = parse_changed_shift(text)
        logger.warning("변경근무파서")
        logger.warning(parsed)
        
        if not parsed:
            say(f"<@{user_id}> 😥 변경근무 형식을 읽을 수 없어요.")
            return
        
        try:
            GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS_JSON")
            credentials_info = json.loads(GOOGLE_CREDENTIALS)
            credentials = Credentials.from_service_account_info(
                credentials_info, scopes=["https://www.googleapis.com/auth/calendar"]
            )
            service = build('calendar', 'v3', credentials=credentials)

            event = {
                'summary': parsed['summary'],
                'start': {
                    'dateTime': parsed['start'],
                    'timeZone': 'Asia/Seoul',
                },
                'end': {
                    'dateTime': parsed['end'],
                    'timeZone': 'Asia/Seoul',
                },
            }

            event_result = service.events().insert(calendarId='primary', body=event).execute()
            say(f"<@{user_id}> ✅ `{parsed['summary']}` 일정이 등록되었어요!\n📅 {event_result.get('htmlLink')}")
        except Exception as e:
            logger.error("캘린더 등록 오류: " + str(e))
            say(f"<@{user_id}> 😥 캘린더 일정 등록에 실패했어요. 다시 시도해 주세요.")
        return
        
    else:
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
                content=text
            )
    
            # 어시스턴트 실행
            run = client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id
            )
            logger.warning(run)
            
            # 최대 30초 기다리기 (3초 간격, 총 10번)
            for _ in range(10):
                run_status = client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id
                )
                logger.warning(f"Run status: {run_status.status}")
    
                if run_status.status == "completed":
                    break
                elif run_status.status == "failed":
                    error = run_status.last_error
                    logger.error(f"Run failed! Error: {error}")
                    if error.code == "rate_limit_exceeded":
                        say(f"<@{user_id}> ⚠️ 현재 사용량 제한(쿼터)을 초과했어요. 조금 뒤에 다시 시도해 주세요!")
                    else:
                        say(f"<@{user_id}> GPT 응답 실패 😥: {error.message}")
                    return
                time.sleep(3)
            else:
                say(f"<@{user_id}> GPT 응답 시간이 너무 오래 걸려서 중단했어요 😥")
                return
    
            # 응답 메시지 가져오기
            messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc")
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
