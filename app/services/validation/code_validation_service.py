class CodeValidationService:

    def validate(
        self,
        files: dict
    ):

        errors = []

        required_files = [

            "main.py",
            "requirements.txt"
        ]

        for file_name in required_files:

            if file_name not in files:

                errors.append(
                    f"{file_name} missing"
                )

        for (
            file_name,
            content
        ) in files.items():

            if not content.strip():

                errors.append(
                    f"{file_name} is empty"
                )

        if "main.py" in files:

            try:

                compile(

                    files[
                        "main.py"
                    ],

                    "main.py",

                    "exec"
                )

            except Exception as e:

                errors.append(
                    str(e)
                )

        return {

            "success":
            len(errors) == 0,

            "valid":
            len(errors) == 0,

            "errors":
            errors
        }