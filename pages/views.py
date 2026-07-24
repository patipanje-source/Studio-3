from django.http import HttpResponse
from django.http import HttpResponse
from django.db.models import Q
from .models import Athlete
from django.shortcuts import render


def home_page_view(request):
    return HttpResponse("Hello, World! This is my first Django app.")

# The same function handles both URL patterns!
def display_athlete(request, athlete_id=None, athlete_name=None):
    athlete = None
    
    # Check which parameter was passed from the URL
    if athlete_id is not None:
        athlete = Athlete.objects.filter(athlete_id=athlete_id).first()
        
    elif athlete_name is not None:
        # Search firstName or lastName (case-insensitive)
        athlete = Athlete.objects.filter(
            Q(firstName__icontains=athlete_name) | Q(lastName__icontains=athlete_name)
        ).first()
        
    # Since we are ignoring HTML forms/templates, let's just return a simple text response
    if athlete:
        return HttpResponse(
            f"Found Athlete: {athlete.firstName} {athlete.lastName} <br>"
            f"ID: {athlete.athlete_id} <br>"
            f"Country: {athlete.country} <br>"
            f"Class: {athlete.classification}"
        )
    else:
        return HttpResponse("Athlete not found in the database.")


def display_all_athletes(request):
    athletes = Athlete.objects.all()

    return render(request, 'athletes.html', {
        'athletes': athletes
    })