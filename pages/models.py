import os
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from mapbox_location_field.models import LocationField

def athlete_pfp_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    filename_base = f"pfp{instance.bib}"

    upload_dir = os.path.join(settings.MEDIA_ROOT, "athletePfp")

    # delete previous pfp
    for old_ext in [".jpg", ".jpeg", ".png"]:
        old_file = os.path.join(upload_dir, filename_base + old_ext)

        if os.path.exists(old_file):
            os.remove(old_file)

    return f"athletePfp/{filename_base}{ext}"


class Athlete(models.Model):
    country = models.CharField(max_length=3)
    bib = models.IntegerField(unique=True)
    firstName = models.CharField(max_length=100)
    lastName = models.CharField(max_length=100)
    gender = models.CharField(max_length=20, null=True, blank=True)
    dateOfBirth = models.DateField(null=True, blank=True)
    classification = models.CharField(max_length=20, null=True, blank=True)
    imgProfile = models.ImageField(upload_to=athlete_pfp_path)
    email = models.EmailField(null=True, blank=True)
    remark = models.CharField(max_length=100, null=True, blank=True)
    phone = models.IntegerField(null=True, blank=True)

    def __str__(self): return f"{self.firstName} {self.lastName} ({self.country})"
         
class Profile(models.Model):
    ROLE_AGENT = 'agent'
    ROLE_SPORTER = 'sporter'
    ROLE_JUDGE = 'judge'
    ROLE_VISITOR = 'visitor'
    # 'admin' is NOT a self-register role: admins are users with is_staff / is_superuser
    ROLE_CHOICES = [
        (ROLE_AGENT, 'Agent'),
        (ROLE_SPORTER, 'Sporter (athlete)'),
        (ROLE_JUDGE, 'Judge'),
        (ROLE_VISITOR, 'Visitor'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE) # profile.user
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_VISITOR)
    # a sporter account can be linked to its Athlete record (matched by e-mail at register time)
    athlete = models.OneToOneField('Athlete', null=True, blank=True, on_delete=models.SET_NULL, related_name='profile')
    # 'null' - can be added later in DB | 'blank' is for validation for blank field in forms
    def __str__(self): return str(self.user) # func to display object as something (like str(self.user)) in Django Admin Page

class Sport(models.Model):
    sport_type = models.CharField(max_length=100)
    sport_code = models.CharField(max_length=3, unique=True)
    def __str__(self): return self.sport_type

class Event(models.Model):
    number = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)
    classification = models.CharField(max_length=20, null=True, blank=True)
    date_time = models.DateTimeField()
    gender = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=100)
    location = LocationField()
    stage = models.CharField(max_length=500, null=True, blank=True)
    score_format = models.CharField(max_length=500, null=True, blank=True)
    sport = models.ForeignKey(Sport, on_delete=models.CASCADE, related_name='events')
    remark = models.CharField(max_length=100, null=True, blank=True)
    # requirement 3: the judge of an event is OPTIONAL
    judge = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='judged_events')

    def __str__(self): return self.name

class ParticipatingAthlete(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="participations")
    athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE, related_name="participations")
    
    def __str__(self): return f"{self.event} - {self.athlete}"

class Result(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='results')
    athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE, related_name='results')
    best_score = models.IntegerField(null=True, blank=True)
    medal = models.IntegerField()
    rank = models.IntegerField()
    point = models.IntegerField()

    def __str__(self): return f"{self.event} - {self.athlete}"

class Attempt(models.Model):
    result = models.ForeignKey(Result, on_delete=models.CASCADE, related_name='attempts')
    attempt_number = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=100)
    score = models.IntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['result', 'attempt_number'],
                name='unique_attempt'
            ),
        ]


class PointTable(models.Model):
    """
    Parameters of the points formula (ERD tables FIELDPOINT + TRACKPOINT merged into one).
    points = a * exp(-exp(b - c * performance))
    performance = metres (field) or seconds (track).
    `event` is matched as a lowercase substring of Event.name (e.g. 'long jump').
    """
    KIND_FIELD = 'field'
    KIND_TRACK = 'track'
    KIND_CHOICES = [(KIND_FIELD, 'Field (distance)'), (KIND_TRACK, 'Track (time)')]

    kind = models.CharField(max_length=5, choices=KIND_CHOICES)
    event = models.CharField(max_length=50, help_text="lowercase name fragment, e.g. 'long jump'")
    classification = models.CharField(max_length=20)
    gender = models.CharField(max_length=5, help_text="'men' or 'women'")
    a = models.FloatField()
    b = models.FloatField()
    c = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['kind', 'event', 'classification', 'gender'], name='unique_point_row'),
        ]

    def __str__(self): return f"{self.event} {self.classification} {self.gender}"
