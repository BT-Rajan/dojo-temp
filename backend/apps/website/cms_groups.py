"""
The two Wagtail groups that RBAC maps onto (see middleware.sync_cms_groups):

- Editors    (cms.edit):    draft pages, images, documents; edit timetable, products, size guides.
- Moderators (cms.publish): all of the above, plus publish pages and change site/shop settings.

Wagtail creates similar groups in its own migrations; this makes them exact and repairs
them if someone changes them by hand.
"""

from django.contrib.auth.models import Group, Permission
from django.db import transaction

EDIT_MODELS = [
    ("website", "timetableentry"),
    ("shop", "product"),
    ("shop", "sizeguide"),
    ("wagtailimages", "image"),
    ("wagtaildocs", "document"),
]
PUBLISH_MODELS = [("website", "sitesettings"), ("shop", "shopsettings")]


@transaction.atomic
def ensure_cms_groups():
    from wagtail.models import Collection, GroupCollectionPermission, GroupPagePermission, Page

    root = Page.get_first_root_node()
    collection = Collection.get_first_root_node()
    access = Permission.objects.get(content_type__app_label="wagtailadmin", codename="access_admin")
    groups = {}
    for name, page_perms, models in (
        ("Editors", ["add_page", "change_page"], EDIT_MODELS),
        (
            "Moderators",
            ["add_page", "change_page", "publish_page", "lock_page", "unlock_page"],
            EDIT_MODELS + PUBLISH_MODELS,
        ),
    ):
        group, _ = Group.objects.get_or_create(name=name)
        perms = [access]
        for app, model in models:
            perms += list(
                Permission.objects.filter(
                    content_type__app_label=app,
                    content_type__model=model,
                    codename__in=[f"add_{model}", f"change_{model}", f"view_{model}", f"choose_{model}"],
                )
            )
        group.permissions.add(*perms)
        if root is not None:
            for codename in page_perms:
                perm = Permission.objects.get(content_type__app_label="wagtailcore", codename=codename)
                GroupPagePermission.objects.get_or_create(group=group, page=root, permission=perm)
        if collection is not None:
            for app, model in (("wagtailimages", "image"), ("wagtaildocs", "document")):
                for action in ("add", "change", "choose"):
                    perm = Permission.objects.filter(content_type__app_label=app, codename=f"{action}_{model}").first()
                    if perm:
                        GroupCollectionPermission.objects.get_or_create(
                            group=group, collection=collection, permission=perm
                        )
        groups[name] = group
    return groups
