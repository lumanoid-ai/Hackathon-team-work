"""Saare email templates ek jagah. Jinja2 syntax, plain HTML."""

BASE = """<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;
 max-width:560px;margin:0 auto;color:#111">
{{ body }}
<hr style="border:none;border-top:1px solid #eee;margin:24px 0">
<p style="color:#888;font-size:12px">{{ company }} · Yeh email hamare AI recruiting
assistant ne bheja hai. Reply karein to insaan hi parhega.</p></div>"""

TEMPLATES: dict[str, dict[str, str]] = {

    "application_received": {
        "subject": "Aapki application mil gayi — {{ job_title }}",
        "body": """<h2>Shukriya, {{ candidate_name }}!</h2>
<p><b>{{ job_title }}</b> ke liye aapki application <b>{{ company }}</b> ko mil chuki hai.</p>
<p>Hamari screening abhi chal rahi hai. Aapko <b>48 ghante</b> ke andar update mil jayega —
chahe khabar achi ho ya buri, hum khamosh nahi rehte.</p>
<p>Application ID: <code>{{ application_id }}</code></p>""",
    },

    "waiting": {
        "subject": "Update: aapki application review mein hai — {{ job_title }}",
        "body": """<h2>Salam {{ candidate_name }},</h2>
<p><b>{{ job_title }}</b> ke liye aapka profile hamari shortlist ke bilkul qareeb hai.
Filhal hum aapko <b>waiting list</b> pe rakh rahe hain.</p>
<p>{{ note }}</p>
<p>Agar shortlist mein jagah khali hui to hum sabse pehle aapko rabta karenge.</p>""",
    },

    "shortlisted": {
        "subject": "Achi khabar — aap shortlist ho gaye ({{ job_title }})",
        "body": """<h2>Mubarak ho {{ candidate_name }}!</h2>
<p>Aap <b>{{ job_title }}</b> ke liye shortlist ho gaye hain.</p>
<p>{{ note }}</p>
<p>Interview ka schedule alag email mein aa raha hai — calendar invite bhi sath hogi.</p>""",
    },

    "rejected": {
        "subject": "Update on your application — {{ job_title }}",
        "body": """<h2>Salam {{ candidate_name }},</h2>
<p>Aapke waqt ka shukriya. Is dafa hum <b>{{ job_title }}</b> ke liye aage nahi barh rahe.</p>
<p>{{ note }}</p>
<p>Aapka profile hamare talent pool mein mehfooz hai — matching role aane pe rabta karenge.</p>""",
    },

    "interview_invite": {
        "subject": "Interview scheduled — {{ job_title }} ({{ when }})",
        "body": """<h2>{{ candidate_name }}, aapka interview set ho gaya</h2>
<table style="font-size:15px">
<tr><td><b>Role</b></td><td>{{ job_title }}</td></tr>
<tr><td><b>Kab</b></td><td>{{ when }}</td></tr>
<tr><td><b>Kis se</b></td><td>{{ interviewer }}</td></tr>
<tr><td><b>Kahan</b></td><td>{{ meeting_link }}</td></tr>
</table>
<p>Calendar invite (.ics) attach hai — apne calendar mein add kar lein.</p>
<p>Reschedule chahiye? Is email ka reply kar dein.</p>""",
    },

    "interviewer_brief": {
        "subject": "You're interviewing {{ candidate_name }} — {{ when }}",
        "body": """<h2>Interview brief</h2>
<p><b>{{ candidate_name }}</b> ({{ candidate_email }}) — {{ job_title }}</p>
<p><i>{{ one_liner }}</i></p>
<h3>Screening questions</h3>
<ol>{% for q in questions %}<li><b>{{ q.question }}</b><br>
<small>Good answer: {{ q.good_answer_looks_like }}<br>
Red flag: {{ q.red_flag }}</small></li>{% endfor %}</ol>""",
    },

    "interview_reminder": {
        "subject": "Kal aapka interview hai — {{ job_title }}",
        "body": """<p>Salam {{ candidate_name }}, yaad dehani: <b>{{ when }}</b> ko
aapka <b>{{ job_title }}</b> interview hai.</p><p>Link: {{ meeting_link }}</p>""",
    },

    "offer": {
        "subject": "Offer — {{ job_title }} at {{ company }}",
        "body": """<h2>Mubarak ho {{ candidate_name }}! 🎉</h2>
<p>Hum aapko <b>{{ job_title }}</b> ka offer de rahe hain.</p>
<p><b>Start date:</b> {{ start_date }}</p>
<p>{{ note }}</p>
<p>Qubool karne ke liye is email ka reply <b>"I accept"</b> ke sath karein.
Onboarding checklist next email mein aayegi.</p>""",
    },

    "onboarding": {
        "subject": "Welcome aboard — aapka onboarding plan",
        "body": """<h2>Welcome, {{ candidate_name }}!</h2>
<p>{{ start_date }} se pehle, pehle din, pehle hafte aur pehle mahine ka plan neeche hai.</p>
{{ checklist_html }}""",
    },
}
