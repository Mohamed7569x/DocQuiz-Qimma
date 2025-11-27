from fastapi import APIRouter, Depends, HTTPException, status,Request, WebSocket, WebSocketDisconnect
import os, json, uuid, hashlib, textwrap, time
from app.dependencies import get_current_active_user, db_debends, get_current_subuser
from pydantic import BaseModel, Field
from typing import List, Optional,Dict, Literal
from datetime import datetime
from bs4 import BeautifulSoup, NavigableString, Tag
from dotenv import load_dotenv
from urllib.parse import urljoin
from app.schemas import models
from google import genai
from uuid import UUID, uuid4
from urllib.parse import urlparse
import urllib.request
import requests

load_dotenv()

bad_request_error = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Bad request."
)

unauthorized_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Unauthorized.",
    headers={"WWW-Authenticate": "Bearer"},
)

forbidden_error = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Forbidden."
)

not_found_error = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Resource not found."
)

method_not_allowed_error = HTTPException(
    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
    detail="Method not allowed."
)

conflict_error = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Conflict."
)

unsupported_media_type_error = HTTPException(
    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    detail="Unsupported media type."
)

unprocessable_entity_error = HTTPException(
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    detail="Unprocessable entity."
)

too_many_requests_error = HTTPException(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Too many requests."
)

unexpected_error = HTTPException(
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    detail="Something unexpected happened!"
)

bad_gateway_error = HTTPException(
    status_code=status.HTTP_502_BAD_GATEWAY,
    detail="Bad gateway."
)

service_unavailable_error = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="Service unavailable."
)

gateway_timeout_error = HTTPException(
    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
    detail="Gateway timeout."
)

router = APIRouter(tags=['Core'])


MAX_SECTIONS_PER_ROUND = 3
MAX_BULLETS_PER_SECTION = 5
MAX_EXAMPLES_PER_SECTION = 2
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"


ALLOWED_SOCIAL_DOMAINS = {
    "facebook.com",
    "fb.com",
    "x.com",
    "twitter.com",
    "reddit.com",
    "linkedin.com"
}

def sanitize_social_url(url: str) -> str | None:
    if not url or not isinstance(url, str):
        return None

    url = url.strip()
    parsed = urlparse(url)
    if not parsed.netloc:
        parsed = urlparse("https://" + url)
        
    domain = parsed.netloc.lower().replace("www.", "")

    if domain in ALLOWED_SOCIAL_DOMAINS:
        return url

    return None 


def get_html(url: str) -> bytes:
    headers = {
        "User-Agent": USER_AGENT
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.content

def clean_text(s: str) -> str:
    return " ".join(s.replace("\u00a0"," ").split()).strip()

def text_of(el: Tag, sep="\n") -> str:
    for br in el.find_all("br"):
        br.replace_with("\n")
    return el.get_text(separator=sep, strip=True)

def bullets_from_paragraphs(paras: List[str], max_bullets=6) -> List[str]:
    out = []
    for p in paras:
        if not p:
            continue
        if len(p) > 220:
            p = textwrap.shorten(p, width=220, placeholder=" …")
        out.append(p)
        if len(out) >= max_bullets:
            break
    return out

def parse_sections(full_url: str, soup: BeautifulSoup) -> dict:
    main = soup.find('div', id='main') or soup
    h1 = main.find('h1')
    page_title = text_of(h1) if h1 else "page"
    h2s = []
    seen_h1 = False
    for node in main.find_all(['h1','h2'], recursive=True):
        if node.name == 'h1':
            seen_h1 = True
            continue
        if seen_h1 and node.name == 'h2':
            h2s.append(node)

    sections = []
    for h2 in h2s:
        section_title = text_of(h2)
        explanation_paras: List[str] = []
        examples: List[dict] = []

        sib = h2.next_sibling
        while sib:
            if isinstance(sib, NavigableString):
                sib = sib.next_sibling
                continue
            if isinstance(sib, Tag):
                if sib.name == 'h2':
                    break
                if sib.name == 'p' and not explanation_paras:
                    cur = sib
                    while cur and isinstance(cur, Tag) and cur.name == 'p':
                        explanation_paras.append(clean_text(text_of(cur)))
                        cur = cur.next_sibling
                        while isinstance(cur, NavigableString):
                            cur = cur.next_sibling
                    sib = cur
                    continue
                if sib.name == 'div' and 'w3-example' in (sib.get('class') or []):
                    code_div = sib.select_one('div.w3-code')
                    if code_div:
                        code = text_of(code_div)
                        if code:
                            examples.append({"code": code})
                for ex_div in sib.select('div.w3-example'):
                    code_div = ex_div.select_one('div.w3-code')
                    if code_div:
                        code = text_of(code_div)
                        if code:
                            examples.append({"code": code})
            sib = sib.next_sibling

        summary = bullets_from_paragraphs(explanation_paras, MAX_BULLETS_PER_SECTION)
        if not summary:
            summary = [f"ملخص: شرح مبسط لقسم «{section_title}»"]

        if not examples:
            examples = [{"code": 'print("Hello, World!")'}]

        sections.append({
            "title": section_title,
            "summary": summary,
            "examples": examples
        })

    if not sections:
        paras = []
        if h1:
            cur = h1.next_sibling
            while cur and len(paras) < 5:
                if isinstance(cur, NavigableString):
                    cur = cur.next_sibling
                    continue
                if isinstance(cur, Tag) and cur.name == 'p':
                    paras.append(clean_text(text_of(cur)))
                cur = cur.next_sibling
        sections.append({
            "title": page_title,
            "summary": bullets_from_paragraphs(paras, MAX_BULLETS_PER_SECTION) or [f"ملخص: {page_title}"],
            "examples": [{"code": 'print("Hello")'}]
        })

    return {"page_title": page_title, "sections": sections, "source_url": full_url}

def content_hash(page_obj: dict) -> str:
    blob = json.dumps(page_obj["sections"], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

def upsert_page(db: db_debends, url: str, page_obj: dict) -> models.Page:
    
    h = content_hash(page_obj)
    existing: Optional[models.Page] = db.query(models.Page).filter(models.Page.url == url).first()
    if existing and existing.content_hash == h:
        return existing

    if not existing:
        existing = models.Page(url=url, page_title=page_obj["page_title"], source_json=json.dumps(page_obj, ensure_ascii=False),
                        content_hash=h, scraped_at=datetime.utcnow())
        db.add(existing)
        db.flush()
    else:
        existing.page_title = page_obj["page_title"]
        existing.source_json = json.dumps(page_obj, ensure_ascii=False)
        existing.content_hash = h
        existing.scraped_at = datetime.utcnow()
        db.query(models.Section).filter(models.Section.page_id == existing.id).delete()

    for s in page_obj["sections"]:
        db.add(models.Section(
            page_id=existing.id,
            title=s["title"],
            summary_json=json.dumps(s["summary"], ensure_ascii=False),
            examples_json=json.dumps(s["examples"], ensure_ascii=False),
        ))
    db.commit()
    db.refresh(existing)
    return existing

# ------------------ Gemini client (lazy) ------------------

GEMINI_API_KEY = os.getenv('GEMINI_KEY')
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = (
    "أنت منشئ أسئلة برمجية بالعربية. مهمتك إنشاء بنك أسئلة من محتوى تعليمي يُرسَل لك على شكل JSON. "
    "أعد JSON فقط بدون أي نص خارجه. "
    
    "سيصلك JSON يحتوي على معلومات مثل: language, level, num_questions, "
    "وقائمة sections، وكل section فيها title, summary, examples. "
    "اعتبر الـ summary والـ examples مرجع لكتابة أسئلة جديدة، "
    "ولا تكرر نفس الجمل أو الأسئلة حرفيًا من الشرح. "
    
    "التزم باستخدام نفس أسماء الـ topics التي يرسلها لك المستخدم فقط، "
    "ولا تضف topics جديدة أو تعدّل أسمائها. اربط كل سؤال بالـ topic المناسب من هذه القائمة. "
    
    "لا تترجم المصطلحات البرمجية التقنية، واترك الكلمات مثل: array, list, index, loop, function, file, open, read, write, mode "
    "وأسماء الدوال والكود كما هي بالإنجليزية. "
    "لا تغيّر الكود إلا إذا كنت تعدّل الأرقام أو القيم لصناعة سؤال مختلف، مع الحفاظ على صحته برمجيًا. "
    
    "نوع الأسئلة يكون واحدًا من: "
    "1) اختيار من متعدد (MCQ) "
    "2) سؤال ناتج الكود (What is the output). "
    "يجب أن يحتوي كل سؤال على 4 اختيارات فقط وإجابة صحيحة واحدة. "
    
    "أنشئ الأسئلة بناءً على الفهم: "
    "– غطِّ المفاهيم المذكورة في الشرح (مثلاً: تعريف array، طريقة الوصول للعناصر، التعديل على العناصر...). "
    "– يمكنك المزج بين أكثر من مثال أو فكرة من الشرح لصناعة سؤال جديد. "
    "– لا تلتزم بنفس ترتيب أو صياغة الشرح. "
    
    "أضف explanation عربي مختصر وواضح لكل سؤال يشرح لماذا هذه هي الإجابة الصحيحة، "
    "مع الإشارة للكود أو المفهوم البرمجي بدون ترجمة حرفية للمصطلحات التقنية. "
    
    "تأكد أن المخرجات كلها بصيغة JSON صحيحة التركيب، "
    "وبدون أي نص إضافي خارج JSON."
    
    "أي سؤال يحتوي على كود يجب أن يكون الكود بداخله بين code fences "
    "بهذا الشكل:\n```python\n<code goes here>\n```. "
    "لا تسمح بوضع الكود كسطر واحد مفصول بفواصل منقوطة. "
    "الكود يجب أن يكون متعدد الأسطر مثل الكود الطبيعي. "
    "لا تضع أي كود خارج code fences. "
)



class QuizQuestion(BaseModel):
    id: str
    topic: str
    type: Literal["mcq", "output"]
    question: str
    options: List[str] | None = None
    correct_index: int
    explanation: str


class QuizResponse(BaseModel):
    questions: List[QuizQuestion]
    
    

def call_gemini_quiz(language: str, level: str, sections: List[dict], num_questions: int) -> dict:
    client = gemini_client
    user_payload = {
        "language": language,
        "level": level,
        "num_questions": num_questions,
        "sections": sections
    }
    rsp = client.models.generate_content(
        model='gemini-2.5-flash',
        config={
        "response_mime_type": "application/json",
        "response_json_schema": QuizResponse.model_json_schema(),
    },
        contents = (
    "[\n"
    f'    {{"role": "system", "content": {json.dumps(SYSTEM_PROMPT)}}},\n'
    f'    {{"role": "user", "content": {json.dumps(user_payload, ensure_ascii=False)}}}\n'
    "]"
))

    data = rsp.parsed
    qs = data.get("questions", [])[:num_questions]
    qs = [q for q in qs if isinstance(q, dict) and len(q.get("options", [])) == 4 and 0 <= q.get("correct_index", -1) <= 3]
    
    return {"questions": qs}

class GenerateReq(BaseModel):
    topics: List[str]
    language: Literal["python","javascript"]
    level: Literal["beginner","intermediate","advanced"]
    num_questions: int

class SubmitReq(BaseModel):
    questions: List[dict]
    answers: List[int]

@router.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}

@router.get("/topics")
def list_topics(db: db_debends):
    rows = db.query(models.Url).order_by(models.Url.lang).all()
    return [
        {"id": t.id, "lang": t.lang, "title": t.title}
        for t in rows
    ]


def _ensure_page(db, page_url: str):
    page = db.query(models.Page).filter(models.Page.url == page_url).first()
    if page:
        return page
    try:
        html = get_html(page_url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fetch failed for {page_url}: {e}")
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.select('#mainLeaderboard, .w3-clear.nextprev'):
        el.decompose()
    page_obj = parse_sections(page_url, soup)
    return upsert_page(db, page_url, page_obj)

class QuestionOut(BaseModel):
    id: UUID        
    topic: Optional[str]
    q_type: str
    question: str
    options: List[str]

    class Config:
        from_attributes = True
    
class QuizOut(BaseModel):
    id: UUID
    language: str
    level: Optional[str]
    questions: List[QuestionOut]

    class Config:
        from_attributes = True

@router.post("/generate-quiz", response_model=QuizOut)
def generate_quiz(body: GenerateReq, db: db_debends):
    q = (
        db.query(models.Url)
        .filter(models.Url.lang.ilike(f'%{body.language}%'))
        .filter(models.Url.title.in_(body.topics))
    )
    url_rows = q.all()

    
    found_titles = {u.title for u in url_rows}
    missing = [t for t in set(body.topics) if t not in found_titles]
    
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"error": "unknown-topics", "missing": missing}
        )

    pages = []
    for u in url_rows:
        page = _ensure_page(db, u.url)
        pages.append(page)

    section_rows = (
        db.query(models.Section)
        .filter(models.Section.page_id.in_([p.id for p in pages]))
        .all()
    )
    if not section_rows:
        raise HTTPException(status_code=400, detail="No sections were parsed for the selected topics.")

    selected = section_rows[:MAX_SECTIONS_PER_ROUND]
    compact_sections = []
    for s in selected:
        compact_sections.append({
            "title": s.title,
            "summary": (json.loads(s.summary_json) if s.summary_json else [])[:MAX_BULLETS_PER_SECTION],
            "examples": (json.loads(s.examples_json) if s.examples_json else [])[:MAX_EXAMPLES_PER_SECTION],
        })

    
    questions = call_gemini_quiz(body.language, body.level, compact_sections, body.num_questions)
    quiz = models.Quiz(
        language = body.language,
        level = body.level
    )
    db.add(quiz)
    db.flush()
    for q in questions.get('questions'):
        question = models.Question(
            quiz_id=quiz.id,
            topic=q.get("topic"),
            q_type=q.get("type"),
            question=q.get("question"),
            options=q.get("options", []),
            correct_index=q.get("correct_index", 0),
            explanation=q.get("explanation")
        )
        db.add(question)

    db.flush()
    
    return quiz


class PerTopic(BaseModel):
    topic: str
    correct: int
    total: int

class WrongQuestion(BaseModel):
    index: int
    question: dict       
    user_index: Optional[int]
    correct_index: int
    
class QuizResultIn(BaseModel):
    language: Optional[str] = None
    level: Optional[str] = None
    topics: List[str] = []

    score: int
    total: int
    per_topic: List[PerTopic]
    weak_topics: List[str] = []
    wrong_questions: List[WrongQuestion] = []

class AnswerIn(BaseModel):
    question_id: UUID
    user_index: Optional[int]


class GradeQuizIn(BaseModel):
    quiz_id: UUID
    answers: List[AnswerIn]
    username: str
    social: Optional[str] = None


class TopicStats(BaseModel):
    correct: int
    total: int


class WrongQuestionOut(BaseModel):
    question_id: UUID
    question: str
    options: List[str]
    explanation: str
    topic: str
    user_index: Optional[int]
    correct_index: int


class GradeQuizOut(BaseModel):
    share_id: UUID
    share_url: str
    quiz_id: UUID
    score: int
    total: int
    per_topic: Dict[str, TopicStats]
    wrong_questions: List[WrongQuestionOut]
     
@router.post("/grade-quiz", response_model=GradeQuizOut)
def grade_quiz(payload: GradeQuizIn, db: db_debends, request: Request):
    quiz: models.Quiz | None = (
        db.query(models.Quiz)
        .filter(models.Quiz.id == payload.quiz_id)
        .first()
    )
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    question_ids = [a.question_id for a in payload.answers]
    if not question_ids:
        raise HTTPException(status_code=400, detail="No answers provided")

    questions: List[models.Question] = (
        db.query(models.Question)
        .filter(models.Question.id.in_(question_ids))
        .all()
    )
    questions_map: Dict[UUID, models.Question] = {q.id: q for q in questions}

    score = 0
    total = 0

    per_topic_raw: Dict[str, Dict[str, int]] = {}
    wrong_questions: List[WrongQuestionOut] = []

    for ans in payload.answers:
        q = questions_map.get(ans.question_id)
        if not q:
            continue

        total += 1
        correct_idx = q.correct_index
        topic = q.topic or "غير محدد"
        ok = (ans.user_index == correct_idx)

        if ok:
            score += 1

        if topic not in per_topic_raw:
            per_topic_raw[topic] = {"correct": 0, "total": 0}

        per_topic_raw[topic]["total"] += 1
        if ok:
            per_topic_raw[topic]["correct"] += 1
        
        if not ok:
            wrong_questions.append(
                WrongQuestionOut(
                    question_id=q.id,
                    question=q.question,
                    options=q.options,
                    explanation=q.explanation,
                    topic=topic,
                    user_index=ans.user_index,
                    correct_index=correct_idx,
                )
            )

    if total == 0:
        raise HTTPException(status_code=400, detail="No valid answers for this quiz")

    per_topic_out: Dict[str, TopicStats] = {
        topic: TopicStats(correct=v["correct"], total=v["total"])
        for topic, v in per_topic_raw.items()
    }
    
    wrong_questions_raw = [
        {
            "question_id": str(w.question_id),
            "question": w.question,
            "options": w.options,
            "explanation": w.explanation,
            "topic": w.topic,
            "user_index": w.user_index,
            "correct_index": w.correct_index,
        }
        for w in wrong_questions
    ]
    socialmedia = sanitize_social_url(payload.social)
    result_obj = models.QuizResult(
        name=payload.username,
        social=socialmedia,
        language=quiz.language,
        level=quiz.level,
        score=score,
        total=total,
        per_topic=per_topic_raw,      
        wrong_questions=wrong_questions_raw
    )

    db.add(result_obj)
    db.flush()

    base_url = str(request.base_url).rstrip("/")
    share_url = f"{base_url}/share/{result_obj.id}"

    return GradeQuizOut(
        share_id=result_obj.id,
        share_url=share_url,
        quiz_id=quiz.id,
        score=score,
        total=total,
        per_topic=per_topic_out,        
        wrong_questions=wrong_questions
    )

    
@router.get("/api/shared/{share_id}")
def get_shared_result(share_id: str, db: db_debends):
  obj = db.query(models.QuizResult).filter_by(id=share_id).first()
  if not obj:
      raise HTTPException(status_code=404, detail="Result not found")

  return {
      "name": obj.name,
      "social": obj.social,
      "language": obj.language,
      "level": obj.level,
      "topics": obj.topics,
      "score": obj.score,
      "total": obj.total,
      "per_topic": obj.per_topic,
      "wrong_questions": obj.wrong_questions,
      "created_at": obj.created_at,
  }
