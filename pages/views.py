from django.http import HttpResponse
from django.db.models import Q
from django.shortcuts import render, redirect

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Profile, Sport, Athlete, Event, ParticipatingAthlete, Result, Attempt
from django.http import JsonResponse
from django import forms
from mapbox_location_field.forms import LocationField
from django.db import transaction
from django.shortcuts import get_object_or_404

class AddEventForm(forms.ModelForm):
    location = LocationField(
        map_attrs={
            "id": "add-map",
        }
    )

    class Meta:
        model = Event
        fields = ['location']


class EditEventForm(forms.ModelForm):
    location = LocationField(
        map_attrs={
            "id": "edit-map",
        }
    )

    class Meta:
        model = Event
        fields = ['location']

# The same function handles both URL patterns!
def display_athlete(request, athlete_id=None, athlete_name=None):
    athlete = None
    
    # Check which parameter was passed from the URL
    if athlete_id is not None:
        athlete = Athlete.objects.filter(bib=athlete_id).first()
        
    elif athlete_name is not None:
        # Search firstName or lastName (case-insensitive)
        athlete = Athlete.objects.filter(
            Q(firstName__icontains=athlete_name) | Q(lastName__icontains=athlete_name)
        ).first()
        
    # Since we are ignoring HTML forms/templates, let's just return a simple text response
    if athlete:
        return HttpResponse(
            f"Found Athlete: {athlete.firstName} {athlete.lastName} <br>"
            f"ID: {athlete.bib} <br>"
            f"Country: {athlete.country} <br>"
            f"Class: {athlete.classification}"
        )
    else:
        return HttpResponse("Athlete not found in the database.")

# Patipan's

@login_required
def home_page_view(req):
    return render(req, 'home.html')

def display_all_athletes(request):
    athletes = Athlete.objects.all()
    return render(request, 'athletes.html', {'athletes': athletes})

# The same function handles both URL patterns!
def display_athlete(request, athlete_id=None, athlete_name=None):
    athlete = None

    # Check which parameter was passed from the URL
    if athlete_id is not None:
        athlete = Athlete.objects.filter(bib=athlete_id).first()

    elif athlete_name is not None:
        # Search firstName or lastName (case-insensitive)
        athlete = Athlete.objects.filter(
            Q(firstName__icontains=athlete_name) | Q(lastName__icontains=athlete_name)
        ).first()

    if athlete:
        return HttpResponse(
            f"Found Athlete: {athlete.firstName} {athlete.lastName} <br>"
            f"ID: {athlete.bib} <br>"
            f"Country: {athlete.country} <br>"
            f"Class: {athlete.classification}"
        )
    else:
        return HttpResponse("Athlete not found in the database.")

### (PATHOMKANT) LOGIN / REGISTER PAGE ###

def auth(req, route):
    if route == 'login':
        if req.user.is_authenticated: return redirect('home')
        if req.method == 'POST':
            # (1) get data from login.html
            uid = req.POST.get("uid")
            pwd = req.POST.get("pwd")
            user = authenticate(req, username=uid, password=pwd) # i use built-in auth (-.-||)
            # (2) check if credentials correct
            if user is not None:
                auth_login(req, user)
                return redirect('home')
            else:
                print(f"Login failed for user: {uid}")
                messages.error(req, "Invalid username or password.")
                return redirect('auth', route='login')
    
    elif route == 'register':
        if req.user.is_authenticated: return redirect('home')
        if req.method == 'POST':
            # (1) get data from register.html
            uid = (req.POST.get("uid") or "").strip()
            pwd1 = req.POST.get("pwd1") or ""
            pwd2 = req.POST.get("pwd2") or ""
            email = (req.POST.get("email") or "").strip().lower()
            role = req.POST.get("role")
            # (2) check data  (REQ 1: agent / sporter / judge / visitor)
            if role not in dict(Profile.ROLE_CHOICES):
                messages.error(req, "Please choose a role."); return redirect('auth', route='register')
            if len(uid) < 3:
                messages.error(req, "Username needs at least 3 characters."); return redirect('auth', route='register')
            if len(pwd1) < 8:
                messages.error(req, "Password needs at least 8 characters."); return redirect('auth', route='register')
            if pwd2 != pwd1:
                messages.error(req, "Passwords do not match."); return redirect('auth', route='register')
            if User.objects.filter(username=uid).exists():
                messages.error(req, "That username is already taken."); return redirect('auth', route='register')
            # (3) register uid (if 2)
            user = User.objects.create_user(username=uid, password=pwd1, email=email)
            profile = Profile.objects.create(user=user, role=role) # required when register
            if role == Profile.ROLE_SPORTER and email:
                # link to the athlete record that has the same e-mail (if any, and not yet taken)
                athlete = Athlete.objects.filter(email__iexact=email, profile__isnull=True).first()
                if athlete:
                    profile.athlete = athlete
                    profile.save()
            auth_login(req, user)
            return redirect('home')

    return render(req, 'auth.html', {'route': route, 'roles': Profile.ROLE_CHOICES})

def uid_check(req): # register.html gonna fetch() this to check for uid availability
    uid = req.GET.get('uid', '').strip()
    is_exists = User.objects.filter(username=uid).exists() # true if uid exists in database (not available)
    return JsonResponse({'exists': is_exists})

### (PATHOMKANT) ADMIN MANAGEMENT PAGE ###

def event_participants(req, number):
    event = Event.objects.get(number=number)

    eventAths = Athlete.objects.filter(participations__event=event)
    noEventAths = Athlete.objects.exclude(participations__event=event)

    results = {
        result.athlete_id: result
        for result in Result.objects.filter(
            event=event
        ).prefetch_related('attempts')
    }

    eventAths_data = []

    for athlete in eventAths:
        result = results.get(athlete.id)
        eventAths_data.append({
            "id": athlete.id,
            "bib": athlete.bib,
            "firstName": athlete.firstName,
            "lastName": athlete.lastName,
            "gender": athlete.gender,
            "classification": athlete.classification,
            "country": athlete.country,

            # result fields
            "point": result.point if result else "0",
            "rank": result.rank if result else "0",
            "medal": result.medal if result else "0",
            "best_score": result.best_score if result else "0",

            # attempt fields
            "attempts": [
                {
                    "attempt_number": attempt.attempt_number,
                    "status": attempt.status if attempt.status else "unset",
                    "score": attempt.score,
                }
                for attempt in result.attempts.all()
            ] if result else [],
        })

    return JsonResponse({
        "eventAths": eventAths_data,
        "noEventAths": list(noEventAths.values(
            "id",
            "bib",
            "firstName",
            "lastName",
            "gender",
            "classification",
            "country",
        )),
    })

def admin(req, route):
    if not req.user.is_authenticated or not req.user.is_staff:
        return redirect('home')
    if route == 'users' and not req.user.is_superuser:
        return redirect('/manage/athletes/')

    add_event_form = AddEventForm(prefix='add')
    edit_event_form = EditEventForm(prefix='edit')
    
    # fetch all users and their profiles
    users = User.objects.all().select_related('profile')
    role = 'all'
    athletes = Athlete.objects.all().order_by('bib')
    sports = Sport.objects.all()
    events = Event.objects.all().select_related().order_by('-date_time')
    eventAths = ParticipatingAthlete.objects.all().select_related()
    results = Result.objects.all().select_related()

    if req.method == 'GET':
        action = req.GET.get('Action')

        # 'Search' requests
        if action == 'findUser':
            search = req.GET.get('find', '').strip()
            role = req.GET.get('role', 'all')
            #if search:
            print(f"Search query: {search}")
            if role == 'admin':
                users = users.filter(is_superuser=True)
            elif role == 'staff':
                users = users.filter(Q(is_staff=True) & Q(is_superuser=False))
            elif role == 'user':
                users = users.filter(is_staff=False, is_superuser=False) # same as Q() & Q()

            # filtered-role 'users' var
            users = users.filter(Q(username__icontains=search)) # | Q(email__icontains=search)) # Q() is best when using |
        
        elif action == 'findAthlete':
            search = req.GET.get('find', '').strip()
            country = req.GET.get('country', 'all')
            if country == 'all':
                athletes = athletes.filter(Q(firstName__icontains=search) | Q(lastName__icontains=search))
            else:
                athletes = athletes.filter(Q(country=country) & (Q(firstName__icontains=search) | Q(lastName__icontains=search)))

        elif action == 'findEvent':
            search = req.GET.get('find', '').strip()
            events = events.filter(Q(name__icontains=search) | Q(number__icontains=search))

    if req.method == 'POST':
        action = req.POST.get('Action')

        if action == 'editUser':
            e = User.objects.get(username=req.POST.get('e-username'))
            e.username = req.POST.get('username')
            e.email = req.POST.get('email')
            e.is_staff = req.POST.get('staff') == 'on'
            e.save()
            new_role = req.POST.get('role')
            if new_role in dict(Profile.ROLE_CHOICES):
                Profile.objects.update_or_create(user=e, defaults={'role': new_role})
        
        if action == 'delUser':
            d = User.objects.get(username=req.POST.get('d-username'))
            d.delete()

        if action == 'addAthlete':            
            country = req.POST.get('country')
            bib = req.POST.get('bib')
            fname = req.POST.get('firstname')
            lname = req.POST.get('lastname')
            gender = req.POST.get('gender')
            dob = req.POST.get('dob')
            classi = req.POST.get('classification')
            pfp = req.FILES.get('pfp')
            email = req.POST.get('email')
            rem = req.POST.get('rem')
            phone = req.POST.get('phone')
            Athlete.objects.create(
                country=country,
                bib=bib,
                firstName=fname,
                lastName=lname.upper(),
                gender=gender,
                dateOfBirth=dob or None,
                classification=classi,
                imgProfile= pfp,
                email=email.lower(),
                remark=rem,
                phone=phone
                )

        if action == 'editAthlete':
            e = Athlete.objects.get(bib=req.POST.get('e-bib'))
            e.country = req.POST.get('country')
            e.bib = req.POST.get('bib')
            e.firstName = req.POST.get('firstname')
            e.lastName = req.POST.get('lastname')
            e.gender = req.POST.get('gender')
            e.dateOfBirth = req.POST.get('dob') or None
            e.classification = req.POST.get('classification')
            e.email = req.POST.get('email')
            e.remark = req.POST.get('rem')
            e.phone = req.POST.get('phone')
            pfp = req.FILES.get('pfp')
            if pfp: e.imgProfile = pfp  
            e.save()

        if action == 'delAthlete':
            d = Athlete.objects.get(bib=req.POST.get('d-bib'))
            d.delete()

        if action == 'addEvent':
            number = req.POST.get('number')
            eventname = req.POST.get('eventname')
            sport = Sport.objects.get(sport_code=req.POST.get('sport')) # get sport instance (not str)
            score = req.POST.get('score')
            status = req.POST.get('status')
            stage = req.POST.get('stage')
            datetime = req.POST.get('datetime')
            eventgender = req.POST.get('eventgender')
            eventclass = req.POST.get('eventclass')
            rem = req.POST.get('rem')
            raw_location = req.POST.get('add-location')
            judge = User.objects.filter(pk=req.POST.get('judge') or None, profile__role=Profile.ROLE_JUDGE).first() # optional
            # if raw_location: longitude, latitude = raw_location.split(',')

            Event.objects.create(
                number=number,
                name=eventname,
                classification=eventclass,
                date_time=datetime,
                gender=eventgender,
                status=status,
                location=raw_location,
                stage=stage,
                score_format=score,
                sport=sport,
                remark=rem,
                judge=judge
                )

        if action == 'peopleEvent':
            number = Event.objects.get(number=req.POST.get('number'))

            athlete_ids = req.POST.getlist('athletes')

            # delete old participant list
            ParticipatingAthlete.objects.filter(event=number).delete()
            # to replace whole with new list
            for athlete_id in athlete_ids:
                ParticipatingAthlete.objects.create(event=number, athlete_id=athlete_id)

        if action == 'editEvent':
            e = Event.objects.get(number=req.POST.get('e-number'))
            e.number = req.POST.get('number')
            e.name = req.POST.get('eventname')
            e.classification = req.POST.get('eventclass')
            e.date_time = req.POST.get('datetime')
            e.gender = req.POST.get('eventgender')
            e.status = req.POST.get('status')
            e.location = req.POST.get('edit-location')
            e.stage = req.POST.get('stage')
            e.score_format = req.POST.get('score')
            e.sport = Sport.objects.get(sport_code=req.POST.get('sport'))
            e.remark = req.POST.get('rem') 
            e.judge = User.objects.filter(pk=req.POST.get('judge') or None, profile__role=Profile.ROLE_JUDGE).first() # optional
            e.save()

        if action == 'delEvent':
            d = Event.objects.get(number=req.POST.get('d-number'))
            d.delete()

        if action == 'editResult':
            event_number = req.POST.get('res-number')
            athlete_id = req.POST.get('athlete-id')

            event = get_object_or_404(Event, number=event_number)
            athlete = get_object_or_404(Athlete, id=athlete_id)

            participation_exists = ParticipatingAthlete.objects.filter(event=event, athlete=athlete).exists()

            if not participation_exists:
                return JsonResponse({'error': 'Athlete is not participating in this event.'}, status=400)

            # if any 1 not pass: not commit
            # if all pass: commit
            with transaction.atomic():
                result, created = Result.objects.get_or_create(
                    event=event,
                    athlete=athlete,
                    defaults={
                        'point': 0,
                        'rank': 0,
                        'medal': 0,
                        'best_score': 0,
                    }
                )
                for number in range(1, 7):
                    Attempt.objects.get_or_create(
                        result=result,
                        attempt_number=number,
                        defaults={
                            'status': 'unset',
                            'score': 0,
                        }
                    )

                result.point = req.POST.get('point') or 0
                result.rank = req.POST.get('rank') or 0
                result.medal = req.POST.get('medal') or 0
                result.best_score = req.POST.get('best-score') or 0
                for attempt in result.attempts.all():
                    n = attempt.attempt_number
                    attempt.status = req.POST.get(f'status-{n}', 'unset')
                    attempt.score = req.POST.get(f'score-{n}') or 0
                    attempt.save()
                result.save()

    return render(req, 'admin.html', {'route': route, 'users': users, 'role': role, 'athletes': athletes, 'sports':sports,
                                      'events': events, 'add_event_form': add_event_form, 'edit_event_form': edit_event_form,
                                      'eventAths': eventAths, 'results': results,
                                      'judges': User.objects.filter(profile__role=Profile.ROLE_JUDGE).order_by('username')})