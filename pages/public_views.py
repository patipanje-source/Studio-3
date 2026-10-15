"""
PUBLIC SIDE OF THE SITE (visible without login) + result entry for admin/judge.

  /                 home_page_view   REQ 6  medal table = opening page
  /events/          events_page      REQ 2  event schedule (search + CSV download)
  /athletes/        athletes_page           athlete directory (search + CSV download)
  /results/         results_page     REQ 4  list of events -> result pages
  /results/<no>/    result_detail    REQ 4/5 ranking + (admin/judge) score entry, auto-calc, manual edit
"""
import csv
import math
from decimal import Decimal, InvalidOperation, ROUND_FLOOR

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .models import Athlete, Attempt, Event, ParticipatingAthlete, Result
from .permissions import can_edit_results, get_role, is_admin
from .scoring import calculate_event


# ----------------------------------------------------------------- helpers
def _csv_response(filename, header, rows):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


def medal_table():
    """Medals per country. Sorted gold > silver > bronze (Olympic order), total points shown too."""
    rows = (
        Result.objects.filter(medal__in=(1, 2, 3))
        .values('athlete__country')
        .annotate(
            gold=Count('id', filter=Q(medal=1)),
            silver=Count('id', filter=Q(medal=2)),
            bronze=Count('id', filter=Q(medal=3)),
            points=Sum('point'),
        )
        .order_by('-gold', '-silver', '-bronze', '-points', 'athlete__country')
    )
    table = []
    for position, r in enumerate(rows, start=1):
        table.append({
            'position': position,
            'country': r['athlete__country'],
            'gold': r['gold'], 'silver': r['silver'], 'bronze': r['bronze'],
            'total': r['gold'] + r['silver'] + r['bronze'],
            'points': r['points'] or 0,
        })
    return table


# ----------------------------------------------------------------- REQ 6  home
def home_page_view(req):
    table = medal_table()
    totals = {
        'gold': sum(r['gold'] for r in table),
        'silver': sum(r['silver'] for r in table),
        'bronze': sum(r['bronze'] for r in table),
    }
    totals['total'] = totals['gold'] + totals['silver'] + totals['bronze']
    latest = (Result.objects.filter(medal__in=(1, 2, 3)).select_related('event', 'athlete')
              .order_by('-event__date_time', 'event__number', 'rank')[:9])
    return render(req, 'home.html', {'table': table, 'totals': totals, 'latest': latest, 'active': 'home'})


# ----------------------------------------------------------------- REQ 2  events
def events_page(req):
    q = req.GET.get('q', '').strip()
    gender = req.GET.get('gender', '')
    events = Event.objects.select_related('sport', 'judge').order_by('date_time')
    if q:
        events = events.filter(Q(name__icontains=q) | Q(number__icontains=q) | Q(classification__icontains=q)
                               | Q(sport__sport_type__icontains=q) | Q(stage__icontains=q))
    if gender in ('M', 'F'):
        events = events.filter(gender=gender)

    if req.GET.get('download') == 'csv':
        return _csv_response('events.csv',
            ['number', 'name', 'sport', 'classification', 'gender', 'date_time', 'stage', 'status'],
            [[e.number, e.name, e.sport.sport_type, e.classification, e.gender, e.date_time, e.stage, e.status]
             for e in events])
    return render(req, 'events.html', {'events': events, 'q': q, 'gender': gender, 'active': 'events'})


# ----------------------------------------------------------------- athletes
def athletes_page(req):
    q = req.GET.get('q', '').strip()
    country = req.GET.get('country', '')
    athletes = Athlete.objects.all().order_by('country', 'bib')
    if q:
        athletes = athletes.filter(Q(firstName__icontains=q) | Q(lastName__icontains=q) | Q(bib__icontains=q)
                                   | Q(classification__icontains=q))
    if country:
        athletes = athletes.filter(country=country)
    countries = Athlete.objects.order_by('country').values_list('country', flat=True).distinct()

    if req.GET.get('download') == 'csv':
        return _csv_response('athletes.csv',
            ['country', 'id', 'firstName', 'lastName', 'gender', 'dateOfBirth', 'classification'],
            [[a.country, a.bib, a.firstName, a.lastName, a.gender, a.dateOfBirth, a.classification] for a in athletes])
    return render(req, 'athletes.html', {
        'athletes': athletes, 'q': q, 'country': country, 'countries': countries,
        'show_email': is_admin(req.user), 'active': 'athletes',
    })


def display_athlete(request, athlete_id=None, athlete_name=None):
    """Kept from the original project (/athlete/id/<bib>/ and /athlete/name/<name>/)."""
    athlete = None
    if athlete_id is not None:
        athlete = Athlete.objects.filter(bib=athlete_id).first()
    elif athlete_name is not None:
        athlete = Athlete.objects.filter(
            Q(firstName__icontains=athlete_name) | Q(lastName__icontains=athlete_name)).first()
    if not athlete:
        return HttpResponse("Athlete not found in the database.")
    results = athlete.results.select_related('event').order_by('event__date_time')
    return render(request, 'athlete_detail.html', {'athlete': athlete, 'results': results, 'active': 'athletes'})


# ----------------------------------------------------------------- REQ 4  results
def results_page(req):
    q = req.GET.get('q', '').strip()
    events = Event.objects.select_related('sport', 'judge').annotate(
        n_athletes=Count('participations', distinct=True),
        n_results=Count('results', filter=Q(results__rank__gt=0), distinct=True),
    ).order_by('-date_time')
    if q:
        events = events.filter(Q(name__icontains=q) | Q(number__icontains=q))
    return render(req, 'results.html', {'events': events, 'q': q, 'active': 'results'})


def _fmt(score):
    return f"{score / 100:.2f}" if score is not None else ""


def _unit(event):
    fmt = (event.score_format or '').lower()
    return {'distance': 'm', 'time': 's'}.get(fmt, '')


def _attempt_slots(event):
    fmt = (event.score_format or '').lower()
    return 6 if fmt == 'distance' else 1 if fmt == 'time' else 0


def result_detail(req, number):
    event = get_object_or_404(Event.objects.select_related('sport', 'judge'), number=number)
    editable = can_edit_results(req.user, event)

    if req.method == 'POST':
        if not editable:
            return HttpResponseForbidden("Only an administrator or the judge of this event can edit results.")
        error = _handle_post(req, event)
        if error: messages.error(req, error)
        return redirect('result_detail', number=event.number)

    existing = {r.athlete_id: r for r in Result.objects.filter(event=event).prefetch_related('attempts')}
    participants = (ParticipatingAthlete.objects.filter(event=event).select_related('athlete')
                    .order_by('athlete__bib'))
    slots = _attempt_slots(event)
    rows = []
    for p in participants:
        res = existing.get(p.athlete_id)
        saved = {a.attempt_number: a for a in res.attempts.all()} if res else {}
        rows.append({
            'athlete': p.athlete,
            'result': res,
            'attempts': [{
                'n': n,
                'status': saved[n].status if n in saved else 'unset',
                'value': _fmt(saved[n].score) if n in saved and saved[n].score else '',
            } for n in range(1, slots + 1)],
            'best': _fmt(res.best_score) if res and res.best_score else '',
        })
    # ranked first (rank 0 = not ranked yet goes last)
    rows.sort(key=lambda r: (r['result'].rank == 0 if r['result'] else True,
                             r['result'].rank if r['result'] else 0, r['athlete'].bib))
    return render(req, 'result_detail.html', {
        'event': event, 'rows': rows, 'editable': editable, 'unit': _unit(event),
        'slots': slots, 'role': get_role(req.user), 'active': 'results',
    })


def _handle_post(req, event):
    """mode=calculate : save attempts, then points/rank/medal are computed automatically (REQ 5)
       mode=manual    : save point/rank/medal exactly as typed                              (REQ 5)"""
    mode = req.POST.get('mode')
    participants = list(ParticipatingAthlete.objects.filter(event=event).select_related('athlete'))
    if not participants:
        return "Add participating athletes to this event first (Management -> Events -> people icon)."

    if mode == 'manual':
        try:
            with transaction.atomic():
                for p in participants:
                    a = p.athlete
                    point = int(req.POST.get(f'point-{a.id}') or 0)
                    rank = int(req.POST.get(f'rank-{a.id}') or 0)
                    medal = int(req.POST.get(f'medal-{a.id}') or 0)
                    if medal not in (0, 1, 2, 3) or rank < 0 or point < 0:
                        raise ValueError
                    res, _ = Result.objects.get_or_create(
                        event=event, athlete=a, defaults={'point': 0, 'rank': 0, 'medal': 0})
                    res.point, res.rank, res.medal = point, rank, medal
                    res.save()
        except ValueError:
            return "Points and rank must be whole numbers >= 0 and medal must be 0-3."
        messages.success(req, "Manual points / ranks / medals saved.")
        return None

    if mode == 'calculate':
        slots = _attempt_slots(event)
        if slots == 0:
            return "This event's score format is not distance or time, so points must be entered manually."
        try:
            with transaction.atomic():
                for p in participants:
                    a = p.athlete
                    res, _ = Result.objects.get_or_create(
                        event=event, athlete=a, defaults={'point': 0, 'rank': 0, 'medal': 0})
                    for n in range(1, slots + 1):
                        status = req.POST.get(f'status-{a.id}-{n}', 'unset')
                        raw = (req.POST.get(f'value-{a.id}-{n}') or '').strip()
                        if status == 'unset' and raw:
                            status = 'score'
                        if status not in ('score', 'foul', 'pass', 'unset'):
                            raise ValueError("An attempt has an unsupported status.")
                        score = None
                        if status == 'score':
                            try:
                                mark = Decimal(raw)
                            except (InvalidOperation, ValueError):
                                raise ValueError(f"Enter a value for every attempt marked Score ({a.firstName} {a.lastName}, attempt {n}).")
                            if not mark.is_finite() or mark <= 0:
                                raise ValueError("Marks must be greater than zero.")
                            score = int((mark * 100).to_integral_value(rounding=ROUND_FLOOR))
                        elif raw:
                            raise ValueError("Only attempts marked Score can have a value. Clear it for foul / pass / unset.")
                        Attempt.objects.update_or_create(
                            result=res, attempt_number=n, defaults={'status': status, 'score': score})
        except ValueError as exc:
            return str(exc)
        ok, msg = calculate_event(event)
        if not ok:
            return msg
        messages.success(req, msg)
        return None

    return "Unknown action."
