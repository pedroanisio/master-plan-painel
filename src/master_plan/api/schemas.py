"""API request/response schemas for the Project CRUDL endpoints.

The domain model :class:`~master_plan.models.project.Project` describes the
*content* of a project. These schemas add the transport concerns:

* :class:`ProjectRecord` — a stored project, i.e. ``Project`` plus a server
  assigned ``id`` (the stable handle used by read/update/delete).
* :class:`ProjectUpdate` — a partial patch where every field is optional.

``ProjectCreate`` is simply the domain ``Project`` used directly as the POST
body, so it is re-exported here for symmetry.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from master_plan.models.project import (
    COLOR_ID_MAX,
    COLOR_ID_MIN,
    DependencyScope,
    Language,
    Package,
    PackageEcosystem,
    Project,
)

__all__ = ["ProjectCreate", "ProjectRecord", "ProjectUpdate"]

# Creating a project takes the full domain model as its body.
ProjectCreate = Project


class ProjectRecord(Project):
    """A persisted project: the domain model plus server-assigned identity.

    ``owner_id`` is the id of the user the project belongs to. Like ``id`` it is
    assigned by the server from the authenticated caller, never accepted from
    the request body.
    """

    id: str = Field(..., description="Server-assigned unique identifier.")
    owner_id: str = Field(..., description="Id of the user that owns this project.")

    @classmethod
    def from_project(
        cls, id: str, project: Project, *, owner_id: str
    ) -> "ProjectRecord":
        """Combine an ``id`` and ``owner_id`` with an existing :class:`Project`."""
        return cls(id=id, owner_id=owner_id, **project.model_dump())

    def to_project(self) -> Project:
        """Return the underlying :class:`Project` without server-only fields."""
        return Project.model_validate(self.model_dump(exclude={"id", "owner_id"}))


class ProjectUpdate(BaseModel):
    """Partial update for a project; only provided fields are changed."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    name: str | None = Field(default=None, min_length=1)
    color_id: int | None = Field(default=None, ge=COLOR_ID_MIN, le=COLOR_ID_MAX)
    domain: str | None = Field(default=None, min_length=1)
    sub_domain: str | None = None
    purpose: str | None = Field(default=None, min_length=1)
    languages: list[Language] | None = Field(default=None, min_length=1)
    primary_language: Language | None = None
    packages: list[Package] | None = None
    repository: str | None = None
    description: str | None = None
    tags: list[str] | None = None

    def apply_to(self, project: Project) -> Project:
        """Return a new ``Project`` with this patch's set fields overlaid.

        Re-validates through ``Project`` so invariants (primary language
        membership, package uniqueness, ...) are enforced on the merged result.
        """
        patch = self.model_dump(exclude_unset=True)
        merged = {**project.model_dump(), **patch}
        return Project.model_validate(merged)


# Re-export domain enums/types so API consumers can import from one module.
__all__ += ["Language", "PackageEcosystem", "DependencyScope", "Package", "Project"]
