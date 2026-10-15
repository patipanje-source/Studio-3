"""Scoring helpers and staff page for the Para long-jump project calculator."""

from decimal import Decimal, InvalidOperation, ROUND_FLOOR
import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction

from .models import Attempt, Event, ParticipatingAthlete, PointTable, Result


# World Para Athletics 2025/2026 Raza field table, Long Jump rows.
# Formula: a * exp(-exp(b - c * performance_metres)); see version in template.
RAZA_LONG_JUMP = {
    "T61": {"a": 1200, "men_b": 5.541375, "men_c": 1.012864, "women_b": 5.796262, "women_c": 1.297211},
    "T62": {"a": 1200, "men_b": 5.541375, "men_c": 0.988727, "women_b": 5.796262, "women_c": 1.118046},
    "T63": {"a": 1200, "men_b": 5.541375, "men_c": 0.960706, "women_b": 5.796262, "women_c": 1.445337},
    "T64": {"a": 1200, "men_b": 5.541375, "men_c": 0.904433, "women_b": 5.796262, "women_c": 1.181861},
}

GENDER_ALIASES = {
    "m": "men", "male": "men", "man": "men", "men": "men",
    "f": "women", "female": "women", "woman": "women", "w": "women", "women": "women",
}


def _class_code(value):
    return (value or "").strip().upper()


def _gender_code(value):
    return GENDER_ALIASES.get((value or "").strip().lower())


def raza_long_jump_points(distance_cm, class_code, gender_code):
    """Return unrounded Raza points for ranking; distance is stored in centimetres."""
    params = RAZA_LONG_JUMP[class_code]
    distance_m = distance_cm / 100
    b = params[f"{gender_code}_b"]
    c = params[f"{gender_code}_c"]
    exponent = b - c * distance_m
    return params["a"] * math.exp(-math.exp(exponent))


def _event_page(request, event=None, error=None):
    events = Event.objects.filter(name__icontains="long jump").order_by("-date_time")
    rows = []
    if event:
        existing = {
            result.athlete_id: result
            for result in Result.objects.filter(event=event).prefetch_related("attempts")
        }
        participants = ParticipatingAthlete.objects.filter(event=event).select_related("athlete").order_by("athlete__bib")
        for participation in participants:
            athlete = participation.athlete
            result = existing.get(athlete.id)
            attempts = {a.attempt_number: a for a in result.attempts.all()} if result else {}
            rows.append({
                "athlete": athlete,
                "attempts": [
                    {
                        "number": n,
                        "status": request.POST.get(f"status-{athlete.id}-{n}", attempts[n].status if n in attempts else "unset"),
                        "distance": request.POST.get(
                            f"distance-{athlete.id}-{n}",
                            f"{attempts[n].score / 100:.2f}" if n in attempts and attempts[n].score is not None else "",
                        ),
                    }
                    for n in range(1, 7)
                ],
                "best_metres": f"{result.best_score / 100:.2f}" if result and result.best_score is not None else "",
                "point": result.point if result else "",
                "rank": result.rank if result and result.rank else "—",
                "medal": {1: "Gold", 2: "Silver", 3: "Bronze"}.get(result.medal, "—") if result else "—",
            })
    return render(request, "medal_calculator.html", {
        "events": events,
        "selected_event": event,
        "rows": rows,
        "error": error,
        "class_codes": sorted(RAZA_LONG_JUMP),
    })


@login_required
def medal_calculator(request):
    if not request.user.is_staff:
        return redirect("home")

    if request.method == "GET":
        event_id = request.GET.get("event")
        event = get_object_or_404(Event, id=event_id) if event_id else None
        if event and "long jump" not in event.name.lower():
            return _event_page(request, error="Choose a Long Jump event.")
        return _event_page(request, event=event)

    event = get_object_or_404(Event, id=request.POST.get("event_id"))
    if "long jump" not in event.name.lower():
        return _event_page(request, error="This calculator only supports Long Jump events.")

    participants = list(
        ParticipatingAthlete.objects.filter(event=event).select_related("athlete").order_by("athlete__bib")
    )
    if not participants:
        return _event_page(request, event=event, error="Add participating athletes to this event first.")
    if len(participants) > 8:
        return _event_page(request, event=event, error="This project version supports up to 8 athletes so everyone can take all 6 attempts.")

    parsed = []
    genders = set()
    for participation in participants:
        athlete = participation.athlete
        class_code = _class_code(athlete.classification)
        gender_code = _gender_code(athlete.gender)
        if class_code not in RAZA_LONG_JUMP:
            return _event_page(request, event=event, error=f"{athlete.firstName} {athlete.lastName} needs a verified T61, T62, T63, or T64 sport class.")
        if not gender_code:
            return _event_page(request, event=event, error=f"{athlete.firstName} {athlete.lastName} needs gender recorded as Male/Female (or M/F) to use the official table parameters.")
        genders.add(gender_code)

        attempts = []
        for number in range(1, 7):
            status = request.POST.get(f"status-{athlete.id}-{number}", "unset")
            raw = request.POST.get(f"distance-{athlete.id}-{number}", "").strip()
            if status not in {"score", "foul", "pass", "unset"}:
                return _event_page(request, event=event, error="An attempt has an unsupported status.")
            if status == "score":
                try:
                    mark = Decimal(raw)
                except (InvalidOperation, ValueError):
                    return _event_page(request, event=event, error="Enter a distance for every attempt marked Score.")
                if not mark.is_finite() or mark < 0:
                    return _event_page(request, event=event, error="Distances must be zero or greater.")
                centimetres = int((mark * 100).to_integral_value(rounding=ROUND_FLOOR))
            else:
                if raw:
                    return _event_page(request, event=event, error="Only Score attempts can have a distance. Clear the distance for fouls, passes, and unset attempts.")
                centimetres = None
            attempts.append({"number": number, "status": status, "score": centimetres})

        valid_marks = [a["score"] for a in attempts if a["status"] == "score"]
        best_cm = max(valid_marks) if valid_marks else None
        trial_points = sorted(
            (raza_long_jump_points(mark, class_code, gender_code) for mark in valid_marks),
            reverse=True,
        )
        parsed.append({
            "athlete": athlete,
            "class_code": class_code,
            "gender_code": gender_code,
            "attempts": attempts,
            "best_cm": best_cm,
            "best_points": trial_points[0] if trial_points else None,
            "trial_points": trial_points,
        })

    if len(genders) > 1:
        return _event_page(request, event=event, error="Keep each open event gender-separated; the official table has separate male and female parameters.")

    ranked = sorted(
        (row for row in parsed if row["best_cm"] is not None),
        key=lambda row: (-row["best_points"], tuple(-p for p in row["trial_points"][1:])),
    )
    previous_key = None
    current_rank = 0
    for position, row in enumerate(ranked, start=1):
        tie_key = (row["best_points"], tuple(row["trial_points"][1:]))
        if tie_key != previous_key:
            current_rank = position
            previous_key = tie_key
        row["rank"] = current_rank
        row["medal"] = current_rank if current_rank <= 3 else 0
    for row in parsed:
        if row["best_cm"] is None:
            row["rank"] = 0
            row["medal"] = 0

    with transaction.atomic():
        for row in parsed:
            result, _ = Result.objects.get_or_create(
                event=event,
                athlete=row["athlete"],
                defaults={"point": 0, "rank": 0, "medal": 0, "best_score": None},
            )
            result.best_score = row["best_cm"]
            result.point = int(math.floor(row["best_points"] + 0.5)) if row["best_points"] is not None else 0
            result.rank = row["rank"]
            result.medal = row["medal"]
            result.save()
            for trial in row["attempts"]:
                Attempt.objects.update_or_create(
                    result=result,
                    attempt_number=trial["number"],
                    defaults={"status": trial["status"], "score": trial["score"]},
                )

    messages.success(request, "Results, Raza points, ranks, and medals have been calculated and saved.")
    return redirect(f"/manage/medal-calculator/?event={event.id}")


# ---------------------------------------------------------------------------
# GENERIC CALCULATION (any event that has rows in PointTable)  -> requirement 5
# ---------------------------------------------------------------------------

def points_from_table(row, performance):
    """points = a * exp(-exp(b - c * performance)); performance in metres or seconds."""
    return row.a * math.exp(-math.exp(row.b - row.c * performance))


def find_point_row(event_name, class_code, gender_code):
    """Best PointTable row whose `event` fragment appears in the event name (longest fragment wins)."""
    name = (event_name or "").lower()
    candidates = [
        row for row in PointTable.objects.filter(classification=class_code, gender=gender_code)
        if row.event.lower() in name
    ]
    return max(candidates, key=lambda r: len(r.event), default=None)


def calculate_event(event):
    """
    Read the saved attempts of every participating athlete, convert each valid mark to points,
    rank by points (NOT by raw score), and store point / rank / medal on Result.

    Attempt.score is stored as an integer: centimetres (distance) or hundredths of a second (time).
    Returns (ok: bool, message: str).
    """
    participants = list(
        ParticipatingAthlete.objects.filter(event=event).select_related("athlete").order_by("athlete__bib")
    )
    if not participants:
        return False, "Add participating athletes to this event first."

    parsed, genders = [], set()
    for participation in participants:
        athlete = participation.athlete
        class_code = _class_code(athlete.classification)
        gender_code = _gender_code(athlete.gender)
        who = f"{athlete.firstName} {athlete.lastName}"
        if not class_code:
            return False, f"{who} has no classification."
        if not gender_code:
            return False, f"{who} needs gender recorded as M/F (or Men/Women)."
        row = find_point_row(event.name, class_code, gender_code)
        if row is None:
            return False, (f"No points-table row for '{event.name}' / {class_code} / {gender_code}. "
                           f"Add it under Point tables in Django admin, or enter points manually.")
        genders.add(gender_code)

        result = Result.objects.filter(event=event, athlete=athlete).prefetch_related("attempts").first()
        marks = []
        if result:
            marks = [a.score for a in result.attempts.all() if a.status == "score" and a.score and a.score > 0]
        scored = sorted(((points_from_table(row, m / 100), m) for m in marks), reverse=True)
        parsed.append({
            "athlete": athlete,
            "best_points": scored[0][0] if scored else None,
            "best_mark": scored[0][1] if scored else None,
            "rest": tuple(-round(p, 6) for p, _ in scored[1:]),
        })

    if len(genders) > 1:
        return False, "Keep each event gender-separated (the points table has separate men/women parameters)."

    ranked = sorted((r for r in parsed if r["best_points"] is not None),
                    key=lambda r: (-round(r["best_points"], 6), r["rest"]))
    previous, current = None, 0
    for position, r in enumerate(ranked, start=1):
        key = (round(r["best_points"], 6), r["rest"])
        if key != previous:
            current, previous = position, key
        r["rank"] = current
        r["medal"] = current if current <= 3 else 0
    for r in parsed:
        if r["best_points"] is None:
            r["rank"], r["medal"] = 0, 0

    with transaction.atomic():
        for r in parsed:
            result, _ = Result.objects.get_or_create(
                event=event, athlete=r["athlete"],
                defaults={"point": 0, "rank": 0, "medal": 0, "best_score": None},
            )
            result.best_score = r["best_mark"]
            result.point = int(math.floor(r["best_points"] + 0.5)) if r["best_points"] is not None else 0
            result.rank = r["rank"]
            result.medal = r["medal"]
            result.save()
    return True, f"Calculated points, ranks and medals for {len(ranked)} athlete(s)."
