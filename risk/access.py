"""
Who can see and change what. Every view goes through these helpers, so the
rules live in one file:

  - Everyone sees only the companies returned by user.visible_companies().
  - Consultants and safety officers can create and edit assessments.
  - A task can be updated by its owner, or by a consultant / safety officer.
  - Superseded versions are read-only.
"""
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Assessment, Task


def current_company(request):
    """The company being viewed. Consultants can switch; everyone else is fixed to their own."""
    companies = request.user.visible_companies()
    wanted = request.GET.get("company") or request.session.get("company_id")
    company = companies.filter(id=wanted).first() if wanted else None
    if company is None:
        company = companies.filter(id=request.user.company_id).first() or companies.first()
    if company:
        request.session["company_id"] = company.id
    return company


def get_assessment(user, pk):
    a = get_object_or_404(Assessment.objects.select_related("company", "previous"), pk=pk)
    if not user.visible_companies().filter(id=a.company_id).exists():
        raise Http404
    return a


def get_task(user, pk):
    t = get_object_or_404(Task.objects.select_related("hazard__assessment__company", "owner"), pk=pk)
    if not user.visible_companies().filter(id=t.hazard.assessment.company_id).exists():
        raise Http404
    if not user.can_manage and t.owner_id != user.id:
        raise Http404
    return t


def can_edit_assessment(user, assessment):
    return user.can_manage and assessment.is_active


def can_update_task(user, task):
    return (
        (task.owner_id == user.id or user.can_manage)
        and task.is_live
        and task.hazard.assessment.is_active
    )
