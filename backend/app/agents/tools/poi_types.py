from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VerifiedPoi:
    provider: str
    provider_place_id: str
    name: str
    city: str
    address: str
    lat: float
    lng: float
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    verification_status: str = "single_verified"
    source_providers: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "provider_place_id": self.provider_place_id,
            "name": self.name,
            "city": self.city,
            "address": self.address,
            "lat": self.lat,
            "lng": self.lng,
            "categories": self.categories,
            "tags": self.tags,
            "verification_status": self.verification_status,
            "source_providers": self.source_providers or [self.provider],
        }
