"""Pydantic models describing a tracked project (codebase).

A :class:`Project` captures the taxonomy of a single codebase: the business
``domain`` and ``sub_domain`` it serves, its human-readable ``purpose``, the
programming ``languages`` it is written in, and the third-party ``packages`` it
depends on.

All models target Pydantic v2.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "Language",
    "PackageEcosystem",
    "DependencyScope",
    "Package",
    "Project",
    "COLOR_ID_MIN",
    "COLOR_ID_MAX",
]

# Inclusive bounds for a project's display color id. The upper bound is the
# frontend palette size: each id maps 1:1 to a distinct precomputed color, so
# the catalogue holds at most COLOR_ID_MAX projects, each visibly separable.
COLOR_ID_MIN = 1
COLOR_ID_MAX = 256


class Language(str, Enum):
    """Programming languages a codebase may be written in.

    ``OTHER`` is the explicit escape hatch: prefer it over silently coercing an
    unrecognized language, so that gaps are visible rather than hidden.
    """

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    KOTLIN = "kotlin"
    SWIFT = "swift"
    C = "c"
    CPP = "cpp"
    CSHARP = "csharp"
    RUBY = "ruby"
    PHP = "php"
    SCALA = "scala"
    ELIXIR = "elixir"
    HASKELL = "haskell"
    LUA = "lua"
    R = "r"
    JULIA = "julia"
    SHELL = "shell"
    SQL = "sql"
    HTML = "html"
    CSS = "css"
    OTHER = "other"


class PackageEcosystem(str, Enum):
    """Dependency ecosystems / registries a package can be resolved from."""

    PYPI = "pypi"
    NPM = "npm"
    CARGO = "cargo"
    GO_MODULES = "go_modules"
    MAVEN = "maven"
    NUGET = "nuget"
    RUBYGEMS = "rubygems"
    PACKAGIST = "packagist"
    HEX = "hex"
    HACKAGE = "hackage"
    SYSTEM = "system"
    OTHER = "other"


class DependencyScope(str, Enum):
    """Why a package is present in the project."""

    RUNTIME = "runtime"
    DEV = "dev"
    TEST = "test"
    BUILD = "build"
    OPTIONAL = "optional"


class Package(BaseModel):
    """A single third-party dependency of a project."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    name: str = Field(..., min_length=1, description="Package identifier, e.g. 'pydantic'.")
    ecosystem: PackageEcosystem = Field(
        default=PackageEcosystem.PYPI,
        description="Registry the package is resolved from.",
    )
    version: str | None = Field(
        default=None,
        description="Pinned version or version constraint, e.g. '2.12.5' or '>=2,<3'.",
    )
    scope: DependencyScope = Field(
        default=DependencyScope.RUNTIME,
        description="Dependency scope (runtime, dev, test, ...).",
    )
    extras: list[str] = Field(
        default_factory=list,
        description="Optional feature extras enabled, e.g. ['email'] for 'pydantic[email]'.",
    )

    @field_validator("extras")
    @classmethod
    def _dedupe_extras(cls, value: list[str]) -> list[str]:
        """Strip, drop empties, and de-duplicate extras while preserving order."""
        seen: set[str] = set()
        result: list[str] = []
        for extra in value:
            cleaned = extra.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result

    @property
    def key(self) -> tuple[PackageEcosystem, str]:
        """Identity of the package within a project (ecosystem + name)."""
        return (self.ecosystem, self.name.lower())


class Project(BaseModel):
    """Taxonomy of a single tracked codebase.

    Tracks the four axes the operator cares about — ``domain``/``sub_domain``,
    ``purpose``, ``languages``, and ``packages`` — plus light identifying
    metadata.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    name: str = Field(..., min_length=1, description="Human-readable project name.")
    color_id: int = Field(
        ...,
        ge=COLOR_ID_MIN,
        le=COLOR_ID_MAX,
        description=(
            "Unique display color id, an integer in [1, 256], indexing the "
            "fixed frontend palette. No two projects may share the same value; "
            "uniqueness is enforced by the repository, range by this field."
        ),
    )
    domain: str = Field(..., min_length=1, description="Top-level business/technical domain.")
    sub_domain: str | None = Field(
        default=None,
        description="Narrower area within the domain.",
    )
    purpose: str = Field(..., min_length=1, description="What the codebase exists to do.")

    languages: list[Language] = Field(
        ...,
        min_length=1,
        description="Programming languages the codebase uses (at least one).",
    )
    primary_language: Language | None = Field(
        default=None,
        description="Dominant language; defaults to the first entry in `languages`.",
    )

    packages: list[Package] = Field(
        default_factory=list,
        description="Third-party dependencies of the project.",
    )

    repository: str | None = Field(
        default=None,
        description="Repository URL or local path.",
    )
    description: str | None = Field(
        default=None,
        description="Longer free-form description.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form labels for filtering/grouping.",
    )

    @field_validator("languages")
    @classmethod
    def _dedupe_languages(cls, value: list[Language]) -> list[Language]:
        """De-duplicate languages while preserving declared order."""
        seen: set[Language] = set()
        result: list[Language] = []
        for language in value:
            if language not in seen:
                seen.add(language)
                result.append(language)
        return result

    @field_validator("tags")
    @classmethod
    def _dedupe_tags(cls, value: list[str]) -> list[str]:
        """Strip, drop empties, and de-duplicate tags while preserving order."""
        seen: set[str] = set()
        result: list[str] = []
        for tag in value:
            cleaned = tag.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result

    @model_validator(mode="after")
    def _resolve_primary_language(self) -> Project:
        """Default `primary_language` to the first language; enforce membership."""
        if self.primary_language is None:
            # Bypass validate_assignment re-entry by setting on __dict__.
            object.__setattr__(self, "primary_language", self.languages[0])
        elif self.primary_language not in self.languages:
            raise ValueError(
                f"primary_language {self.primary_language.value!r} "
                f"is not among languages {[lang.value for lang in self.languages]}"
            )
        return self

    @model_validator(mode="after")
    def _reject_duplicate_packages(self) -> Project:
        """Fail on two packages sharing the same (ecosystem, name) identity."""
        seen: set[tuple[PackageEcosystem, str]] = set()
        for package in self.packages:
            if package.key in seen:
                raise ValueError(
                    f"duplicate package {package.name!r} in ecosystem "
                    f"{package.ecosystem.value!r}"
                )
            seen.add(package.key)
        return self

    def packages_in(self, ecosystem: PackageEcosystem) -> list[Package]:
        """Return packages belonging to the given ``ecosystem``."""
        return [pkg for pkg in self.packages if pkg.ecosystem is ecosystem]

    def packages_with_scope(self, scope: DependencyScope) -> list[Package]:
        """Return packages declared with the given dependency ``scope``."""
        return [pkg for pkg in self.packages if pkg.scope is scope]

    @property
    def runtime_packages(self) -> list[Package]:
        """Packages required at runtime."""
        return self.packages_with_scope(DependencyScope.RUNTIME)
