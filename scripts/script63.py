from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error


@dataclass
class Student:
    student_id: str
    name: str
    grades: Dict[str, float] = field(default_factory=dict)
    enrolled_at: datetime = field(default_factory=datetime.utcnow)

    def average(self) -> float:
        if not self.grades:
            return 0.0
        return sum(self.grades.values()) / len(self.grades)

    def passed(self, threshold: float = 50.0) -> bool:
        avg = self.average()
        if avg == 0.0:
            return False
        return avg >= threshold

    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        if not q:
            return True
        if q in self.name.lower():
            return True
        return q in self.student_id.lower()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "student_id": self.student_id,
            "name": self.name,
            "grades": self.grades,
            "enrolled_at": self.enrolled_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Optional["Student"]:
        try:
            enrolled_raw = raw.get("enrolled_at")
            enrolled = (
                datetime.fromisoformat(enrolled_raw)
                if isinstance(enrolled_raw, str)
                else datetime.utcnow()
            )
            return cls(
                student_id=str(raw.get("student_id", "")),
                name=str(raw.get("name", "")),
                grades=dict(raw.get("grades", {})),
                enrolled_at=enrolled,
            )
        except Exception:
            return None


class Course:
    def __init__(self, course_id: str, title: str) -> None:
        self.course_id = course_id
        self.title = title
        self._students: Dict[str, Student] = {}

    def add_student(self, student: Student) -> None:
        self._students[student.student_id] = student

    def get_student(self, student_id: str) -> Optional[Student]:
        return self._students.get(student_id)

    def all_students(self) -> List[Student]:
        return list(self._students.values())

    def class_average(self) -> float:
        students = self.all_students()
        if not students:
            return 0.0
        return sum(s.average() for s in students) / len(students)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "title": self.title,
            "students": [s.to_dict() for s in self._students.values()],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Course":
        course = cls(str(raw.get("course_id", "")), str(raw.get("title", "")))
        for s_raw in raw.get("students", []):
            student = Student.from_dict(s_raw)
            if student:
                course.add_student(student)
        return course


class AnalyticsClient:
    def __init__(self, base_url: str, timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, course_id: str) -> str:
        return f"{self.base_url}/courses/{course_id}/benchmarks.json"

    def fetch_benchmarks(self, course_id: str) -> Optional[Dict[str, Any]]:
        if not self.base_url:
            return None
        url = self._url(course_id)
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
            return json.loads(data.decode("utf-8"))
        except (error.URLError, error.HTTPError, json.JSONDecodeError):
            return None

    def push_summary(self, course_id: str, summary: Dict[str, Any]) -> bool:
        if not self.base_url:
            return False
        url = f"{self.base_url}/courses/{course_id}/summary"
        body = json.dumps(summary).encode("utf-8")
        req = request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except error.URLError:
            return False


def load_course(path: Path) -> Course:
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return Course.from_dict(raw)
    except (OSError, json.JSONDecodeError):
        return Course(course_id="local", title="Local Course")


def save_course(path: Path, course: Course) -> None:
    payload = course.to_dict()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(path)
    except OSError:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def summarize_course(course: Course) -> Dict[str, Any]:
    students = course.all_students()
    if not students:
        return {"count": 0, "class_avg": 0.0, "pass_rate": 0.0}
    count = len(students)
    passed = sum(1 for s in students if s.passed())
    return {
        "count": count,
        "class_avg": course.class_average(),
        "pass_rate": passed / count if count else 0.0,
    }


def apply_curve(course: Course, curve: float = 5.0) -> None:
    for student in course.all_students():
        for subject, grade in list(student.grades.items()):
            new_grade = min(100.0, grade + curve)
            student.grades[subject] = new_grade


def merge_remote_benchmarks(
    summary: Dict[str, Any], remote: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    if not remote:
        return summary
    merged = dict(summary)
    target = remote.get("target_average")
    if isinstance(target, (int, float)):
        merged["target_average"] = float(target)
        merged["gap_to_target"] = target - merged.get("class_avg", 0.0)
    return merged


def simulate_study(course: Course, days: int = 3) -> None:
    day = 0
    subjects = ["math", "science", "history"]
    while day < days:
        for student in course.all_students():
            subject = random.choice(subjects)
            increment = random.uniform(0.0, 3.0)
            current = student.grades.get(subject, 0.0)
            student.grades[subject] = min(100.0, current + increment)
        day += 1


def main(data_dir: str = "data", base_url: str = "") -> int:
    base = Path(data_dir)
    course_path = base / "course.json"
    summary_path = base / "summary.json"

    course = load_course(course_path)
    simulate_study(course, days=2)
    apply_curve(course, curve=2.5)

    summary = summarize_course(course)

    client = AnalyticsClient(base_url=base_url) if base_url else None
    if client:
        remote = client.fetch_benchmarks(course.course_id)
        summary = merge_remote_benchmarks(summary, remote)
        ok = client.push_summary(course.course_id, summary)
        if not ok:
            save_course(course_path, course)
            return 1
    save_course(course_path, course)
    try:
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    except OSError:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
