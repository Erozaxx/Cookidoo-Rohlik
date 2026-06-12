"""Async client for the (reverse-engineered) Rohlik.cz frontend API.

Endpoints verified against two community projects
(github.com/dvejsada/HA-RohlikCZ, github.com/tomaspavlin/rohlik-mcp):

- POST /services/frontend-service/login            {email, password, name: ""}
- POST /services/frontend-service/logout
- GET  /services/frontend-service/search-metadata  ?search=&offset=&limit=&companyId=1&canCorrect=true
- GET  /services/frontend-service/v2/cart
- POST /services/frontend-service/v2/cart          {productId, quantity, actionId: null, recipeId: null, source}
- DELETE /services/frontend-service/v2/cart?orderFieldId=...
- GET  /services/frontend-service/timeslots-api/0  ?userId=&addressId=&reasonableDeliveryTime=true

NOTE: No public reverse-engineered CHECKOUT endpoint exists. This client
intentionally stops at "filled cart"; order completion happens in the
Rohlik app/e-shop (which also matches Rohlik's MCP terms of service).
Unofficial API — personal use only, may break anytime.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://www.rohlik.cz"


class RohlikError(RuntimeError):
    """Generic Rohlik API error."""


class RohlikAuthError(RohlikError):
    """Invalid credentials."""


@dataclass(frozen=True)
class Product:
    """A product as returned by search."""

    id: int
    name: str
    brand: str
    price: float
    currency: str
    textual_amount: str  # e.g. "500 g"


@dataclass(frozen=True)
class CartItem:
    id: str
    order_field_id: str
    name: str
    quantity: int
    price: float


class RohlikClient:
    """Session-scoped client; use as async context manager."""

    def __init__(self, email: str, password: str) -> None:
        self._email = email
        self._password = password
        self._session: aiohttp.ClientSession | None = None
        self.user_id: int | None = None
        self.address_id: int | None = None

    async def __aenter__(self) -> "RohlikClient":
        self._session = aiohttp.ClientSession()
        await self.login()
        return self

    async def __aexit__(self, *exc: object) -> None:
        assert self._session is not None
        try:
            await self._session.post(f"{BASE_URL}/services/frontend-service/logout")
        finally:
            await self._session.close()
            self._session = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RohlikError("Client not started; use 'async with RohlikClient(...)'")
        return self._session

    async def login(self) -> None:
        payload = {"email": self._email, "password": self._password, "name": ""}
        async with self.session.post(
            f"{BASE_URL}/services/frontend-service/login", json=payload
        ) as resp:
            data: dict[str, Any] = await resp.json()
        status = data.get("status")
        if status == 401:
            raise RohlikAuthError("Invalid Rohlik credentials")
        if status != 200:
            raise RohlikError(f"Login failed with status {status}")
        user = (data.get("data") or {}).get("user") or {}
        address = (data.get("data") or {}).get("address") or {}
        self.user_id = user.get("id")
        self.address_id = address.get("id")
        logger.info("Logged in to Rohlik (user_id=%s)", self.user_id)

    async def search_products(self, query: str, limit: int = 10) -> list[Product]:
        """Search products; sponsored results are filtered out."""
        params = {
            "search": query,
            "offset": 0,
            "limit": limit + 5,
            "companyId": 1,
            "canCorrect": "true",
        }
        async with self.session.get(
            f"{BASE_URL}/services/frontend-service/search-metadata", params=params
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        products: list[Product] = []
        for p in (data.get("data") or {}).get("productList", []):
            if any(b.get("slug") == "promoted" for b in p.get("badge", []) or []):
                continue
            price = p.get("price") or {}
            products.append(
                Product(
                    id=int(p["productId"]),
                    name=p.get("productName", ""),
                    brand=p.get("brand", "") or "",
                    price=float(price.get("full", 0) or 0),
                    currency=price.get("currency", "CZK"),
                    textual_amount=p.get("textualAmount", "") or "",
                )
            )
            if len(products) >= limit:
                break
        return products

    async def add_to_cart(self, product_id: int, quantity: int) -> None:
        payload = {
            "actionId": None,
            "productId": int(product_id),
            "quantity": int(quantity),
            "recipeId": None,
            "source": "true:Shopping Lists",
        }
        async with self.session.post(
            f"{BASE_URL}/services/frontend-service/v2/cart", json=payload
        ) as resp:
            resp.raise_for_status()

    async def get_cart(self) -> tuple[float, list[CartItem]]:
        """Return (total price, items)."""
        async with self.session.get(
            f"{BASE_URL}/services/frontend-service/v2/cart"
        ) as resp:
            resp.raise_for_status()
            data = (await resp.json()).get("data") or {}
        items = [
            CartItem(
                id=pid,
                order_field_id=p.get("orderFieldId", ""),
                name=p.get("productName", ""),
                quantity=int(p.get("quantity", 0)),
                price=float(p.get("price", 0) or 0),
            )
            for pid, p in (data.get("items") or {}).items()
        ]
        return float(data.get("totalPrice", 0) or 0), items

    async def remove_from_cart(self, order_field_id: str) -> None:
        async with self.session.delete(
            f"{BASE_URL}/services/frontend-service/v2/cart",
            params={"orderFieldId": order_field_id},
        ) as resp:
            resp.raise_for_status()

    async def get_delivery_slots(self) -> dict[str, Any]:
        """Raw timeslot data for the default address."""
        if not self.user_id or not self.address_id:
            raise RohlikError("user_id/address_id unavailable (login first)")
        params = {
            "userId": self.user_id,
            "addressId": self.address_id,
            "reasonableDeliveryTime": "true",
        }
        async with self.session.get(
            f"{BASE_URL}/services/frontend-service/timeslots-api/0", params=params
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        return data.get("data") or data

    async def checkout(self) -> None:
        """Not implemented on purpose.

        No public reverse-engineered checkout endpoint exists and Rohlik's
        own MCP terms require completing orders in the e-shop. The flow
        therefore ends with a filled cart + notification.
        """
        raise NotImplementedError(
            "Checkout must be completed in the Rohlik app/e-shop."
        )
