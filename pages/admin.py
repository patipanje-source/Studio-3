from django.contrib import admin
from .models import Profile, Sport, Athlete, Event, ParticipatingAthlete, Result, Attempt, PointTable

class AttemptInline(admin.TabularInline):
    model = Attempt
    extra = 0

admin.site.register(Sport)
admin.site.register(Athlete)
admin.site.register(ParticipatingAthlete)

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'date_time', 'status', 'judge')
    search_fields = ('name', 'number')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'athlete')
    list_filter = ('role',)

@admin.register(PointTable)
class PointTableAdmin(admin.ModelAdmin):
    list_display = ('event', 'classification', 'gender', 'kind', 'a', 'b', 'c')
    list_filter = ('kind', 'gender', 'event')

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    inlines = [AttemptInline]
