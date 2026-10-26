from app.services.identity.lumira_identity_service import (
    LumiraIdentityService
)

from app.services.features.feature_activation_service import (
    FeatureActivationService
)


class FeatureCommandRouter:
    """Route explicit feature lifecycle commands without masking failures."""

    def __init__(self):
        self.identity = LumiraIdentityService()
        self.activation = FeatureActivationService()

    def process(self, text: str):
        parsed = self.identity.parse(text)

        if not parsed.get("recognized"):
            return {
                "success": False,
                "type": "not_feature_command",
                "data": parsed,
            }

        command = parsed.get("command")
        target = parsed.get("target")

        if command == "activate":
            result = self.activation.activate(target)
        elif command == "disable":
            result = self.activation.deactivate(target)
        else:
            return {
                "success": False,
                "type": "feature_command",
                "message": "unsupported command",
                "parsed": parsed,
            }

        # A recognized request is not a successful operation. Preserve the
        # activation service's verdict so blocked dependencies or protected
        # core features cannot be reported as successful to the main brain.
        operation_succeeded = isinstance(result, dict) and result.get("success") is True
        return {
            "success": operation_succeeded,
            "type": "feature_command",
            "parsed": parsed,
            "result": result,
        }
