"""Tests for the Project taxonomy models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from master_plan.models import (
    DependencyScope,
    Language,
    Package,
    PackageEcosystem,
    Project,
)


def _minimal_project(**overrides: object) -> Project:
    payload: dict[str, object] = {
        "name": "master-plan-painel",
        "color_id": 42,
        "domain": "developer-tooling",
        "purpose": "Catalogue and track codebases.",
        "languages": [Language.PYTHON],
    }
    payload.update(overrides)
    return Project(**payload)


class TestPackage:
    def test_defaults(self) -> None:
        pkg = Package(name="pydantic")
        assert pkg.ecosystem is PackageEcosystem.PYPI
        assert pkg.scope is DependencyScope.RUNTIME
        assert pkg.version is None
        assert pkg.extras == []

    def test_name_is_required(self) -> None:
        with pytest.raises(ValidationError):
            Package(name="")

    def test_extras_are_stripped_and_deduped(self) -> None:
        pkg = Package(name="pydantic", extras=[" email ", "email", "", "dotenv"])
        assert pkg.extras == ["email", "dotenv"]

    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Package(name="pydantic", licence="MIT")  # type: ignore[call-arg]

    def test_key_is_case_insensitive_on_name(self) -> None:
        assert Package(name="Pydantic").key == (PackageEcosystem.PYPI, "pydantic")


class TestProject:
    def test_minimal_valid_project(self) -> None:
        project = _minimal_project()
        assert project.name == "master-plan-painel"
        assert project.color_id == 42
        assert project.sub_domain is None
        assert project.packages == []

    def test_color_id_is_required(self) -> None:
        with pytest.raises(ValidationError):
            Project(
                name="x", domain="d", purpose="p", languages=[Language.PYTHON]
            )

    @pytest.mark.parametrize("color_id", [1, 128, 256])
    def test_color_id_accepts_in_range(self, color_id: int) -> None:
        assert _minimal_project(color_id=color_id).color_id == color_id

    @pytest.mark.parametrize("color_id", [0, -1, 257, 1024])
    def test_color_id_rejects_out_of_range(self, color_id: int) -> None:
        with pytest.raises(ValidationError):
            _minimal_project(color_id=color_id)

    def test_primary_language_defaults_to_first(self) -> None:
        project = _minimal_project(languages=[Language.PYTHON, Language.SQL])
        assert project.primary_language is Language.PYTHON

    def test_primary_language_must_be_in_languages(self) -> None:
        with pytest.raises(ValidationError, match="primary_language"):
            _minimal_project(
                languages=[Language.PYTHON],
                primary_language=Language.RUST,
            )

    def test_languages_cannot_be_empty(self) -> None:
        with pytest.raises(ValidationError):
            _minimal_project(languages=[])

    def test_languages_are_deduped_preserving_order(self) -> None:
        project = _minimal_project(
            languages=[Language.PYTHON, Language.SQL, Language.PYTHON],
        )
        assert project.languages == [Language.PYTHON, Language.SQL]

    def test_whitespace_is_stripped(self) -> None:
        project = _minimal_project(name="  spaced  ")
        assert project.name == "spaced"

    def test_string_language_is_coerced_to_enum(self) -> None:
        project = _minimal_project(languages=["python", "typescript"])
        assert project.languages == [Language.PYTHON, Language.TYPESCRIPT]

    def test_duplicate_packages_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate package"):
            _minimal_project(
                packages=[Package(name="pydantic"), Package(name="Pydantic")],
            )

    def test_same_name_different_ecosystem_is_allowed(self) -> None:
        project = _minimal_project(
            packages=[
                Package(name="parser", ecosystem=PackageEcosystem.PYPI),
                Package(name="parser", ecosystem=PackageEcosystem.NPM),
            ],
        )
        assert len(project.packages) == 2

    def test_packages_in_filters_by_ecosystem(self) -> None:
        project = _minimal_project(
            packages=[
                Package(name="pydantic", ecosystem=PackageEcosystem.PYPI),
                Package(name="react", ecosystem=PackageEcosystem.NPM),
            ],
        )
        assert [p.name for p in project.packages_in(PackageEcosystem.NPM)] == ["react"]

    def test_runtime_packages_property(self) -> None:
        project = _minimal_project(
            packages=[
                Package(name="pydantic", scope=DependencyScope.RUNTIME),
                Package(name="pytest", scope=DependencyScope.TEST),
            ],
        )
        assert [p.name for p in project.runtime_packages] == ["pydantic"]

    def test_tags_are_stripped_and_deduped(self) -> None:
        project = _minimal_project(tags=[" cli ", "cli", "", "internal"])
        assert project.tags == ["cli", "internal"]

    def test_round_trips_through_json(self) -> None:
        project = _minimal_project(
            sub_domain="cataloguing",
            packages=[Package(name="pydantic", version="2.12.5")],
            tags=["internal"],
        )
        restored = Project.model_validate_json(project.model_dump_json())
        assert restored == project

    def test_assignment_is_validated(self) -> None:
        project = _minimal_project()
        with pytest.raises(ValidationError):
            project.name = ""
