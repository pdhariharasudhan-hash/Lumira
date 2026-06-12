from app.services.template_store import (
    TemplateStore
)


class FeatureLearning:


    def learn(
        self,
        feature:str,
        route:str
    ):

        TemplateStore().save(

            feature,

            route
        )


        return {

            "success":
            True
        }