from django.db import models

# Create your models here.

class SeismicData(models.Model):
    data = models.JSONField()
    file_name = models.CharField(max_length =255)