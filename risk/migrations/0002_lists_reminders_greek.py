"""
Update 2:
  - The hazard library becomes editable dropdown lists (ListItem). Existing library entries
    (hazards, their controls and measures) are copied into the lists, nothing is lost.
  - "Who is affected" tick boxes become a free list (one entry per line).
  - Greek labels for the scoring tables, reminder fields on actions.
"""
from django.db import migrations, models


def forwards(apps, schema_editor):
    Hazard = apps.get_model("risk", "Hazard")
    ListItem = apps.get_model("risk", "ListItem")
    HazardTemplate = apps.get_model("risk", "HazardTemplate")

    for h in Hazard.objects.all():
        who = []
        if h.affects_operator:
            who.append("Operator")
        if h.affects_employees:
            who.append("Other employees")
        if h.affects_third_parties:
            who.append("Third parties")
        h.affected = "\n".join(who)
        h.save(update_fields=["affected"])

    def add(kind, text, order):
        text = (text or "").strip()
        if text:
            ListItem.objects.get_or_create(kind=kind, text=text[:300], defaults={"order": order})

    for i, t in enumerate(HazardTemplate.objects.all()):
        add("hazard", t.name, i)
        # Library consequences were free sentences; the new default consequence list replaces them.
        for c in t.controls.all():
            add("control", c.text, 100)
        for m in t.measures.all():
            add("measure", m.text, 100)
    for i, who in enumerate(["Operator", "Other employees", "Third parties"]):
        add("affected", who, i)


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0001_initial"),
    ]

    operations = [
        # 1. New fields and the list table
        migrations.AddField(
            model_name="hazard",
            name="affected",
            field=models.TextField(blank=True, verbose_name="Who is involved"),
        ),
        migrations.CreateModel(
            name="ListItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[
                    ("hazard", "Hazard"), ("affected", "Who is involved"), ("consequence", "Consequence"),
                    ("control", "Existing control measure"), ("measure", "Additional measure")],
                    db_index=True, max_length=20)),
                ("text", models.CharField(max_length=300, verbose_name="Text (English)")),
                ("text_el", models.CharField(blank=True, max_length=300, verbose_name="Text (Greek)")),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True, help_text="Untick to hide it from the dropdown without deleting it.")),
            ],
            options={"ordering": ["kind", "order", "text"], "unique_together": {("kind", "text")}},
        ),
        # 2. Copy existing data across
        migrations.RunPython(forwards, migrations.RunPython.noop),
        # 3. Remove what is no longer used
        migrations.RemoveField(model_name="hazard", name="template"),
        migrations.RemoveField(model_name="hazard", name="affects_employees"),
        migrations.RemoveField(model_name="hazard", name="affects_operator"),
        migrations.RemoveField(model_name="hazard", name="affects_third_parties"),
        migrations.RemoveField(model_name="measuretemplate", name="hazard"),
        migrations.DeleteModel(name="ControlTemplate"),
        migrations.DeleteModel(name="HazardTemplate"),
        migrations.DeleteModel(name="MeasureTemplate"),
        # 4. Greek labels and reminders
        migrations.AddField(model_name="consequencelevel", name="label_el",
                            field=models.CharField(blank=True, max_length=60, verbose_name="Label (Greek)")),
        migrations.AddField(model_name="likelihoodlevel", name="label_el",
                            field=models.CharField(blank=True, max_length=60, verbose_name="Label (Greek)")),
        migrations.AddField(model_name="riskrating", name="action_el",
                            field=models.TextField(blank=True, verbose_name="Meaning (Greek)")),
        migrations.AddField(model_name="riskrating", name="label_el",
                            field=models.CharField(blank=True, max_length=40, verbose_name="Label (Greek)")),
        migrations.AddField(model_name="task", name="overdue_sent_on", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="task", name="remind_days", field=models.PositiveSmallIntegerField(
            default=3, help_text="Send a reminder this many days before the deadline (0 = no reminder).")),
        migrations.AddField(model_name="task", name="reminder_sent_on", field=models.DateField(blank=True, null=True)),
    ]
