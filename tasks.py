from celery.registry import tasks
from celery.task import Task 
#from models import Trackpost

class CreateInstancesTask(Task):
    #def run(self, **kwargs):
    #name = 'CheckWebsiteTask'
    def run(self, pk):
        #tp = Trackpost.objects.get(pk=pk)
        #print tp.file.path
        from django.core import management
        management.call_command('create_instances', verbosity=0, pk=pk)
        #management.call_command('loaddata', 'test_data', verbosity=0)

tasks.register(CreateInstancesTask)

