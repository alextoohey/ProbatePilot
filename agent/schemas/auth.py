from __future__ import annotations

from pydantic import EmailStr, Field

from .estate import ContractModel, EstateState, utc_now_iso


class User(ContractModel):
    """Canonical user record stored at Redis key ``user:{id}``.

    ``passwordHash`` is a bcrypt hash and must never cross the wire — only
    ``PublicUser`` is returned to the browser.
    """

    id: str
    name: str
    email: str
    phone: str | None = None
    passwordHash: str
    relationship: str | None = None
    state: str | None = None
    county: str | None = None
    estateIds: list[str] = Field(default_factory=list)
    createdAt: str = Field(default_factory=utc_now_iso)


class PublicUser(ContractModel):
    """The user fields safe to send to the browser (no password hash)."""

    id: str
    name: str
    email: str
    phone: str | None = None
    relationship: str | None = None
    state: str | None = None
    county: str | None = None
    estateIds: list[str] = Field(default_factory=list)
    createdAt: str

    @classmethod
    def from_user(cls, user: User) -> "PublicUser":
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            phone=user.phone,
            relationship=user.relationship,
            state=user.state,
            county=user.county,
            estateIds=user.estateIds,
            createdAt=user.createdAt,
        )


class RegisterRequest(ContractModel):
    # Account
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    phone: str | None = None
    # Who they're helping
    deceasedName: str
    dateOfDeath: str | None = None
    relationship: str | None = None
    # The estate
    state: str | None = "California"
    county: str | None = None
    hasWill: str | None = None


class LoginRequest(ContractModel):
    email: EmailStr
    password: str


class AuthResponse(ContractModel):
    """Returned by register/login. ``token`` is the opaque session token the
    web layer stores in an httpOnly cookie."""

    token: str
    user: PublicUser
    estate: EstateState | None = None


class MeResponse(ContractModel):
    user: PublicUser
    estates: list[EstateState] = Field(default_factory=list)
