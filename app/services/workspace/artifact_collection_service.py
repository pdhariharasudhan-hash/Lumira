from pathlib import Path
import json


class ArtifactCollectionService:

    def __init__(self):

        self.collection_file = Path(
            "memory/artifact_collections.json"
        )

        self.collection_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if not self.collection_file.exists():

            self._write(
                {}
            )

    def _read(self):

        content = (
            self.collection_file
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

        if not content:

            return {}

        return json.loads(
            content
        )

    def _write(
        self,
        data
    ):

        self.collection_file.write_text(
            json.dumps(
                data,
                indent=2
            ),
            encoding="utf-8"
        )

    def create_collection(
        self,
        name: str
    ):

        collections = (
            self._read()
        )

        if name in collections:

            return {

                "success":
                False,

                "message":
                "collection already exists"
            }

        collections[
            name
        ] = {

            "artifacts":
            []
        }

        self._write(
            collections
        )

        return {

            "success":
            True,

            "collection":
            name
        }

    def add_artifact(
        self,
        collection_name: str,
        artifact_id: str
    ):

        collections = (
            self._read()
        )

        if collection_name not in collections:

            return {

                "success":
                False,

                "message":
                "collection not found"
            }

        artifacts = (
            collections[
                collection_name
            ][
                "artifacts"
            ]
        )

        if artifact_id not in artifacts:

            artifacts.append(
                artifact_id
            )

        self._write(
            collections
        )

        return {

            "success":
            True
        }

    def remove_artifact(
        self,
        collection_name: str,
        artifact_id: str
    ):

        collections = (
            self._read()
        )

        if collection_name not in collections:

            return {

                "success":
                False,

                "message":
                "collection not found"
            }

        artifacts = (
            collections[
                collection_name
            ][
                "artifacts"
            ]
        )

        if artifact_id in artifacts:

            artifacts.remove(
                artifact_id
            )

        self._write(
            collections
        )

        return {

            "success":
            True
        }

    def list_collection(
        self,
        collection_name: str
    ):

        collections = (
            self._read()
        )

        if collection_name not in collections:

            return {

                "success":
                False,

                "message":
                "collection not found"
            }

        return {

            "success":
            True,

            "name":
            collection_name,

            "artifacts":
            collections[
                collection_name
            ][
                "artifacts"
            ]
        }

    def list_collections(
        self
    ):

        collections = (
            self._read()
        )

        return {

            "success":
            True,

            "count":
            len(
                collections
            ),

            "collections":
            list(
                collections.keys()
            )
        }

    def delete_collection(
        self,
        collection_name: str
    ):

        collections = (
            self._read()
        )

        if collection_name not in collections:

            return {

                "success":
                False,

                "message":
                "collection not found"
            }

        del collections[
            collection_name
        ]

        self._write(
            collections
        )

        return {

            "success":
            True
        }