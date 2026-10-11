from django.contrib import admin
from .models import Profile, Sport, Athlete, Event, ParticipatingAthlete, Result, Attempt

class AttemptInline(admin.TabularInline):
    model = Attempt
    extra = 0

# Register your models here.
# admin.site.register(Profile)
admin.site.register(Sport)
admin.site.register(Athlete)
admin.site.register(ParticipatingAthlete)
admin.site.register(Event)
@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    inlines = [AttemptInline]