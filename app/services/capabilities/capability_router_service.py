from app.services.features.feature_activation_service import (
    FeatureActivationService
)

from app.services.image.image_generation_service import (
    ImageGenerationService
)

from app.services.search.unified_search_service import (
    UnifiedSearchService
)


class CapabilityRouterService:

    def __init__(self):

        self.features = (
            FeatureActivationService()
        )

        self.images = (
            ImageGenerationService()
        )

        self.search = (
            UnifiedSearchService()
        )

    # ==========================
    # MAIN ROUTER
    # ==========================

    def execute(
        self,
        capability: str,
        payload: dict = None
    ):

        payload = payload or {}

        capability = (
            capability
            .strip()
            .lower()
        )

        # --------------------------
        # FEATURE ACTIVATION
        # --------------------------

        if capability == "activate_feature":

            return self.features.activate(

                payload.get(
                    "feature"
                )
            )

        if capability == "deactivate_feature":

            return self.features.deactivate(

                payload.get(
                    "feature"
                )
            )

        if capability == "feature_status":

            return self.features.status(

                payload.get(
                    "feature"
                )
            )

        if capability == "list_features":

            return self.features.list_features()

        # --------------------------
        # IMAGE GENERATION
        # --------------------------

        if capability == "generate_image":

            return self.images.generate(

                prompt=
                payload.get(
                    "prompt",
                    ""
                ),

                image_type=
                payload.get(
                    "image_type",
                    "image"
                )
            )

        # --------------------------
        # SEARCH
        # --------------------------

        if capability == "search":

            return self.search.search_all(

                payload.get(
                    "query",
                    ""
                )
            )

        # --------------------------
        # UNKNOWN
        # --------------------------

        return {

            "success":
            False,

            "message":
            f"Unknown capability: {capability}"
        }