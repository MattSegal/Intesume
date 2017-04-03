from __future__ import unicode_literals

from django.db import models

class Panel(models.Model):
    html = models.TextField(default='')
    order = models.IntegerField()

    def __unicode__(self):
        return u'Panel #{}'.format(self.order)