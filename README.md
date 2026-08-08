# RailRo API

RailRo is a railway freight booking platform backend built with FastAPI. It is designed to manage the full booking lifecycle for freight transport, including e-way bill validation, vehicle eligibility checks, booking creation, QR generation, and operational workflows.

## What this project does

This project helps a freight booking system process requests from start to finish:

1. A user submits a freight booking request.
2. The system validates the e-way bill data.
3. The vehicle and driver details are checked for eligibility.
4. The booking is created and tracked through its lifecycle.
5. QR-based operational workflows and loading/dispatch processes are supported.

In simple terms, this project acts as the backend engine for a digital freight booking and operations platform.

## How the whole process works

- The application starts with a FastAPI server and initializes the database and Redis connections.
- The booking flow is handled through modular services under the `modules/` package.
- E-way bill information is validated and processed through the e-way bill module.
- Vehicle and driver eligibility checks are performed in the vehicles module.
- Bookings are managed through the bookings module, including status transitions and related services.
- Operational modules support loading plans and operational actions for the freight process.
- QR services help generate and manage booking-related QR outputs.

## Main features

- FastAPI-based backend API
- Modular monolith architecture
- PostgreSQL and Redis integration
- Async SQLAlchemy support
- Alembic database migrations
- Booking, vehicle, and e-way bill modules
- QR generation support
- Health monitoring endpoint

## Project structure

- `main.py` – application entry point
- `core/` – shared configuration, database, and health utilities
- `modules/bookings/` – booking domain logic and API models
- `modules/eway_bill/` – e-way bill validation and services
- `modules/vehicles/` – vehicle eligibility and driver-related logic
- `modules/operations/` – operations and loading plan workflows
- `tests/` – test cases for QR and service behaviour

## Requirements

- Python 3.11+
- PostgreSQL
- Redis
- Virtual environment recommended

## Installation

1. Create and activate a virtual environment
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables
   Create a `.env` file based on `.env.example` and set your database and Redis values.

4. Run database migrations
   ```bash
   alembic upgrade head
   ```

5. Start the application
   ```bash
   uvicorn main:app --reload
   ```



## Testing

Run tests with:

```bash
pytest
```

## GitHub README note

If you want to paste this into the GitHub repository description, you can use the following short version:

> RailRo is a FastAPI-based backend for a railway freight booking platform. It supports e-way bill validation, vehicle eligibility checks, booking lifecycle management, QR-based operations, and freight workflow automation.

## License

This project is intended for internal or educational use unless otherwise specified by the repository owner.
