import json
from pathlib import Path


EVAL_PATH = Path("evaluations/retrieval_eval.json")


def main():
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    ids = [case.get("id") for case in cases]

    is_valid = len(cases) == 18
    is_valid = is_valid and len(ids) == len(set(ids))

    print(f"Total evaluation cases: {len(cases)}")

    for case in cases:
        question = case.get("question")
        primary_section = case.get("primary_section")
        acceptable_sections = case.get("acceptable_sections")

        case_valid = isinstance(question, str) and bool(question.strip())
        case_valid = (
            case_valid
            and isinstance(primary_section, str)
            and bool(primary_section.strip())
            and isinstance(acceptable_sections, list)
            and bool(acceptable_sections)
            and all(
                isinstance(section, str) and bool(section.strip())
                for section in acceptable_sections
            )
            and primary_section in acceptable_sections
        )
        is_valid = is_valid and case_valid

        sections_text = ", ".join(acceptable_sections or [])
        print(f"ID: {case.get('id')}")
        print(f"Question: {question}")
        print(f"Primary section: {primary_section}")
        print(f"Acceptable section(s): {sections_text}")

    print(f"Final validation: {'PASS' if is_valid else 'FAIL'}")


if __name__ == "__main__":
    main()