#core/generation/quality.py
from typing import Dict, Any, List


DANGEROUS_PATTERNS = [

    "users[username] = password",

    "password = password",

    "stored_password = password",

    "admin/admin",

    "TODO",

    "FIXME",

    "mock implementation",

    "placeholder",

    "hardcoded secret",

    "api_key =",

    "secret_key =",

    "token = \""
]


WEAK_FILE_PATTERNS = {

    "auth": [
        "main.py",
        "requirements.txt",
        "README.md"
    ],

    "api": [
        "main.py",
        "requirements.txt"
    ],

    "fastapi": [
        "main.py",
        "requirements.txt"
    ]
}


def collect_generated_code(
    code_output: Dict[str, Any]
) -> str:

    files = code_output.get(
        "files",
        {}
    )

    if not isinstance(
        files,
        dict
    ):
        return ""

    combined = []

    for content in files.values():

        combined.append(
            str(content)
        )

    return "\n".join(
        combined
    )


def find_dangerous_patterns(
    code_output: Dict[str, Any]
) -> List[str]:

    code = collect_generated_code(
        code_output
    )

    found = []

    lowered = code.lower()

    for pattern in DANGEROUS_PATTERNS:

        if pattern.lower() in lowered:

            found.append(
                pattern
            )

    return found


def validate_file_plan(
    code_output: Dict[str, Any]
) -> List[str]:

    problems = []

    target = str(
        code_output.get(
            "code_target",
            ""
        )
    ).lower()

    file_plan = code_output.get(
        "file_plan",
        []
    )

    if not isinstance(
        file_plan,
        list
    ):
        return [
            "invalid_file_plan"
        ]

    for keyword, expected in WEAK_FILE_PATTERNS.items():

        if keyword in target:

            missing = []

            for file in expected:

                if file not in file_plan:

                    missing.append(
                        file
                    )

            if missing:

                problems.append(
                    "missing_files:"
                    + ",".join(
                        missing
                    )
                )

    return problems


def validate_implementation_steps(
    code_output: Dict[str, Any]
) -> List[str]:

    problems = []

    steps = code_output.get(
        "implementation_steps",
        []
    )

    if not isinstance(
        steps,
        list
    ):
        return [
            "invalid_steps"
        ]

    if len(steps) < 2:

        problems.append(
            "too_few_steps"
        )

    generic = {

        "build app",
        "generate app",
        "create project"
    }

    for step in steps:

        lowered = str(
            step
        ).lower()

        if lowered in generic:

            problems.append(
                f"generic:{step}"
            )

    return problems


def validate_test_steps(
    code_output: Dict[str, Any]
) -> List[str]:

    tests = code_output.get(
        "test_steps",
        []
    )

    if not isinstance(
        tests,
        list
    ):
        return [
            "invalid_test_steps"
        ]

    if len(tests) == 0:

        return [
            "missing_tests"
        ]

    return []


def analyze_code_quality(
    code_output: Dict[str, Any]
) -> Dict[str, Any]:

    issues = []

    issues.extend(
        find_dangerous_patterns(
            code_output
        )
    )

    issues.extend(
        validate_file_plan(
            code_output
        )
    )

    issues.extend(
        validate_implementation_steps(
            code_output
        )
    )

    issues.extend(
        validate_test_steps(
            code_output
        )
    )

    return {

        "passed":
        len(issues) == 0,

        "issues":
        issues
    }