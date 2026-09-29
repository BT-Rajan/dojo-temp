from django.urls import path

from .views import auth, checkin, classes, home, manage, members, sales

app_name = "desk"

urlpatterns = [
    path("", home.home, name="home"),
    path("sign-in/", auth.login_view, name="login"),
    path("sign-out/", auth.logout_view, name="logout"),
    path("two-factor/", auth.mfa_setup, name="mfa_setup"),
    path("password/", auth.change_password, name="change_password"),
    path("branch/", auth.switch_branch, name="switch_branch"),
    # Check-in
    path("check-in/", checkin.checkin, name="checkin"),
    path("check-in/do/", checkin.checkin_do, name="checkin_do"),
    # Members
    path("members/", members.member_list, name="members"),
    path("members/new/", members.member_new, name="member_new"),
    path("members/<int:pk>/", members.member_detail, name="member"),
    path("members/<int:pk>/edit/", members.member_edit, name="member_edit"),
    path("members/<int:pk>/photo/", members.member_photo, name="member_photo"),
    path("members/<int:pk>/photo.jpg", members.member_photo_file, name="member_photo_file"),
    path("members/<int:pk>/card/", members.member_card, name="member_card"),
    path("members/<int:pk>/consent/", members.member_consent, name="member_consent"),
    path("members/<int:pk>/enroll/", members.member_enroll, name="member_enroll"),
    path("members/<int:pk>/enroll/<int:enrollment_id>/end/", members.member_unenroll, name="member_unenroll"),
    path("members/<int:pk>/active/", members.member_deactivate, name="member_deactivate"),
    # Sales
    path("sell/", sales.sell, name="sell"),
    path("sales/", sales.sale_list, name="sales"),
    path("sales/<int:pk>/", sales.sale_detail, name="sale"),
    path("sales/<int:pk>/send/", sales.sale_resend, name="sale_resend"),
    path("requests/new/", sales.request_new, name="request_new"),
    # Classes
    path("timetable/", classes.timetable, name="timetable"),
    path("timetable/new/", classes.slot_edit, name="slot_new"),
    path("timetable/<int:pk>/", classes.slot_edit, name="slot_edit"),
    path("rooms/", classes.rooms, name="rooms"),
    path("classes/", classes.sessions, name="sessions"),
    path("classes/new/", classes.session_new, name="session_new"),
    path("classes/mine/", classes.my_classes, name="my_classes"),
    path("classes/<int:pk>/", classes.session_detail, name="session"),
    path("classes/<int:pk>/check-in/", classes.session_checkin, name="session_checkin"),
    path("classes/<int:pk>/undo/<int:attendance_id>/", classes.session_undo, name="session_undo"),
    path("classes/<int:pk>/book/", classes.session_book, name="session_book"),
    path("classes/<int:pk>/change/", classes.change_request, name="change_request"),
    path("bookings/<int:pk>/cancel/", classes.booking_cancel, name="booking_cancel"),
    path("class-changes/", classes.change_log, name="changes"),
    path("class-changes/<int:pk>/decide/", classes.change_decide, name="change_decide"),
    # Management
    path("approvals/", manage.approvals, name="approvals"),
    path("approvals/requests/<int:pk>/", manage.request_decide, name="request_decide"),
    path("approvals/prices/<int:pk>/", manage.price_decide, name="price_decide"),
    path("cash-up/", manage.cash_up, name="cashup"),
    path("cash-up/<int:pk>/verify/", manage.cash_up_verify, name="cashup_verify"),
    path("renewals/", manage.renewals_list, name="renewals"),
    path("renewals/<int:pk>/", manage.renewal_record, name="renewal_record"),
    path("handoffs/<int:pk>/done/", manage.handoff_done, name="handoff_done"),
    path("pricing/", manage.pricing, name="pricing"),
    path("pricing/discounts/<int:pk>/toggle/", manage.discount_toggle, name="discount_toggle"),
    path("reports/", manage.reports, name="reports"),
    path("trials/", manage.trial_requests, name="trials"),
    path("trials/<int:pk>/", manage.trial_update, name="trial_update"),
]
