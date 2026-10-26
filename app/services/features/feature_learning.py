from app.services.templates.template_store import (
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