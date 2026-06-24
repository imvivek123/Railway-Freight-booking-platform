# E-Way Bill Module Study and Modification Guide

This document explains how the `modules/eway_bill` feature works, what every
source file and function is responsible for, and where to make common changes.

## 1. Module purpose

The module exposes this API:

```http
POST /api/v1/eway/fetch
Content-Type: application/json

{
  "booking_id": "3e7346b5-8b9d-4cc3-8e3d-42e651df8c37",
  "eway_bill_number": "181012345678"
}
```

It validates the request, checks Redis, fetches GST data when necessary,
applies RailRo's business rules, saves the result in PostgreSQL, and returns a
decision such as:

```json
{
  "status": "ALLOW",
  "validity_hours_remaining": 120,
  "warnings": [],
  "eway_data": {
    "ewayBillNo": "181012345678"
  }
}
```

## 2. Architecture and request flow

The module follows a layered design:

```text
HTTP request
    |
    v
router.py       HTTP handling and dependency injection
    |
    v
schemas.py      Request and response validation
    |
    v
services/eway_bill_service.py  Cache flow and business decisions
   / \
  v   v
repository.py   adapters/gst_adapter.py
PostgreSQL      GST provider
  |
  v
models.py       SQLAlchemy table mapping
```

For a valid request, the exact sequence is:

1. FastAPI converts the JSON body into `EWayBillFetchRequest`.
2. The E-Way Bill number validator ensures it has exactly 12 ASCII digits.
3. `EWayBillService.fetch()` checks Redis key `eway:{eway_bill_number}`.
4. A valid cache hit is returned immediately.
5. On a cache miss, the configured `GSTAdapter` fetches the GST data.
6. The service parses `validUpto` and calculates remaining whole hours.
7. The service checks expiry and restricted-commodity rules.
8. The repository saves the decision and complete GST response.
9. The response is cached for 900 seconds (15 minutes).
10. FastAPI serializes the response as JSON.

Important: a cache hit does not create another database record because it
returns at step 4.

## 3. Folder structure

```text
modules/
└── eway_bill/
    ├── __init__.py
    ├── EWAY_BILL_GUIDE.md
    ├── router.py
    ├── schemas.py
    ├── services/
    │   ├── __init__.py
    │   └── eway_bill_service.py
    ├── repository.py
    ├── models.py
    └── adapters/
        ├── __init__.py
        └── gst_adapter.py
```

## 4. `schemas.py`: API data validation

Pydantic schemas describe and validate data at the HTTP boundary.

### `EWayBillFetchRequest`

Represents the incoming request body.

Fields:

- `booking_id: UUID`: Pydantic accepts a UUID string and converts it to a
  Python `UUID` object.
- `eway_bill_number: str`: the GST E-Way Bill number.

Its `model_config` has two useful settings:

- `extra="forbid"` rejects unknown request fields. This helps catch spelling
  mistakes instead of silently ignoring them.
- `str_strip_whitespace=True` removes surrounding spaces from strings before
  validation.

### `validate_eway_bill_number()`

This field validator runs when Pydantic creates an `EWayBillFetchRequest`.
It requires exactly 12 ASCII digits.

```python
if len(value) != 12 or not value.isascii() or not value.isdigit():
    raise ValueError(...)
```

All three checks matter. `isdigit()` alone accepts some non-ASCII Unicode

Represents the successful API response.

- `status` can only be `"ALLOW"` or `"REJECT"`.
- `validity_hours_remaining` contains whole hours, rounded down.
- `warnings` is a list of human-readable warnings.
- `eway_data` contains the full raw dictionary received from GST.

### `ErrorResponse`

Documents FastAPI error responses. `detail` uses `Any` because validation
errors are a list of details, while service errors use a string.

## 5. `router.py`: HTTP and dependency wiring

The router is the module's public HTTP boundary. It should translate HTTP data
and errors, but business decisions belong in `services/eway_bill_service.py`.

### `BadRequestValidationRoute`

FastAPI normally returns HTTP 422 for invalid Pydantic input. The requirement
for this module is HTTP 400, so this custom route catches
`RequestValidationError` and raises an HTTP 400 response.

### `BadRequestValidationRoute.get_route_handler()`

This method wraps FastAPI's original route handler. The nested `handler()`:

1. lets FastAPI process the request normally;
2. catches request validation failures;
3. removes the non-serializable `ctx` error information; and
4. returns the cleaned validation details with status 400.

### `router`

The `APIRouter` has:

- prefix `/api/v1/eway`;
- OpenAPI tag `E-Way Bill`; and
- the custom validation route described above.

The `fetch_eway_bill` function adds `/fetch`, producing the full endpoint
`POST /api/v1/eway/fetch`.

### `get_db_session()`

Reads an async SQLAlchemy session factory from:

```python
request.app.state.db_sessionmaker
```

It opens one session for the request and closes it automatically afterward.
The main FastAPI application must configure this state value during startup.

### `get_cache()`

Reads the async Redis client from:

```python
request.app.state.redis
```

The returned client satisfies the smaller `AsyncCache` interface used by the
service.

### `get_gst_adapter()`

Currently returns `MockGSTAdapter`. Change this dependency to return a real
adapter when GST credentials and API access are available.

Keeping the choice here means `services/eway_bill_service.py` does not need to know whether the
data comes from a mock, an HTTP API, or another provider.

### `get_repository()`

Receives the request's SQLAlchemy session through FastAPI dependency injection
and creates `SQLAlchemyEWayBillRepository`.

### `get_eway_bill_service()`

Builds `EWayBillService` using three replaceable dependencies:

- repository;
- cache; and
- GST adapter.

Tests can override any of these FastAPI dependencies or construct the service
directly with fake objects.

### `fetch_eway_bill()`

This is the endpoint function. It delegates all work to `service.fetch()` and
translates module errors into HTTP errors:

- unavailable or malformed GST response becomes HTTP 502;
- database persistence failure becomes HTTP 500;
- successful processing returns HTTP 200.

## 6. `services/eway_bill_service.py`: business logic

This is the central application layer. Changes to expiry, warning, commodity,
or cache behavior normally belong here.

### Constants

- `CACHE_TTL_SECONDS = 15 * 60`: stores responses for 900 seconds.
- `EXPIRY_WARNING_HOURS = 48`: warning threshold.
- `EXPIRY_WARNING`: warning text returned to the client.
- `RESTRICTED_COMMODITIES`: normalized categories that produce `REJECT`.

### `AsyncCache`

This `Protocol` defines only the Redis-like operations needed by the service:
`get`, `set`, and `delete`. A compatible fake cache can be used in unit tests
without importing or starting Redis.

### `GSTServiceUnavailableError`

Signals that the adapter failed to obtain data. The router maps it to HTTP 502.

### `InvalidGSTResponseError`

Signals that GST returned data without a usable `validUpto` value. The router
also maps it to HTTP 502 because the client's input was not the problem.

### `EWayBillService.__init__()`

Receives all external dependencies instead of constructing them internally:

- `repository` handles PostgreSQL;
- `cache` handles Redis;
- `gst_adapter` handles GST; and
- `clock` supplies the current time.

`clock` is optional in production and defaults to current UTC. Injecting it is
important for deterministic tests of expiry rules.

### `EWayBillService.fetch()`

This function performs the complete business workflow.

Cache key creation:

```python
cache_key = f"eway:{request.eway_bill_number}"
```

On a cache hit, the cached `EWayBillFetchResponse` is returned. On a miss, the
adapter is called. Adapter failures are logged and converted to
`GSTServiceUnavailableError`.

Remaining hours are calculated using:

```python
math.floor((validity - now).total_seconds() / 3600)
```

This means 47 hours and 59 minutes becomes `47`. An expired bill can have a
negative value.

The result is `REJECT` when either condition is true:

- `validUpto` is earlier than current UTC; or
- the normalized commodity is in `RESTRICTED_COMMODITIES`.

A warning is added whenever remaining hours are less than 48. This includes an
already expired bill because its remaining hours are also below 48.

After calculating the response, the function saves the lookup first and then
writes the cache. This avoids caching a response that failed to persist.

### `_read_cache()`

Reads the Redis value and validates the cached JSON using
`EWayBillFetchResponse.model_validate_json()`.

Redis failures or corrupt values do not fail the request. The error is logged,
the service tries to delete the corrupt entry, and processing continues as a
cache miss.

### `_write_cache()`

Serializes the Pydantic response to JSON and writes it with a 15-minute TTL.
Cache write errors are logged but do not turn an otherwise successful request
into HTTP 500.

### `_parse_validity()`

Reads `validUpto` from the raw GST dictionary and parses ISO 8601 values.
It also converts a trailing `Z` to the format understood by
`datetime.fromisoformat()`.

Missing, non-string, or invalid values raise `InvalidGSTResponseError`.

### `_utc()`

Normalizes datetime values to UTC:

- a timezone-aware datetime is converted to UTC;
- a timezone-less datetime is treated as UTC.

If a real GST provider returns timezone-less India time rather than UTC, this
method or the adapter must be changed to attach `Asia/Kolkata` before converting
to UTC.

### `_extract_commodity()`

Looks for commodity data in this order:

1. `commodityCategory`;
2. `commodity_category`;
3. `category`; or
4. `prodDesc` as a fallback.

It converts values to lowercase snake-case. For example,
`"Petroleum Crude"` becomes `"petroleum_crude"`. This allows provider spelling
styles to be compared with `RESTRICTED_COMMODITIES` consistently.

## 7. `adapters/gst_adapter.py`: GST integration boundary

Adapters isolate external provider details from business logic.

### `GSTAdapterError`

A real adapter should wrap provider timeouts, authentication failures, network
errors, and unsuccessful provider responses in this exception.

### `GSTAdapter`

An abstract base class defining the required adapter function:

```python
async def fetch_eway_bill(self, eway_bill_number: str) -> dict[str, Any]
```

Every real or fake provider must implement this contract.

### `MockGSTAdapter.fetch_eway_bill()`

Returns fixed sample data without making a network request. It copies the
requested E-Way Bill number into `ewayBillNo`.

The mock currently returns `validUpto = 2026-06-30T23:59:59`. After that date,
normal business logic will correctly return `REJECT`. For long-lived local
development, either update the mock date or calculate a future value.

## 8. `repository.py`: PostgreSQL operations

The repository isolates SQLAlchemy operations from the service.

### `EWayBillPersistenceError`

Represents a database write failure without exposing SQLAlchemy details to the
router or client.

### `EWayBillRepository`

A `Protocol` describing the persistence function required by the service.
Tests can provide a small fake class with the same `create()` signature.

### `SQLAlchemyEWayBillRepository.__init__()`

Stores the `AsyncSession` created by the router dependency.

### `SQLAlchemyEWayBillRepository.create()`

Creates an `EWayBill` model, adds it to the session, commits the transaction,
and refreshes the object so database-generated fields such as `created_at` are
loaded.

If SQLAlchemy reports an error, the function rolls back the transaction and
raises `EWayBillPersistenceError`.

## 9. `models.py`: database table

### `Base`

The SQLAlchemy declarative base owns this module's metadata. Alembic needs this
metadata to discover the table.

If RailRo later introduces one shared application `Base`, import that shared
base here and remove this local `Base`. A shared base makes it easier for one
Alembic environment to discover tables from every module.

### `EWayBill`

Maps to PostgreSQL table `eway_bills`.

| Field | PostgreSQL type | Meaning |
|---|---|---|
| `id` | UUID | Primary key generated in Python |
| `booking_id` | UUID | Booking associated with this lookup |
| `eway_bill_number` | VARCHAR(12) | GST bill number |
| `status` | VARCHAR(16) | `ALLOW` or `REJECT` |
| `validity` | TIMESTAMP WITH TIME ZONE | Parsed GST validity time |
| `raw_response` | JSONB | Complete GST provider response |
| `created_at` | TIMESTAMP WITH TIME ZONE | Database-generated creation time |

Indexes exist on `booking_id` and `eway_bill_number` to make common lookups
faster.

## 10. Package `__init__.py` files

`modules/eway_bill/__init__.py` exports `router`, allowing the application to
import it with:

```python
from modules.eway_bill import router as eway_bill_router
```

`modules/eway_bill/adapters/__init__.py` exports `GSTAdapter`,
`GSTAdapterError`, and `MockGSTAdapter` for convenient adapter imports.

## 11. Host application setup

The main FastAPI application must provide the database factory, Redis client,
and router registration. A simplified integration looks like:

```python
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.eway_bill import router as eway_bill_router

app = FastAPI()

engine = create_async_engine(POSTGRESQL_URL)
app.state.db_sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
app.state.redis = Redis.from_url(REDIS_URL)

app.include_router(eway_bill_router)
```

Production startup and shutdown logic should close Redis and dispose of the
SQLAlchemy engine during application shutdown.

## 12. Common changes

### Add or remove a restricted commodity

Edit `RESTRICTED_COMMODITIES` in `services/eway_bill_service.py`. Use normalized lowercase
snake-case:

```python
RESTRICTED_COMMODITIES = frozenset({
    "explosives",
    "new_restricted_category",
})
```

### Change the warning threshold

Edit `EXPIRY_WARNING_HOURS` in `services/eway_bill_service.py`.

### Change the Redis duration

Edit `CACHE_TTL_SECONDS` in `services/eway_bill_service.py`.

### Add another business rejection rule

Add the rule where `status` is calculated in `EWayBillService.fetch()`. For
larger rule sets, extract a method such as `_calculate_status()` and test it
independently.

### Use a real GST provider

1. Create a class that inherits `GSTAdapter`.
2. Implement async HTTP calls in `fetch_eway_bill()`.
3. Use connection and read timeouts.
4. Convert provider failures to `GSTAdapterError`.
5. Return the provider data as a dictionary.
6. Change `get_gst_adapter()` in `router.py` to return the new adapter.

Do not place HTTP-provider code in `services/eway_bill_service.py`; keeping it in the adapter
preserves testability and separation of responsibilities.

### Change API input or output

Update the Pydantic classes in `schemas.py`, then update service construction
of the response. FastAPI will update the generated OpenAPI documentation.

### Change database fields

Update `EWayBill` in `models.py`, adjust repository writes, and generate a new
Alembic migration. Do not edit an already-applied production migration.

## 13. Testing approach

The easiest unit test constructs `EWayBillService` directly with:

- a fake in-memory repository;
- a fake dictionary cache;
- a fake GST adapter; and
- a fixed UTC clock.

Important scenarios to test:

1. valid bill with more than 48 hours returns `ALLOW` without warnings;
2. valid bill with less than 48 hours returns `ALLOW` with a warning;
3. expired bill returns `REJECT`;
4. every restricted commodity returns `REJECT`;
5. cache hit does not call GST or the repository;
6. corrupt cache falls back to GST;
7. Redis failure does not fail a successful request;
8. GST adapter failure becomes HTTP 502;
9. database failure becomes HTTP 500;
10. an E-Way Bill number other than exactly 12 digits becomes HTTP 400.

For endpoint tests, override FastAPI dependencies with
`app.dependency_overrides`. For database integration tests, use a separate
PostgreSQL database because the model depends on PostgreSQL `UUID` and `JSONB`
types.

## 14. Design rules to preserve

- Keep HTTP-specific behavior in `router.py`.
- Keep request/response validation in `schemas.py`.
- Keep business decisions and orchestration in `services/eway_bill_service.py`.
- Keep SQLAlchemy queries and transactions in `repository.py`.
- Keep table definitions in `models.py`.
- Keep external GST communication in `adapters/`.
- Inject dependencies so tests do not require real network services.
- Store the complete upstream payload in `raw_response` for auditing.
- Never log GST credentials, authorization tokens, or sensitive payloads.
