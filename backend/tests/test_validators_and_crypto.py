import datetime
import random

import pytest
from django.core.exceptions import ValidationError
from django.db import connection

from apps.core.crypto import blind_index, mask
from apps.core.validators import civil_id_birth_date, normalize_kuwait_mobile, validate_civil_id
from apps.members.models import Member
from apps.testdata.kuwait import make_civil_id


def test_generated_civil_ids_are_valid_and_match_birth_date():
    rng = random.Random(1)
    used = set()
    for dob in (datetime.date(1985, 3, 14), datetime.date(2015, 12, 1), datetime.date(2004, 2, 29)):
        cid = make_civil_id(rng, dob, used)
        validate_civil_id(cid)
        assert civil_id_birth_date(cid) == dob


@pytest.mark.parametrize("bad", ["12345", "285031412345X", "285133112345", "999999999999"])
def test_invalid_civil_ids_are_rejected(bad):
    with pytest.raises(ValidationError):
        validate_civil_id(bad)


def test_civil_id_wrong_check_digit_rejected():
    cid = make_civil_id(random.Random(2), datetime.date(1990, 1, 1), set())
    wrong = cid[:11] + str((int(cid[11]) + 1) % 10)
    with pytest.raises(ValidationError):
        validate_civil_id(wrong)


@pytest.mark.parametrize("raw", ["99887766", "+96599887766", "00965 9988 7766", "9988-7766"])
def test_kuwait_mobiles_are_normalised(raw):
    assert normalize_kuwait_mobile(raw) == "+96599887766"


@pytest.mark.parametrize("raw", ["12345678", "2222333", "+97199887766"])
def test_non_kuwait_mobiles_rejected(raw):
    with pytest.raises(ValidationError):
        normalize_kuwait_mobile(raw)


def test_mask_shows_only_last_four():
    assert mask("285031412345") == "********2345"


@pytest.mark.django_db
def test_sensitive_fields_are_encrypted_at_rest(branches):
    member = Member.objects.create(
        branch=branches["PRM"],
        first_name="A",
        last_name="B",
        gender="male",
        date_of_birth=datetime.date(2015, 1, 1),
        civil_id="315010112340",
        medical_notes="Asthma — carries inhaler",
    )
    with connection.cursor() as cursor:
        cursor.execute("SELECT civil_id, medical_notes FROM members_member WHERE id=%s", [member.id])
        raw_cid, raw_medical = cursor.fetchone()
    assert "315010112340" not in raw_cid and "Asthma" not in raw_medical
    fresh = Member.objects.get(pk=member.pk)
    assert fresh.civil_id == "315010112340" and fresh.medical_notes.startswith("Asthma")
    assert fresh.civil_id_index == blind_index("315010112340")
