from app.services.lumira_identity_service import (
    LumiraIdentityService
)

from app.services.feature_activation_service import (
    FeatureActivationService
)


class FeatureCommandRouter:

    def __init__(self):

        self.identity = (
            LumiraIdentityService()
        )

        self.activation = (
            FeatureActivationService()
        )

    def process(
        self,
        text: str
    ):

        parsed = (
            self.identity.parse(
                text
            )
        )

        if not parsed.get(
            "recognized"
        ):
            return {
                "success": False,
                "type": "not_feature_command",
                "data": parsed
            }

        command = parsed[
            "command"
        ]

        target = parsed[
            "target"
        ]

        if command == "activate":

            result = (
                self.activation.activate(
                    target
                )
            )

        elif command == "disable":

            result = (
                self.activation.deactivate(
                    target
                )
            )

        else:

            return {
                "success": False,
                "message": "unsupported command"
            }

        return {
            "success": True,
            "type": "feature_command",
            "parsed": parsed,
            "result": result
        }