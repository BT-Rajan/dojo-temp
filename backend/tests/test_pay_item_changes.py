"""Changing a pay item: corrected in place until it has been used in a submitted payroll, then split by date."""

import datetime
from decimal import Decimal as D

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.payroll import services as pay
from apps.payroll.models import PayComponent, PayrollRun
from apps.staff.models import StaffProfile


@pytest.fixture
def setup(make_user):
    om = make_user("operations_manager")
    coach = make_user("instructor")
    staff = StaffProfile.objects.create(
        user=coach, job_title="Coach", employment_type="hourly", start_date=datetime.date(2025, 1, 1)
    )
    profile = pay.save_pay_profile(staff, om)
    salary = pay.save_component(profile, om, kind="salary", amount=D("400"), valid_from=datetime.date(2026, 1, 1))
    return om, coach, staff, profile, salary


def test_unused_item_is_corrected_in_place(setup):
    om, coach, staff, profile, salary = setup
    changed = pay.change_component(salary, om, amount=D("450"))
    assert changed.pk == salary.pk and changed.amount == D("450")
    assert PayComponent.objects.filter(profile=profile).count() == 1
    with pytest.raises(PermissionDenied):
        pay.change_component(salary, coach, amount=D("999"))  # nobody sets their own pay


def test_item_used_in_submitted_payroll_is_split(setup):
    om, coach, staff, profile, salary = setup
    month = timezone.localdate().replace(day=1)
    run = pay.build_run(month, om)
    assert pay.component_locked_until(salary) is None  # a draft run doesn't lock it
    PayrollRun.objects.filter(pk=run.pk).update(status=PayrollRun.Status.SUBMITTED)
    locked = pay.component_locked_until(salary)
    assert locked == pay.month_end(month)
    with pytest.raises(ValidationError):
        pay.change_component(salary, om, effective_from=month, amount=D("450"))  # inside a paid month
    start = locked + datetime.timedelta(days=1)
    new = pay.change_component(salary, om, effective_from=start, amount=D("450"))
    salary.refresh_from_db()
    assert salary.amount == D("400") and salary.valid_to == locked  # the paid rate stays
    assert new.pk != salary.pk and new.amount == D("450") and new.valid_from == start and new.kind == "salary"
