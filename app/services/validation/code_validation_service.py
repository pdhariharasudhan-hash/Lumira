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

            main_content = (
                files[
                    "main.py"
                ]
            )

            try:

                compile(
                    main_content,
                    "main.py",
                    "exec"
                )

            except Exception as e:

                errors.append(
                    str(e)
                )

            if (
                "from fastapi import FastAPI"
                not in main_content
            ):

                errors.append(
                    "fastapi import missing"
                )

            if (
                "app = FastAPI()"
                not in main_content
            ):

                errors.append(
                    "FastAPI app instance missing"
                )

            if (
                "@app.get("
                not in main_content
            ):

                errors.append(
                    "GET route missing"
                )

            if (
                "@app.post("
                not in main_content
            ):

                errors.append(
                    "POST route missing"
                )

            if (
                "@app.put("
                not in main_content
            ):

                errors.append(
                    "PUT route missing"
                )

            if (
                "@app.delete("
                not in main_content
            ):

                errors.append(
                    "DELETE route missing"
                )

        return {

            "success":
            len(errors) == 0,

            "valid":
            len(errors) == 0,

            "errors":
            errors
        }