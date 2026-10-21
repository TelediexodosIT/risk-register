from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("assessments/", views.assessment_list, name="assessment_list"),
    path("assessments/new/", views.assessment_create, name="assessment_create"),
    path("assessments/<int:pk>/", views.assessment_detail, name="assessment_detail"),
    path("assessments/<int:pk>/rule/", views.assessment_rule, name="assessment_rule"),
    path("assessments/<int:pk>/reassess/", views.assessment_reassess, name="assessment_reassess"),
    path("assessments/<int:pk>/hazards/new/", views.hazard_create, name="hazard_create"),
    path("assessments/<int:pk>/hazards/<int:hazard_id>/", views.hazard_edit, name="hazard_edit"),
    path("tasks/", views.task_list, name="task_list"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("evidence/<int:pk>/", views.evidence_photo, name="evidence_photo"),
    path("library/", views.library, name="library"),
    path("matrix/", views.matrix, name="matrix"),
    path("reports/", views.report, name="report"),
    path("reports/<int:pk>/", views.report, name="report_detail"),
    path("updates/", views.updates, name="updates"),
]
