"""Bulk interview slots banao — ek command mein 10, 20, jitne chahiye.

Chalao:
  python -m scripts.add_slots                                    # 10 slots, kal se
  python -m scripts.add_slots --count 20                         # 20 slots
  python -m scripts.add_slots --email boss@gmail.com --count 15
  python -m scripts.add_slots --days 7 --per-day 4               # 7 din x 4 slots
  python -m scripts.add_slots --list                             # sirf dekho, banao mat
  python -m scripts.add_slots --clear                            # purane khali slots hatao

Slot ka waqt UTC mein hota hai. 10:00 UTC = Pakistan 3:00 PM.
"""
import argparse
from datetime import datetime, timedelta

from app.database import db_session, init_db
from app.models import InterviewSlot

# Roz ke kaun se waqt (UTC). PKT = UTC + 5
DEFAULT_HOURS = [5, 7, 9, 11]     # PKT: 10am, 12pm, 2pm, 4pm
DURATION_MIN = 45


def list_slots():
    db = db_session()
    try:
        free = db.query(InterviewSlot).filter(
            InterviewSlot.is_booked == False).order_by(InterviewSlot.start_at).all()  # noqa: E712
        booked = db.query(InterviewSlot).filter(InterviewSlot.is_booked == True).count()  # noqa: E712
        usable = [s for s in free if s.start_at > datetime.utcnow() + timedelta(hours=12)]

        print(f"\n  Khali slots      : {len(free)}")
        print(f"  Isme se usable   : {len(usable)}   (12 ghante se aage wale)")
        print(f"  Book ho chuke    : {booked}\n")
        for s in usable[:20]:
            pkt = s.start_at + timedelta(hours=5)
            print(f"   {s.start_at:%d %b %H:%M} UTC  ({pkt:%I:%M %p} PKT)  {s.interviewer_email}")
        if len(usable) > 20:
            print(f"   ... aur {len(usable)-20}")
        if not usable:
            print("   >> Koi usable slot nahi. Naye banayein.")
        print()
    finally:
        db.close()


def clear_slots():
    db = db_session()
    try:
        n = db.query(InterviewSlot).filter(InterviewSlot.is_booked == False).delete()  # noqa: E712
        db.commit()
        print(f"{n} khali slots hata diye (booked wale mehfooz hain)")
    finally:
        db.close()


def add_slots(email: str, count: int, days: int, per_day: int, start_after_days: int):
    db = db_session()
    created = 0
    try:
        base = (datetime.utcnow() + timedelta(days=start_after_days)).replace(
            minute=0, second=0, microsecond=0)
        hours = DEFAULT_HOURS[:per_day] if per_day <= len(DEFAULT_HOURS) else (
            DEFAULT_HOURS + list(range(12, 12 + per_day - len(DEFAULT_HOURS))))

        for d in range(days):
            for h in hours:
                if created >= count:
                    break
                start = base.replace(hour=h) + timedelta(days=d)
                if start < datetime.utcnow() + timedelta(hours=13):
                    continue          # 12-ghante rule se bachne ke liye
                exists = db.query(InterviewSlot).filter(
                    InterviewSlot.interviewer_email == email,
                    InterviewSlot.start_at == start).first()
                if exists:
                    continue
                db.add(InterviewSlot(interviewer_email=email, start_at=start,
                                     end_at=start + timedelta(minutes=DURATION_MIN)))
                created += 1
        db.commit()
        print(f"{created} naye slots ban gaye ({email})")
    finally:
        db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--email", default="mghous373@gmail.com", help="interviewer ka email")
    p.add_argument("--count", type=int, default=10, help="kitne slots banane hain")
    p.add_argument("--days", type=int, default=5, help="kitne din phailane hain")
    p.add_argument("--per-day", type=int, default=4, help="roz kitne slots")
    p.add_argument("--start-after", type=int, default=1, help="aaj se kitne din baad shuru")
    p.add_argument("--list", action="store_true", help="sirf maujooda slots dikhao")
    p.add_argument("--clear", action="store_true", help="khali slots hatao")
    a = p.parse_args()

    init_db()
    if a.clear:
        clear_slots()
    if a.list:
        list_slots()
    if not a.list and not a.clear:
        add_slots(a.email, a.count, a.days, a.per_day, a.start_after)
        list_slots()
