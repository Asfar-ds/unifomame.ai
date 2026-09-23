"""Guess the child's class, age and gender from the uploaded file name,
e.g. "Class 5 Boys Shirt.png", "grade-3_girl.jpg", "KG uniform.png", "7th-shirt.png"."""
import re

ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12}

# (regex, class label, age) — checked in order before numeric classes
PRE_SCHOOL = [
    (r"play\s*group|\bpg\b|toddler", "Playgroup", 3),
    (r"nursery|montessori", "Nursery", 4),
    (r"\bkg\d?\b|kinder\s*garten|kindergarten|\bprep\b|reception", "KG", 5),
    (r"a[\s-]*level", "A Level", 17),
    (r"o[\s-]*level|matric", "O Level / Matric", 15),
    (r"\bfsc\b|inter(mediate)?\b|college", "Intermediate", 17),
]

DEFAULT = {"classLabel": None, "age": 8, "gender": "boy", "detected": False}


def _norm(name: str) -> str:
    name = re.sub(r"\.[a-z0-9]+$", "", name.lower())
    return re.sub(r"[_\-.]+", " ", name)


def _grade(text: str) -> int | None:
    m = re.search(r"\b(?:class|grade|std|standard|gr|cl)\s*(\d{1,2}|[ivx]{1,4})\b", text)
    if m:
        g = m.group(1)
        return int(g) if g.isdigit() else ROMAN.get(g)
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\b", text)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(?:class|grade|g)(\d{1,2})\b", text)  # "class5", "g5"
    return int(m.group(1)) if m else None


def _gender(text: str) -> str | None:
    if re.search(r"\b(girls?|female|ladies|frock|skirt)\b", text):
        return "girl"
    if re.search(r"\b(boys?|male|gents)\b", text):
        return "boy"
    return None


def guess(*filenames: str | None) -> dict:
    result = dict(DEFAULT)
    for name in filter(None, filenames):
        text = _norm(name)
        if not result["detected"]:
            for pattern, label, age in PRE_SCHOOL:
                if re.search(pattern, text):
                    result.update(classLabel=label, age=age, detected=True)
                    break
            else:
                g = _grade(text)
                if g and 1 <= g <= 12:
                    result.update(classLabel=f"Class {g}", age=g + 5, detected=True)
        gender = _gender(text)
        if gender:
            result["gender"] = gender
    return result


def describe(age: int, gender: str) -> str:
    """Short phrase used inside the Claid prompts."""
    if age <= 5:
        stage = "toddler" if age <= 3 else "preschool"
    elif age <= 10:
        stage = "primary school"
    elif age <= 13:
        stage = "middle school"
    else:
        stage = "teenage high school"
    kid = "girl" if gender == "girl" else "boy"
    return f"a {age} year old {stage} {kid}"
