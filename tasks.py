from celery.registry import tasks
from celery.task import Task 
from celery import task
from django.core import management

# This is having some problems with celery 3.0.11 and mod_wsgi
class CreateInstancesTask(Task):
    def run(self, pk):
        management.call_command('create_instances', verbosity=0, pk=pk)

tasks.register(CreateInstancesTask)


@task()
def create_instances_task(pk):
    management.call_command('create_instances', verbosity=0, pk=pk)
