# סוכן מעקב חיפוש עבודה

**רחל וזהבית**

סוכן AI שעוזר לסטודנטית שמחפשת עבודה ראשונה בהייטק. הוא מחפש משרות אמיתיות באינטרנט, זוכר את ההעדפות שלה ואת המועמדויות שהגישה, ומזכיר לה מתי לחזור לחברות. הוא מדבר בעברית.

את אותו סוכן בנינו פעמיים, כדי להשוות בין שתי דרכים לבנות סוכן:

| | `API/` | `SDK/` |
|---|---|---|
| **על מה זה בנוי** | Messages API של Anthropic, בלי שום עזרה | Claude Agent SDK, כלומר Claude Code |
| **מה כתבנו** | את כל ה-harness: לולאה, היסטוריה, זיכרון, קונטקסט, compaction, caching, מדידת טוקנים | רק הגדרות. Claude Code מריץ את ה-harness |
| **הרשאה** | מפתח מ-Claude Console | ההתחברות ל-Claude Code (מנוי) |

ההשוואה המלאה נמצאת ב-[REPORT.md](REPORT.md).

## מה הסוכן יודע לעשות

| כלי | מה הוא עושה |
|---|---|
| `search_jobs` | מחפש משרות מרחוק ב-API החינמי של [Remotive](https://remotive.com). **זה הכלי החיצוני.** הוא מסנן את התוצאות לפי ההעדפות השמורות, למשל רמת ניסיון ותפקידים שלא רוצים |
| `save_application` | שומר מועמדות חדשה או מעדכן סטטוס (הוגש, ראיון, הצעה, דחייה). לא יוצר כפילויות |
| `list_applications` | מציג מועמדויות, עם סינון לפי סטטוס או חברה |
| `save_preference` | שומר העדפות חיפוש. העדפה חדשה **מחליפה** את הישנה, ולא נשמרת לידה |
| `follow_up` | מוסיף תזכורות למעקב, מציג אותן וסוגר אותן |

**דוגמה לשיחה:**
> **משתמשת:** הגשתי מועמדות ל-Wix לתפקיד Junior Backend Developer.
> **סוכן:** שמרתי: Wix, תפקיד Junior Backend Developer, סטטוס: הוגש. להזכיר לך לעשות follow-up בעוד שבוע?

## דרישות התרגיל, ואיך מימשנו אותן

- **זיכרון בין סשנים:** ההעדפות, המועמדויות והתזכורות נשמרות כקובצי JSON (`shared/store.py`).
  - ב-API, תמונת מצב קצרה של הזיכרון נכנסת להודעת המשתמש.
  - ב-SDK, אותו תוכן נכתב ל-`CLAUDE.md`, ו-Claude Code טוען אותו בתחילת כל סשן.
- **Context engineering:** הסוכן לא מקבל הכל בכל תור.
  - הזיכרון נכנס רק כשהוא השתנה מאז הפעם האחרונה שהמודל ראה אותו.
  - פרטים נוספים, כמו הערות, תאריכים ותזכורות, המודל שולף בכלים רק כשהוא צריך אותם.
- **חיסכון בטוקנים:**
  - כל כלי מחזיר כמה שורות קצרות של טקסט, לא JSON מלא.
  - כל תור נמדד: טוקנים, cache, מספר קריאות למודל, עלות וזמן.
- **שגיאות כלים:** קלט לא תקין או תקלה ב-API החיצוני חוזרים למודל כ-`is_error`, כדי שיתקן את עצמו.

## מבנה הפרויקט

```
shared/            קוד הדומיין, משותף לשתי הגרסאות
  tools.py           5 הכלים: סכמות JSON ומימוש
  store.py           שמירת המצב (העדפות, מועמדויות, תזכורות)
  jobs_api.py        הפנייה ל-Remotive
  prompts.py         ה-system prompt
  scenario.py        הרצת בדיקות, ספירת שורות, כתיבת תוצאות
API/
  main.py  agent.py
  harness/           קובץ אחד לכל אחריות:
    loop.py            הלולאה: ממשיכה כל עוד stop_reason == "tool_use"
    tools.py           dispatch של הכלים, וכל ה-tool_result חוזרים בהודעה אחת
    history.py         היסטוריה append-only בדיסק (JSONL)
    memory.py          קריאת הזיכרון
    context.py         מה נכנס לכל תור
    compaction.py      סיכום השיחה כשהיא עוברת סף של טוקנים
    caching.py         נקודות cache_control
    tokens.py          שימוש ועלות לכל קריאה
SDK/
  main.py  agent.py  tools.py   כל שורה שמחליפה קובץ harness מסומנת "# replaces: <שם>"
tests/             בדיקות offline עם client מדומה, בלי מפתח ובלי אינטרנט
scenario.json      התרחיש: 8 פניות בשני סשנים, ו-7 בדיקות pass/fail
results/           api.json, sdk.json
REPORT.md          ההשוואה בין שתי הגרסאות
```

## התקנה

צריך Python 3.13 ו-Windows (בלינוקס או במק, `.venv/bin/` במקום `.venv\Scripts\`).

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

גרסאות הספריות נעולות ב-`requirements.txt`. רשימת כל התלויות נמצאת ב-`requirements.lock.txt`.

## הרצה

**בדיקות offline** (לא צריך מפתח או אינטרנט):
```powershell
.venv\Scripts\python -m pytest tests
```

**גרסת ה-SDK** (רצה על ההתחברות ל-Claude Code; `ANTHROPIC_API_KEY` לא צריך להיות מוגדר):
```powershell
.venv\Scripts\python SDK\main.py --scenario scenario.json --out results\sdk.json
```

**גרסת ה-API** (צריך מפתח מ-Claude Console. מגדירים אותו רק בטרמינל, לעולם לא בקוד או ב-git):
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
.venv\Scripts\python API\main.py --scenario scenario.json --out results\api.json
Remove-Item Env:ANTHROPIC_API_KEY
```

כל ריצה מתחילה ממצב נקי: היא מוחקת את `API/state/` או `SDK/state/`. בסוף הריצה מודפסות תוצאות הבדיקות, והקובץ נשמר ב-`results/`.

## התרחיש

**סשן 1:**
- שמירת העדפות: Backend, Full-stack, Frontend או Data/AI, רק ג'וניור, עבודה מרחוק, בלי QA.
- חיפוש משרות Python.
- שמירת שתי מועמדויות: Wix ו-Monday.
- תזכורת למעקב מול Wix.

**סשן 2** רץ על מופע חדש של הסוכן, שטוען את המצב מהדיסק:
- שאלה מה נשמר. זו השליפה מהזיכרון.
- עדכון: זימון לראיון ב-Wix.
- **בקשה שסותרת את מה שנשמר:** "גם mid-level, לא רק ג'וניור". אחריה חיפוש משרות React.
- שאלה על התזכורות.

**הבדיקות:** 5 מתוך 7 בודקות את המצב שנשמר בדיסק, לא את טקסט התשובה. למשל:
- רמת הניסיון הוחלפה ל-junior + mid.
- ל-Wix יש מועמדות אחת בדיוק, בסטטוס ראיון.
- יש תזכורת פתוחה ל-Wix.

## הגדרות ההשוואה

- **מודל:** `claude-opus-5-5` עם effort `medium` בשתי הגרסאות.
- **system prompt וכלים:** זהים בשתי הגרסאות.
- **הגדרות ה-SDK:**
  - `tools=[]`: אין אף כלי מובנה של Claude Code.
  - `strict_mcp_config=True`.
  - `permission_mode="dontAsk"`.
  - `setting_sources=["project"]`.
- **נתוני המשרות:** תשובות Remotive נשמרות בדיסק לשעה, כדי ששתי הגרסאות יראו את אותן משרות.
