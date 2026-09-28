"""
Member / parent portal. A portal user only ever sees their own family:
records are found through the logged-in user's own guardian or member profile,
never by an id sent from the browser.
"""

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.members.models import Member


class MyFamilyView(APIView):
    required_perm = "portal.own_family"

    def get(self, request):
        user = request.user
        members = Member.objects.none()
        guardian = getattr(user, "guardian_profile", None)
        if guardian is not None:
            members = guardian.members.all()
        own = getattr(user, "member_profile", None)
        if own is not None:
            members = members | Member.objects.filter(pk=own.pk)
        members = members.select_related("branch").distinct()
        return Response(
            {
                "family": [
                    {
                        "id": m.id,
                        "name": f"{m.first_name} {m.last_name}",
                        "name_ar": f"{m.first_name_ar} {m.last_name_ar}".strip(),
                        "branch": m.branch.name,
                        "age": m.age,
                        "is_active": m.is_active,
                    }
                    for m in members
                ]
            }
        )
