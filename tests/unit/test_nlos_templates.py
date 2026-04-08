"""Unit tests for NLOS scene templates.

Tests verify that template classes produce valid Mitsuba scene dicts
without requiring mitsuba to be installed.
"""

from __future__ import annotations

import pytest


class TestNLOSSceneTemplateBase:
    """Tests for the NLOSSceneTemplate base class."""

    def test_default_spp(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            NLOSSceneTemplate,
        )

        template = NLOSSceneTemplate()
        assert template.spp == 256

    def test_default_variant(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            NLOSSceneTemplate,
        )

        template = NLOSSceneTemplate()
        assert template.variant == "llvm_ad_rgb"

    def test_frozen(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            NLOSSceneTemplate,
        )

        template = NLOSSceneTemplate()
        with pytest.raises(Exception):
            template.spp = 512  # type: ignore[misc]

    def test_build_returns_dict_with_required_keys(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            NLOSSceneTemplate,
        )

        scene = NLOSSceneTemplate().build()
        assert isinstance(scene, dict)
        assert "type" in scene
        assert "integrator" in scene
        assert "relay_wall" in scene

    def test_integrator_type(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            NLOSSceneTemplate,
        )

        scene = NLOSSceneTemplate().build()
        assert scene["integrator"]["type"] == "transient_nlos_path"

    def test_film_type(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            NLOSSceneTemplate,
        )

        scene = NLOSSceneTemplate().build()
        film = scene["relay_wall"]["sensor"]["film"]
        assert film["type"] == "transient_hdr_film"

    def test_film_temporal_bins(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            NLOSSceneTemplate,
        )

        template = NLOSSceneTemplate(temporal_bins=1024)
        scene = template.build()
        assert scene["relay_wall"]["sensor"]["film"]["temporal_bins"] == 1024

    def test_bin_width_opl_conversion(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            SPEED_OF_LIGHT,
            NLOSSceneTemplate,
        )

        template = NLOSSceneTemplate(temporal_resolution_ps=32.0)
        expected = 32.0 * 1e-12 * SPEED_OF_LIGHT
        assert abs(template.bin_width_opl - expected) < 1e-10

    def test_auto_start_opl_base_returns_zero(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            NLOSSceneTemplate,
        )

        template = NLOSSceneTemplate()
        assert template.auto_start_opl == 0.0

    def test_start_opl_uses_auto_when_none(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            NLOSSceneTemplate,
        )

        template = NLOSSceneTemplate(start_opl=None)
        scene = template.build()
        film = scene["relay_wall"]["sensor"]["film"]
        assert film["start_opl"] == 0.0

    def test_start_opl_uses_explicit_when_set(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            NLOSSceneTemplate,
        )

        template = NLOSSceneTemplate(start_opl=1.5)
        scene = template.build()
        film = scene["relay_wall"]["sensor"]["film"]
        assert film["start_opl"] == 1.5

    def test_speed_of_light_constant(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            SPEED_OF_LIGHT,
        )

        assert SPEED_OF_LIGHT == 299_792_458.0

    def test_spp_tiers_defined(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.base import (
            SPP_TIERS,
        )

        assert SPP_TIERS["draft"] == 64
        assert SPP_TIERS["low"] == 256
        assert SPP_TIERS["medium"] == 1024
        assert SPP_TIERS["high"] == 4096
        assert SPP_TIERS["ultra"] == 16384


class TestConfocalPointScene:
    """Tests for ConfocalPointScene template."""

    def test_default_scanning_mode(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.confocal_point import (
            ConfocalPointScene,
        )

        template = ConfocalPointScene()
        assert template.scanning_mode == "confocal"

    def test_build_has_hidden_sphere(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.confocal_point import (
            ConfocalPointScene,
        )

        scene = ConfocalPointScene(
            hidden_object_pos=(0.0, 1.0, 0.0),
        ).build()
        assert "hidden_sphere" in scene

    def test_hidden_sphere_structure(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.confocal_point import (
            ConfocalPointScene,
        )

        scene = ConfocalPointScene(
            hidden_object_pos=(0.0, 1.0, 0.0),
            hidden_object_radius=0.1,
        ).build()
        sphere = scene["hidden_sphere"]
        assert sphere["type"] == "sphere"
        assert sphere["center"] == [0.0, 1.0, 0.0]
        assert sphere["radius"] == 0.1

    def test_auto_start_opl_computes_from_geometry(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.confocal_point import (
            ConfocalPointScene,
        )

        template = ConfocalPointScene(
            hidden_object_pos=(0.0, 1.0, 0.0),
        )
        # auto_start_opl should be > 0 (computed from geometry)
        assert template.auto_start_opl > 0.0


class TestNonConfocalMeshScene:
    """Tests for NonConfocalMeshScene template."""

    def test_default_scanning_mode(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.nonconfocal_mesh import (
            NonConfocalMeshScene,
        )

        template = NonConfocalMeshScene(mesh_filename="test.obj")
        assert template.scanning_mode == "non-confocal"

    def test_build_has_hidden_mesh(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.nonconfocal_mesh import (
            NonConfocalMeshScene,
        )

        scene = NonConfocalMeshScene(mesh_filename="Z.obj").build()
        assert "hidden_mesh" in scene

    def test_mesh_type_obj(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.nonconfocal_mesh import (
            NonConfocalMeshScene,
        )

        scene = NonConfocalMeshScene(mesh_filename="Z.obj").build()
        assert scene["hidden_mesh"]["type"] == "obj"

    def test_mesh_type_ply(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.nonconfocal_mesh import (
            NonConfocalMeshScene,
        )

        scene = NonConfocalMeshScene(
            mesh_filename="Z.ply", mesh_format="ply"
        ).build()
        assert scene["hidden_mesh"]["type"] == "ply"


class TestRetroReflectiveScene:
    """Tests for RetroReflectiveScene template."""

    def test_build_has_corner_reflector(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.retroreflective import (
            RetroReflectiveScene,
        )

        scene = RetroReflectiveScene().build()
        # Corner reflector is two perpendicular rectangles
        assert "corner_horizontal" in scene
        assert "corner_vertical" in scene

    def test_corner_geometry_type(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates.retroreflective import (
            RetroReflectiveScene,
        )

        scene = RetroReflectiveScene().build()
        assert scene["corner_horizontal"]["type"] == "rectangle"
        assert scene["corner_vertical"]["type"] == "rectangle"


class TestTemplateRegistry:
    """Tests for __init__.py public API."""

    def test_get_template_confocal(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates import (
            ConfocalPointScene,
            get_template,
        )

        assert get_template("confocal_point") is ConfocalPointScene

    def test_get_template_nonconfocal(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates import (
            NonConfocalMeshScene,
            get_template,
        )

        assert get_template("nonconfocal_mesh") is NonConfocalMeshScene

    def test_get_template_retroreflective(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates import (
            RetroReflectiveScene,
            get_template,
        )

        assert get_template("retroreflective") is RetroReflectiveScene

    def test_get_template_unknown_raises(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates import (
            get_template,
        )

        with pytest.raises(KeyError):
            get_template("nonexistent")

    def test_list_templates(self) -> None:
        from agentsim.physics.domains.nlos_transient_imaging.templates import (
            list_templates,
        )

        names = list_templates()
        assert "confocal_point" in names
        assert "nonconfocal_mesh" in names
        assert "retroreflective" in names
