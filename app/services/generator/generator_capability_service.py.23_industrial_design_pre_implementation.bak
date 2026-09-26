import json
"""
Deterministic Generator capability service.
"""

from typing import Any, Dict


class GeneratorCapabilityService:

    def image_generation(self, request):
        if not isinstance(request, str):
            request = ""

        request = request.strip()

        if not request:
            return {"success": False, "capability": "image_generation", "status": "reject", "error": "request is required"}

        words = [word.strip(".,!?;:()[]{}").lower() for word in request.split()]
        words = [word for word in words if word]

        stop_words = {"a", "an", "the", "for", "to", "of", "and", "with", "my", "simple", "image", "picture", "photo", "generate", "generation", "create", "draw", "show", "make"}
        concepts = []

        for word in words:
            if word not in stop_words and word not in concepts:
                concepts.append(word)

        if not concepts:
            concepts = ["scene"]

        subject = concepts[0]

        image = {
            "type": "generated_image",
            "version": "1.0",
            "request": request,
            "status": "generated",
            "subject": subject,
            "format": "structured_image_spec",
            "composition": {
                "layout": "centered_subject",
                "orientation": "landscape",
                "framing": "medium",
            },
            "visual_elements": [
                {"id": "element_1", "name": subject, "role": "primary_subject"},
                {"id": "element_2", "name": "background", "role": "environment"},
                {"id": "element_3", "name": "lighting", "role": "illumination"},
            ],
            "rendering": {
                "style": "clean_digital",
                "detail": "high",
                "lighting": "balanced",
            },
        }

        try:
            import json
            from app.services.artifacts.artifact_manager_service import ArtifactManagerService

            artifact = ArtifactManagerService().create_artifact(
                artifact_type="images",
                content=json.dumps(image, indent=2),
                source="image_generation",
                extension="json",
            )
        except Exception as exc:
            return {"success": False, "capability": "image_generation", "status": "reject", "request": request, "image": image, "error": str(exc)}

        return {
            "success": True,
            "capability": "image_generation",
            "status": "accept",
            "request": request,
            "image": image,
            "artifact": artifact,
        }
    def schematic_generation(self, request):
        if not isinstance(request, str):
            request = ''

        request = request.strip()

        if not request:
            return {
                'success': False,
                'capability': 'schematic_generation',
                'status': 'reject',
                'error': 'request is required',
            }

        words = [
            word.strip('.,!?;:()[]{}')
            for word in request.split()
        ]
        words = [word for word in words if word]

        stop_words = {
            'a', 'an', 'the', 'for', 'to', 'of', 'and', 'with',
            'my', 'simple', 'schematic', 'generate', 'generation',
            'create', 'draw', 'show', 'make', 'circuit',
        }

        concepts = []

        for word in words:
            normalized = word.lower()
            if normalized not in stop_words and normalized not in concepts:
                concepts.append(normalized)

        if not concepts:
            concepts = ['circuit']

        components = [{
            'id': 'component_1',
            'name': concepts[0],
            'type': 'primary',
            'value': None,
        }]

        for index, concept in enumerate(concepts[1:6], start=2):
            components.append({
                'id': f'component_{index}',
                'name': concept,
                'type': 'component',
                'value': None,
            })

        connections = [{
            'from': 'component_1',
            'to': f'component_{index}',
            'signal': 'connection',
        } for index in range(2, len(components) + 1)]

        schematic = {
            'type': 'schematic',
            'version': '1.0',
            'request': request,
            'status': 'generated',
            'format': 'structured',
            'components': components,
            'connections': connections,
            'component_count': len(components),
            'connection_count': len(connections),
        }

        try:
            import json
            from app.services.artifacts.artifact_manager_service import ArtifactManagerService
            artifact = ArtifactManagerService().create_artifact(
                artifact_type='schematics',
                content=json.dumps(schematic, indent=2),
                source='schematic_generation',
                extension='json',
            )
        except Exception as exc:
            return {
                'success': False,
                'capability': 'schematic_generation',
                'status': 'reject',
                'request': request,
                'schematic': schematic,
                'error': str(exc),
            }

        return {
            'success': True,
            'capability': 'schematic_generation',
            'status': 'accept',
            'request': request,
            'schematic': schematic,
            'artifact': artifact,
        }

    def diagram_generation(self, request):
        if not isinstance(request, str):
            request = ""

        request = request.strip()

        if not request:
            return {
                "success": False,
                "capability": "diagram_generation",
                "status": "reject",
                "error": "request is required",
            }

        words = [
            word.strip(".,!?;:()[]{}")
            for word in request.split()
        ]

        words = [
            word
            for word in words
            if word
        ]

        if not words:
            return {
                "success": False,
                "capability": "diagram_generation",
                "status": "reject",
                "error": "request is required",
            }

        # Deterministic concept extraction.
        #
        # The first meaningful token becomes the subject.
        # Remaining unique meaningful tokens become supporting
        # concepts. This is intentionally deterministic and does
        # not claim semantic understanding beyond the request.
        stop_words = {
            "a",
            "an",
            "the",
            "for",
            "to",
            "of",
            "and",
            "with",
            "my",
            "simple",
            "diagram",
            "generate",
            "generation",
            "create",
            "draw",
            "show",
            "make",
        }

        concepts = []

        for word in words:
            normalized = word.lower()

            if normalized in stop_words:
                continue

            if normalized not in concepts:
                concepts.append(normalized)

        if not concepts:
            concepts = ["request"]

        subject = concepts[0]

        supporting = concepts[1:5]

        nodes = [
            {
                "id": "node_1",
                "label": subject,
                "type": "primary",
            }
        ]

        for index, concept in enumerate(
            supporting,
            start=2,
        ):
            nodes.append(
                {
                    "id": f"node_{index}",
                    "label": concept,
                    "type": "component",
                }
            )

        edges = []

        for index in range(
            2,
            len(nodes) + 1,
        ):
            edges.append(
                {
                    "source": "node_1",
                    "target": f"node_{index}",
                    "relation": "contains",
                }
            )

        diagram = {
            "type": "diagram",
            "version": "1.0",
            "request": request,
            "status": "generated",
            "layout": "hierarchical",
            "direction": "top_down",
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

        artifact = None

        try:
            from app.services.artifacts.artifact_manager_service import (
                ArtifactManagerService,
            )

            artifact_manager = ArtifactManagerService()

            artifact = artifact_manager.create_artifact(
                artifact_type="diagrams",
                content=json.dumps(
                    diagram,
                    indent=2,
                ),
                source="diagram_generation",
                extension="json",
            )

        except Exception as exc:
            return {
                "success": False,
                "capability": "diagram_generation",
                "status": "reject",
                "request": request,
                "diagram": diagram,
                "error": str(exc),
            }

        return {
            "success": True,
            "capability": "diagram_generation",
            "status": "accept",
            "request": request,
            "diagram": diagram,
            "artifact": artifact,
        }

    def architecture_diagrams(self, request):
        if not isinstance(request, str):
            request = ""

        request = request.strip()

        if not request:
            return {"success": False, "capability": "architecture_diagrams", "status": "reject", "error": "request is required"}

        words = [word.strip(".,!?;:()[]{}").lower() for word in request.split()]
        words = [word for word in words if word]

        stop_words = {"a", "an", "the", "for", "to", "of", "and", "with", "my", "simple", "architecture", "architectural", "diagram", "diagrams", "generate", "generation", "create", "draw", "show", "make", "design", "system"}
        concepts = []

        for word in words:
            if word not in stop_words and word not in concepts:
                concepts.append(word)

        if not concepts:
            concepts = ["application"]

        subject = concepts[0]
        supporting = concepts[1:5]

        layers = [
            {"id": "layer_1", "name": "presentation", "order": 1},
            {"id": "layer_2", "name": "application", "order": 2},
            {"id": "layer_3", "name": "data", "order": 3},
        ]

        components = [{"id": "component_1", "name": subject, "layer": "application", "type": "primary"}]

        for index, concept in enumerate(supporting, start=2):
            layer = "presentation" if index % 3 == 2 else "data" if index % 3 == 0 else "application"
            components.append({"id": f"component_{index}", "name": concept, "layer": layer, "type": "service"})

        connections = []

        for index in range(2, len(components) + 1):
            connections.append({"from": "component_1", "to": f"component_{index}", "relation": "depends_on"})

        architecture = {
            "type": "architecture_diagram",
            "version": "1.0",
            "request": request,
            "status": "generated",
            "layout": "layered",
            "direction": "top_down",
            "subject": subject,
            "layers": layers,
            "components": components,
            "connections": connections,
            "layer_count": len(layers),
            "component_count": len(components),
            "connection_count": len(connections),
        }

        try:
            import json
            from app.services.artifacts.artifact_manager_service import ArtifactManagerService

            artifact = ArtifactManagerService().create_artifact(
                artifact_type="diagrams",
                content=json.dumps(architecture, indent=2),
                source="architecture_diagrams",
                extension="json",
            )
        except Exception as exc:
            return {"success": False, "capability": "architecture_diagrams", "status": "reject", "request": request, "architecture": architecture, "error": str(exc)}

        return {
            "success": True,
            "capability": "architecture_diagrams",
            "status": "accept",
            "request": request,
            "architecture": architecture,
            "artifact": artifact,
        }

    def flowcharts(self, request):
        if not isinstance(request, str):
            request = ""

        request = request.strip()

        if not request:
            return {"success": False, "capability": "flowcharts", "status": "reject", "error": "request is required"}

        words = [word.strip(".,!?;:()[]{}").lower() for word in request.split()]
        words = [word for word in words if word]

        stop_words = {"a", "an", "the", "for", "to", "of", "and", "with", "my", "simple", "flowchart", "flowcharts", "generate", "generation", "create", "draw", "show", "make", "process", "workflow"}
        concepts = []

        for word in words:
            if word not in stop_words and word not in concepts:
                concepts.append(word)

        if not concepts:
            concepts = ["process"]

        subject = concepts[0]
        supporting = concepts[1:6]

        nodes = [
            {
                "id": "node_1",
                "label": "Start",
                "type": "start",
            },
            {
                "id": "node_2",
                "label": subject,
                "type": "process",
            },
        ]

        for index, concept in enumerate(supporting, start=3):
            nodes.append({
                "id": f"node_{index}",
                "label": concept,
                "type": "process",
            })

        end_id = len(nodes) + 1
        nodes.append({
            "id": f"node_{end_id}",
            "label": "End",
            "type": "end",
        })

        edges = []

        for index in range(1, len(nodes)):
            edges.append({
                "source": f"node_{index}",
                "target": f"node_{index + 1}",
                "relation": "next",
            })

        flowchart = {
            "type": "flowchart",
            "version": "1.0",
            "request": request,
            "status": "generated",
            "layout": "linear",
            "direction": "top_down",
            "subject": subject,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

        try:
            import json
            from app.services.artifacts.artifact_manager_service import ArtifactManagerService

            artifact = ArtifactManagerService().create_artifact(
                artifact_type="diagrams",
                content=json.dumps(flowchart, indent=2),
                source="flowcharts",
                extension="json",
            )
        except Exception as exc:
            return {"success": False, "capability": "flowcharts", "status": "reject", "request": request, "flowchart": flowchart, "error": str(exc)}

        return {
            "success": True,
            "capability": "flowcharts",
            "status": "accept",
            "request": request,
            "flowchart": flowchart,
            "artifact": artifact,
        }
    def ui_design(self, request):
        if not isinstance(request, str):
            request = ""

        request = request.strip()

        if not request:
            return {"success": False, "capability": "ui_design", "status": "reject", "error": "request is required"}

        words = [word.strip(".,!?;:()[]{}").lower() for word in request.split()]
        words = [word for word in words if word]

        stop_words = {"a", "an", "the", "for", "to", "of", "and", "with", "my", "simple", "ui", "user", "interface", "design", "generate", "generation", "create", "draw", "show", "make"}
        concepts = []

        for word in words:
            if word not in stop_words and word not in concepts:
                concepts.append(word)

        if not concepts:
            concepts = ["application"]

        subject = concepts[0]

        screens = [
            {"id": "screen_1", "name": "home", "purpose": "primary user entry point"},
            {"id": "screen_2", "name": "details", "purpose": "view and manage primary content"},
            {"id": "screen_3", "name": "settings", "purpose": "configure application behavior"},
        ]

        components = [
            {"id": "component_1", "name": "header", "type": "navigation"},
            {"id": "component_2", "name": "content", "type": "primary_content"},
            {"id": "component_3", "name": "action_button", "type": "interaction"},
            {"id": "component_4", "name": "footer", "type": "navigation"},
        ]

        interactions = [
            {"from": "screen_1", "to": "screen_2", "action": "open_details"},
            {"from": "screen_2", "to": "screen_1", "action": "back"},
            {"from": "screen_1", "to": "screen_3", "action": "open_settings"},
        ]

        design = {
            "type": "ui_design",
            "version": "1.0",
            "request": request,
            "status": "generated",
            "subject": subject,
            "layout": "responsive",
            "navigation": "top_navigation",
            "screens": screens,
            "components": components,
            "interactions": interactions,
            "screen_count": len(screens),
            "component_count": len(components),
            "interaction_count": len(interactions),
        }

        try:
            import json
            from app.services.artifacts.artifact_manager_service import ArtifactManagerService

            artifact = ArtifactManagerService().create_artifact(
                artifact_type="diagrams",
                content=json.dumps(design, indent=2),
                source="ui_design",
                extension="json",
            )
        except Exception as exc:
            return {"success": False, "capability": "ui_design", "status": "reject", "request": request, "design": design, "error": str(exc)}

        return {
            "success": True,
            "capability": "ui_design",
            "status": "accept",
            "request": request,
            "design": design,
            "artifact": artifact,
        }
    def product_concepts(self, request):
        if not isinstance(request, str):
            request = ""

        request = request.strip()

        if not request:
            return {"success": False, "capability": "product_concepts", "status": "reject", "error": "request is required"}

        words = [word.strip(".,!?;:()[]{}").lower() for word in request.split()]
        words = [word for word in words if word]

        stop_words = {"a", "an", "the", "for", "to", "of", "and", "with", "my", "simple", "product", "concept", "concepts", "generate", "generation", "create", "make", "design", "idea", "ideas"}
        concepts = []

        for word in words:
            if word not in stop_words and word not in concepts:
                concepts.append(word)

        if not concepts:
            concepts = ["product"]

        subject = concepts[0]

        concept = {
            "id": "concept_1",
            "name": subject,
            "problem": f"Users need a practical solution related to {subject}",
            "solution": f"A focused product designed around {subject}",
            "target_users": ["general_users"],
            "core_features": [
                f"{subject}_management",
                "user_interaction",
                "progress_tracking",
            ],
            "value_proposition": f"Simplifies and organizes {subject}",
        }

        product = {
            "type": "product_concept",
            "version": "1.0",
            "request": request,
            "status": "generated",
            "subject": subject,
            "concepts": [concept],
            "concept_count": 1,
            "development_stages": [
                "problem_definition",
                "solution_design",
                "prototype",
                "validation",
                "launch",
            ],
        }

        try:
            import json
            from app.services.artifacts.artifact_manager_service import ArtifactManagerService

            artifact = ArtifactManagerService().create_artifact(
                artifact_type="blueprints",
                content=json.dumps(product, indent=2),
                source="product_concepts",
                extension="json",
            )
        except Exception as exc:
            return {"success": False, "capability": "product_concepts", "status": "reject", "request": request, "product": product, "error": str(exc)}

        return {
            "success": True,
            "capability": "product_concepts",
            "status": "accept",
            "request": request,
            "product": product,
            "artifact": artifact,
        }
    def industrial_design(self, request):
        if not isinstance(request, str):
            request = ""

        request = request.strip()

        if not request:
            return {"success": False, "capability": "industrial_design", "status": "reject", "error": "request is required"}

        words = [word.strip(".,!?;:()[]{}").lower() for word in request.split()]
        words = [word for word in words if word]

        stop_words = {"a", "an", "the", "for", "to", "of", "and", "with", "my", "simple", "industrial", "design", "product", "generate", "generation", "create", "make", "design", "concept"}
        concepts = []

        for word in words:
            if word not in stop_words and word not in concepts:
                concepts.append(word)

        if not concepts:
            concepts = ["product"]

        subject = concepts[0]

        form = {
            "style": "functional_modern",
            "geometry": "compact_enclosure",
            "ergonomics": "hand_operable",
            "surface": "smooth_protective",
        }

        materials = [
            {"name": "enclosure", "material": "engineering_plastic", "purpose": "protective_body"},
            {"name": "frame", "material": "aluminum", "purpose": "structural_support"},
            {"name": "fasteners", "material": "steel", "purpose": "assembly"},
        ]

        components = [
            {"id": "part_1", "name": subject, "role": "primary_product_body"},
            {"id": "part_2", "name": "control_interface", "role": "user_interaction"},
            {"id": "part_3", "name": "power_module", "role": "power_management"},
            {"id": "part_4", "name": "mounting_structure", "role": "mechanical_support"},
        ]

        manufacturing = [
            "concept_modeling",
            "prototype_fabrication",
            "assembly_validation",
            "production_preparation",
        ]

        design = {
            "type": "industrial_design",
            "version": "1.0",
            "request": request,
            "status": "generated",
            "subject": subject,
            "form": form,
            "materials": materials,
            "components": components,
            "manufacturing_stages": manufacturing,
            "material_count": len(materials),
            "component_count": len(components),
            "manufacturing_stage_count": len(manufacturing),
        }

        try:
            import json
            from app.services.artifacts.artifact_manager_service import ArtifactManagerService

            artifact = ArtifactManagerService().create_artifact(
                artifact_type="blueprints",
                content=json.dumps(design, indent=2),
                source="industrial_design",
                extension="json",
            )
        except Exception as exc:
            return {"success": False, "capability": "industrial_design", "status": "reject", "request": request, "design": design, "error": str(exc)}

        return {
            "success": True,
            "capability": "industrial_design",
            "status": "accept",
            "request": request,
            "design": design,
            "artifact": artifact,
        }
    def _result(capability, request, objective):
        return {
            "success": True,
            "capability": capability,
            "request": request.strip() if isinstance(request, str) else "",
            "objective": objective,
            "steps": [
                "define generation objective",
                "define requirements",
                "define structural constraints",
                "generate concept",
                "verify requirements",
                "prepare artifact output",
            ],
            "status": "accept",
        }


