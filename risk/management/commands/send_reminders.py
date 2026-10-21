from django.core.management.base import BaseCommand

from risk.services import send_due_reminders


class Command(BaseCommand):
    help = "Email deadline reminders and overdue notices. Safe to run often: each one is sent only once."

    def handle(self, *args, **opts):
        reminders, overdue = send_due_reminders()
        self.stdout.write(f"Reminders sent: {reminders}, overdue notices sent: {overdue}")
