from app.services.feature_registry_service import (
    FeatureRegistryService
)


class FeatureActivationService:

    def __init__(self):

        self.registry = (
            FeatureRegistryService()
        )

    def activate(
        self,
        feature_name: str
    ):

        feature_name = (
            feature_name
            .strip()
            .lower()
        )

        if not self.registry.feature_exists(
            feature_name
        ):
            return {
                "success": False,
                "message": f"Feature '{feature_name}' does not exist"
            }

        self.registry.enable(
            feature_name
        )

        feature = (
            self.registry.get_feature(
                feature_name
            )
        )

        return {
            "success": True,
            "action": "activate",
            "feature": feature_name,
            "status": "enabled",
            "metadata": feature
        }

    def deactivate(
        self,
        feature_name: str
    ):

        feature_name = (
            feature_name
            .strip()
            .lower()
        )

        if not self.registry.feature_exists(
            feature_name
        ):
            return {
                "success": False,
                "message": f"Feature '{feature_name}' does not exist"
            }

        if feature_name in {
            "memory",
            "voice_input"
        }:
            return {
                "success": False,
                "message": f"'{feature_name}' is a protected core feature"
            }

        self.registry.disable(
            feature_name
        )

        feature = (
            self.registry.get_feature(
                feature_name
            )
        )

        return {
            "success": True,
            "action": "deactivate",
            "feature": feature_name,
            "status": "disabled",
            "metadata": feature
        }

    def status(
        self,
        feature_name: str
    ):

        feature_name = (
            feature_name
            .strip()
            .lower()
        )

        if not self.registry.feature_exists(
            feature_name
        ):
            return {
                "success": False,
                "message": f"Feature '{feature_name}' does not exist"
            }

        return {
            "success": True,
            "feature": feature_name,
            "metadata": self.registry.get_feature(
                feature_name
            )
        }

    def list_features(
        self
    ):

        return {
            "success": True,
            "features": self.registry.get_all()
        }