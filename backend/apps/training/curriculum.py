"""
The curriculum as delivered (P4-1): the Kajukenbo scalable curriculum from "Kajukenbo – Master Curriculum –
Revised.xlsx" (Belt System, Kickboxing Track, Jiujitsu Track and Self-Defence & Traditional sheets; the
"suggested additions" are not included), and belt lists for the other arts, to be confirmed by the Training
Lead (O-18). `load_curriculum()` is safe to run again: it never overwrites what has been edited in the desk.

    python manage.py load_curriculum
"""

from django.db import transaction

from apps.organization.models import Discipline

KAJUKENBO_RANKS = [
    # key, name, name_ar, phase, stripe, stripe_ar, bjj, seminars, final exam, classes, weeks
    ("white", "White belt", "الحزام الأبيض", "beginner", "", "", "", 0, False, 0, 0),
    ("yellow", "Yellow belt", "الحزام الأصفر", "beginner", "1 × White stripe", "خط أبيض واحد",
     "BJJ White (in progress)", 2, False, 24, 12),
    ("purple", "Purple belt", "الحزام البنفسجي", "beginner", "2 × White stripes", "خطان أبيضان",
     "BJJ White (completing)", 4, False, 24, 12),
    ("blue", "Blue belt", "الحزام الأزرق", "intermediate", "No stripe — the belt is the marker",
     "بلا خط — الحزام هو العلامة", "BJJ Blue (earned)", 6, False, 36, 16),
    ("green", "Green belt", "الحزام الأخضر", "intermediate", "1 × Blue stripe", "خط أزرق واحد",
     "BJJ Blue (progressing)", 8, False, 36, 16),
    ("brown", "Brown belt", "الحزام البني", "advanced", "1 × Blue stripe", "خط أزرق واحد",
     "BJJ Blue (completing)", 10, False, 48, 24),
    ("brownblack", "Brown / black stripe", "بني بخط أسود", "advanced", "1 × Purple stripe", "خط بنفسجي واحد",
     "BJJ Purple (entered)", 11, False, 60, 36),
    ("black", "Black belt", "الحزام الأسود", "expert", "1 × Purple stripe", "خط بنفسجي واحد",
     "BJJ Purple (confirmed)", 12, True, 72, 52),
]  # fmt: skip

KAJUKENBO_TRACKS = [
    # code, name, name_ar, disciplines, who teaches
    ("kickboxing", "Kickboxing", "الكيك بوكسينغ", ["kickboxing", "striking", "kajukenbo"],
     "Kickboxing, Muay Thai, Boxing, MMA striking coaches"),
    ("jiujitsu", "Jiu-Jitsu", "الجوجيتسو", ["jiujitsu", "grappling", "kajukenbo"],
     "BJJ, Judo, Grappling, MMA ground coaches"),
    ("self_defence", "Self-Defence & Traditional", "الدفاع عن النفس والتقليدي", ["kajukenbo"],
     "Kajukenbo instructors only (monthly seminars and weekend classes)"),
]  # fmt: skip

TEST_COMPONENTS = [
    ["kickboxing", "Kickboxing portion", "جزء الكيك بوكسينغ"],
    ["jiujitsu", "Jiu-Jitsu portion", "جزء الجوجيتسو"],
    ["self_defence", "Self-defence demo", "عرض الدفاع عن النفس"],
]

CATEGORY_AR = {
    "Strikes": "الضربات",
    "Kicks": "الركلات",
    "Defense": "الدفاع",
    "Movement": "الحركة",
    "Combos": "التركيبات",
    "Fitness Requirement": "متطلبات اللياقة",
    "Ground Movement": "الحركة الأرضية",
    "Positions": "الوضعيات",
    "Submissions": "الإخضاعات",
    "Takedowns": "الإسقاطات",
    "Fitness": "اللياقة",
    "Self-Defence Techniques": "تقنيات الدفاع عن النفس",
    "Traditional / Katas": "التقليدي / الكاتا",
    "Physical Requirements": "المتطلبات البدنية",
}

# Other arts: belt order to be confirmed by the Training Lead (O-18); skills are added in the desk.
OTHER_ARTS = [
    ("kyokushin", "Kyokushin Karate", "كيوكوشن كاراتيه", ["kyokushin"],
     ["white", "orange", "blue", "yellow", "green", "brown", "black"]),
    ("shin_kyokushin", "Shin-Kyokushin", "شين كيوكوشن", ["shin_kyokushin"],
     ["white", "orange", "blue", "yellow", "green", "brown", "black"]),
    ("taekwondo", "Taekwondo", "تايكوندو", ["taekwondo"], ["white", "yellow", "green", "blue", "red", "black"]),
]  # fmt: skip
BELT_NAMES = {
    "white": ("White belt", "الحزام الأبيض"),
    "orange": ("Orange belt", "الحزام البرتقالي"),
    "yellow": ("Yellow belt", "الحزام الأصفر"),
    "blue": ("Blue belt", "الحزام الأزرق"),
    "green": ("Green belt", "الحزام الأخضر"),
    "red": ("Red belt", "الحزام الأحمر"),
    "brown": ("Brown belt", "الحزام البني"),
    "black": ("Black belt", "الحزام الأسود"),
}

SKILLS = {
    "kickboxing:white": [
        ("Strikes", "Jab"),
        ("Kicks", "Front kick"),
        ("Movement", "Fighting stance"),
        ("Combos", "Jab / Cross"),
        ("Fitness Requirement", "Holding pads"),
        ("Strikes", "Cross"),
        ("Kicks", "Round kick"),
        ("Movement", "Ready stance"),
        ("Combos", "Jab Cross Double Hook"),
        ("Fitness Requirement", "Push-ups (basic)"),
        ("Movement", "Horse stance"),
        ("Combos", "Jab/ Cross front Kick"),
        ("Fitness Requirement", "Squats"),
        ("Movement", "Holding pads"),
        ("Fitness Requirement", "Burpees"),
        ("Fitness Requirement", "Jumping jacks"),
        ("Fitness Requirement", "Set-ups"),
    ],
    "kickboxing:yellow": [
        ("Strikes", "Hook"),
        ("Kicks", "Side kick"),
        ("Defense", "Duck"),
        ("Movement", "Fight movement"),
        ("Combos", "Jab Cross Left Hook Uppercut"),
        ("Fitness Requirement", "Bag work 1.5 min"),
        ("Strikes", "Uppercut"),
        ("Defense", "Parry"),
        ("Combos", "Cross Left Hook Uppercut"),
        ("Fitness Requirement", "Push-ups (10)"),
        ("Defense", "Boxing block"),
        ("Combos", "Double Jab Cross Left Hook"),
        ("Fitness Requirement", "Squats (20)"),
        ("Combos", "Jab Cross Right Round Kick"),
        ("Fitness Requirement", "Burpees (10)"),
        ("Fitness Requirement", "Jumping jacks (20)"),
        ("Fitness Requirement", "Light sparring intro"),
    ],
    "kickboxing:purple": [
        ("Strikes", "Body shots"),
        ("Kicks", "Back kick"),
        ("Defense", "Slip"),
        ("Movement", "Step work"),
        ("Fitness Requirement", "Bag work 2 min"),
        ("Strikes", "All punches fluid"),
        ("Kicks", "Kicks block (lower)"),
        ("Defense", "Head movement"),
        ("Combos", "Jab Cross Left Round Right Round"),
        ("Fitness Requirement", "Push-ups (15)"),
        ("Combos", "Left Front Kick Cross Left Hook"),
        ("Fitness Requirement", "Set-ups (15)"),
        ("Fitness Requirement", "Plank (45s)"),
        ("Fitness Requirement", "Burpees (15)"),
        ("Fitness Requirement", "Full sparring begins"),
    ],
    "kickboxing:blue": [
        ("Strikes", "Open hand strikes"),
        ("Kicks", "Axe kick"),
        ("Defense", "Kicks block (high)"),
        ("Movement", "Shuffle punch"),
        ("Fitness Requirement", "Bag work 3 min"),
        ("Kicks", "Spinning kick"),
        ("Defense", "H.M. while punching"),
        ("Movement", "Advanced step work"),
        ("Combos", "Jab Cross LH LRound RBack Kick"),
        ("Fitness Requirement", "Plank (1 min)"),
        ("Fitness Requirement", "Burpees (20)"),
        ("Fitness Requirement", "Set-ups (20)"),
        ("Fitness Requirement", "Jumping jacks (50)"),
    ],
    "kickboxing:green": [
        ("Strikes", "Elbows"),
        ("Kicks", "Brazilian round kick"),
        ("Defense", "All defense review"),
        ("Movement", "Angles work"),
        ("Fitness Requirement", "Bag work 4 min"),
        ("Strikes", "Knees"),
        ("Fitness Requirement", "Jumping jacks (60)"),
    ],
    "kickboxing:brown": [
        ("Strikes", "All strikes sharp"),
        ("Kicks", "All kicks sharp"),
        ("Defense", "All defense sharp"),
        ("Movement", "Ring control"),
        ("Combos", "Create own combos"),
        ("Fitness Requirement", "Bag work 5 min"),
        ("Strikes", "Combination fluency"),
        ("Movement", "Pressure fighting"),
        ("Fitness Requirement", "Full rounds"),
    ],
    "kickboxing:brownblack": [
        ("Strikes", "MMA-level striking"),
        ("Kicks", "All kicks mastery"),
        ("Defense", "Counter-striking"),
        ("Movement", "Fight IQ"),
        ("Combos", "Fight-specific combos"),
        ("Fitness Requirement", "Full fight rounds"),
    ],
    "kickboxing:black": [
        ("Strikes", "Teaching ability"),
        ("Kicks", "Teaching ability"),
        ("Defense", "Teaching ability"),
        ("Movement", "Teaching ability"),
        ("Combos", "Can design combos"),
        ("Fitness Requirement", "Can lead full class"),
    ],
    "jiujitsu:white": [
        ("Ground Movement", "Shrimp"),
        ("Positions", "Guard (closed)"),
        ("Takedowns", "Sweep (Takedown 1)"),
        ("Defense", "Guard break defense"),
        ("Fitness", "Drill shrimp/bridge"),
        ("Ground Movement", "Bridge"),
        ("Positions", "Seatbelt"),
        ("Takedowns", "Single leg (Takedown 2)"),
        ("Ground Movement", "Rotation"),
        ("Ground Movement", "Skydive"),
    ],
    "jiujitsu:yellow": [
        ("Ground Movement", "Technical standup"),
        ("Positions", "Side control"),
        ("Submissions", "Arm lock (basic)"),
        ("Defense", "Frame (side control)"),
        ("Fitness", "Positional sparring"),
        ("Ground Movement", "Rolls (front & back)"),
        ("Positions", "Full mount"),
        ("Takedowns", "Double leg (Takedown 2')"),
        ("Defense", "Guard retention"),
        ("Positions", "Guard break (adv.)"),
        ("Takedowns", "Takedown from back"),
    ],
    "jiujitsu:purple": [
        ("Positions", "Clinch (over/under hooks)"),
        ("Submissions", "Arm bar (from mount)"),
        ("Takedowns", "Two on one"),
        ("Defense", "Sprawl"),
        ("Fitness", "Controlled rolling"),
        ("Positions", "Back take"),
        ("Takedowns", "Hip throw (Takedown 3)"),
        ("Defense", "Half guard defense"),
        ("Positions", "Half guard (intro)"),
        ("Positions", "Knee on belly"),
    ],
    "jiujitsu:blue": [
        ("Ground Movement", "Ground sweep"),
        ("Positions", "Triangle (mount)"),
        ("Submissions", "Triangle (mount)"),
        ("Takedowns", "Knee tap"),
        ("Defense", "Pass defense"),
        ("Fitness", "Live rolling"),
        ("Positions", "Half guard (attack)"),
        ("Submissions", "Arm bar (side)"),
        ("Takedowns", "Body lock takedown"),
        ("Defense", "Back take defense"),
        ("Positions", "Att. back take"),
    ],
    "jiujitsu:green": [
        ("Positions", "Shin to shin"),
        ("Submissions", "Leg locks"),
        ("Takedowns", "Def. back takedown"),
        ("Defense", "Defending all positions"),
        ("Fitness", "Competition sparring"),
        ("Positions", "Def. back take"),
        ("Submissions", "Kimura"),
        ("Submissions", "Americana"),
        ("Submissions", "Choke (basic)"),
        ("Submissions", "Arm bar (guard)"),
        ("Submissions", "Triangle (guard)"),
    ],
    "jiujitsu:brown": [
        ("Positions", "Half guard (defend)"),
        ("Submissions", "Choke using clothes"),
        ("Defense", "Defending all (review)"),
        ("Fitness", "Full competition rounds"),
        ("Submissions", "Arm bar (guard, mastery)"),
        ("Submissions", "Triangle (guard, mastery)"),
    ],
    "jiujitsu:brownblack": [
        ("Submissions", "Triangle (back)"),
        ("Defense", "Defending all (mastery)"),
        ("Fitness", "Full fight rounds"),
        ("Submissions", "Arm bar (back)"),
        ("Submissions", "Darce choke"),
        ("Submissions", "Bow and arrow"),
        ("Submissions", "Advanced chokes"),
    ],
    "jiujitsu:black": [
        ("Positions", "Understanding & instructing all"),
        ("Submissions", "All submissions mastery"),
        ("Fitness", "Can lead full class"),
        ("Positions", "Knowledge documented"),
    ],
    "self_defence:white": [
        ("Self-Defence Techniques", "Front grabs (one hand)"),
        ("Traditional / Katas", "Exercise A"),
        ("Physical Requirements", "Push-ups (basic)"),
        ("Traditional / Katas", "Hard style block"),
        ("Physical Requirements", "Set-ups"),
        ("Traditional / Katas", "Kata 1"),
        ("Physical Requirements", "Burpees"),
        ("Physical Requirements", "Squats"),
        ("Physical Requirements", "Jumping jacks"),
    ],
    "self_defence:yellow": [
        ("Self-Defence Techniques", "Front grabs (two hands)"),
        ("Traditional / Katas", "Soft style block"),
        ("Physical Requirements", "Push-ups (10)"),
        ("Self-Defence Techniques", "Hand grab defense"),
        ("Traditional / Katas", "Exercise B"),
        ("Physical Requirements", "Squats (20)"),
        ("Traditional / Katas", "Kata 2"),
        ("Physical Requirements", "Plank (30s)"),
        ("Traditional / Katas", "Vertical punches"),
        ("Physical Requirements", "Burpees (10)"),
        ("Traditional / Katas", "Reverse punches"),
        ("Physical Requirements", "Jumping jacks (20)"),
    ],
    "self_defence:purple": [
        ("Self-Defence Techniques", "Back choke defense"),
        ("Traditional / Katas", "Exercise B (advanced)"),
        ("Physical Requirements", "Push-ups (15)"),
        ("Self-Defence Techniques", "Side choke defense"),
        ("Traditional / Katas", "Kata 3"),
        ("Physical Requirements", "Set-ups (15)"),
        ("Self-Defence Techniques", "Bear hug defense"),
        ("Physical Requirements", "Plank (45s)"),
        ("Physical Requirements", "Burpees (15)"),
        ("Physical Requirements", "Jumping jacks (40)"),
    ],
    "self_defence:blue": [
        ("Self-Defence Techniques", "Rear grabs"),
        ("Traditional / Katas", "Kata 4"),
        ("Physical Requirements", "Plank (1 min)"),
        ("Self-Defence Techniques", "Multiple attackers (holding)"),
        ("Traditional / Katas", "Kata 5"),
        ("Physical Requirements", "Burpees (20)"),
        ("Physical Requirements", "Set-ups (20)"),
        ("Physical Requirements", "Jumping jacks (50)"),
    ],
    "self_defence:green": [
        ("Self-Defence Techniques", "Multiple attackers (hitting)"),
        ("Traditional / Katas", "Kata 6"),
        ("Physical Requirements", "Jumping jacks (60)"),
        ("Self-Defence Techniques", "Pressure points"),
        ("Traditional / Katas", "Kata 7"),
        ("Physical Requirements", "Bag work (4 min)"),
    ],
    "self_defence:brown": [
        ("Self-Defence Techniques", "Weapons defense (sticks)"),
        ("Traditional / Katas", "Kata 8"),
        ("Physical Requirements", "Bag work (5 min)"),
    ],
    "self_defence:brownblack": [
        ("Self-Defence Techniques", "Weapons defense (knives)"),
        ("Traditional / Katas", "Kata 9"),
    ],
    "self_defence:black": [
        ("Self-Defence Techniques", "All self-defence mastery"),
        ("Traditional / Katas", "Kata 10"),
        ("Physical Requirements", "All requirements exceeded"),
        ("Self-Defence Techniques", "Can teach all techniques"),
        ("Traditional / Katas", "All katas mastery"),
    ],
}


def _disciplines(codes):
    return list(Discipline.objects.filter(code__in=codes))


@transaction.atomic
def load_curriculum() -> dict:
    from .models import Art, Rank, Skill, Track

    made = {"arts": 0, "ranks": 0, "skills": 0}
    art, created = Art.objects.get_or_create(
        code="kajukenbo",
        defaults={"name": "Kajukenbo", "name_ar": "كاجوكينبو", "test_components": TEST_COMPONENTS},
    )
    made["arts"] += created
    if created:
        art.disciplines.set(_disciplines(["kajukenbo", "kickboxing", "jiujitsu", "grappling", "striking"]))
    tracks = {}
    for i, (code, name, name_ar, discs, who) in enumerate(KAJUKENBO_TRACKS):
        track, created = Track.objects.get_or_create(
            art=art, code=code, defaults={"name": name, "name_ar": name_ar, "order": i, "who_teaches": who}
        )
        if created:
            track.disciplines.set(_disciplines(discs))
        tracks[code] = track
    ranks = {}
    for i, (key, name, name_ar, phase, stripe, stripe_ar, bjj, seminars, final, classes, weeks) in enumerate(
        KAJUKENBO_RANKS
    ):
        rank, created = Rank.objects.get_or_create(
            art=art,
            order=i,
            defaults={
                "name": name,
                "name_ar": name_ar,
                "belt": key,
                "phase": phase,
                "stripe": stripe,
                "stripe_ar": stripe_ar,
                "bjj_equivalent": bjj,
                "seminars_required": seminars,
                "final_exam": final,
                "min_classes": classes,
                "min_weeks": weeks,
                "min_evaluations": 2 if i else 0,
            },
        )
        made["ranks"] += created
        ranks[key] = rank
    for group, items in SKILLS.items():
        track_code, belt = group.split(":")
        rank, track = ranks[belt], tracks[track_code]
        if Skill.objects.filter(rank=rank, track=track).exists():
            continue  # already loaded (and possibly edited by the Training Lead)
        Skill.objects.bulk_create(
            [
                Skill(
                    rank=rank,
                    track=track,
                    category=category,
                    category_ar=CATEGORY_AR.get(category, ""),
                    name=name,
                    order=n,
                )
                for n, (category, name) in enumerate(items)
            ]
        )
        made["skills"] += len(items)
    for code, name, name_ar, discs, belts in OTHER_ARTS:
        other, created = Art.objects.get_or_create(
            code=code,
            defaults={"name": name, "name_ar": name_ar, "test_components": [["practical", "Practical", "العملي"]]},
        )
        if not created:
            continue
        made["arts"] += 1
        other.disciplines.set(_disciplines(discs))
        Track.objects.create(art=other, code="main", name=name, name_ar=name_ar)
        for i, key in enumerate(belts):
            Rank.objects.create(
                art=other,
                order=i,
                name=BELT_NAMES[key][0],
                name_ar=BELT_NAMES[key][1],
                belt=key,
                min_classes=24 if i else 0,
                min_weeks=12 if i else 0,
                min_evaluations=2 if i else 0,
            )
            made["ranks"] += 1
    return made
