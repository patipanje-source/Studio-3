from django.db import models

class Athlete(models.Model):
    country = models.CharField(max_length=3)
    athlete_id = models.IntegerField(unique=True) 
    firstName = models.CharField(max_length=100)
    lastName = models.CharField(max_length=100)
    gender = models.CharField(max_length=20, null=True, blank=True)
    dateOfBirth = models.DateField(null=True, blank=True)
    classification = models.CharField(max_length=20, null=True, blank=True)
    imgProfile = models.URLField(max_length=500, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    def __str__(self):
        return f"{self.firstName} {self.lastName} ({self.country})"