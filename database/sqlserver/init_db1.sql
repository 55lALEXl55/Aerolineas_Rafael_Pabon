-- ============================================================
-- DB1 — América (ATL, LAX, DFW, SAO)
-- IDs: IDENTITY(1,1)  →  rango 1 - 99,999
-- NUNCA usar datetime: todas las fechas son BIGINT epoch unix
-- ============================================================

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'aerolineas_db1')
    CREATE DATABASE aerolineas_db1;
GO

USE aerolineas_db1;
GO

-- ─── aircraft ────────────────────────────────────────────────────────────────
IF OBJECT_ID('dbo.aircraft', 'U') IS NULL
CREATE TABLE dbo.aircraft (
    aircraft_id     INT             NOT NULL PRIMARY KEY,  -- 1-50, compartido
    model           NVARCHAR(30)    NOT NULL,              -- A380-800, B777-300ER, A350-900, B787-9
    manufacturer    NVARCHAR(20)    NOT NULL,
    seats_first     INT             NOT NULL,
    seats_economy   INT             NOT NULL,
    total_seats     INT             NOT NULL,
    engines         INT             NOT NULL,
    -- campos de sincronización distribuida
    node_id             INT             NOT NULL DEFAULT 1,
    lamport_ts          BIGINT          NOT NULL DEFAULT 0,
    vector_clock        NVARCHAR(50)    NOT NULL DEFAULT '[0,0,0]',
    last_update_epoch   BIGINT          NOT NULL DEFAULT 0
);
GO

-- ─── flights ─────────────────────────────────────────────────────────────────
IF OBJECT_ID('dbo.flights', 'U') IS NULL
CREATE TABLE dbo.flights (
    flight_id           INT             NOT NULL IDENTITY(1,1) PRIMARY KEY,
    flight_number       NVARCHAR(10)    NOT NULL,
    aircraft_id         INT             NOT NULL REFERENCES dbo.aircraft(aircraft_id),
    origin              NCHAR(3)        NOT NULL,
    destination         NCHAR(3)        NOT NULL,
    departure_epoch     BIGINT          NOT NULL,   -- unix epoch
    arrival_epoch       BIGINT          NOT NULL,   -- unix epoch
    duration_minutes    INT             NOT NULL,
    price_economy       DECIMAL(10,2)   NOT NULL,
    price_first         DECIMAL(10,2)   NOT NULL,
    status              NVARCHAR(15)    NOT NULL DEFAULT 'SCHEDULED',  -- SCHEDULED | BOARDING | DEPARTED | ARRIVED | CANCELLED
    available_economy   INT             NOT NULL DEFAULT 0,
    available_first     INT             NOT NULL DEFAULT 0,
    -- sincronización
    node_id             INT             NOT NULL DEFAULT 1,
    lamport_ts          BIGINT          NOT NULL DEFAULT 0,
    vector_clock        NVARCHAR(50)    NOT NULL DEFAULT '[0,0,0]',
    last_update_epoch   BIGINT          NOT NULL DEFAULT 0
);
GO

CREATE INDEX IX_flights_origin      ON dbo.flights(origin);
CREATE INDEX IX_flights_destination ON dbo.flights(destination);
CREATE INDEX IX_flights_departure   ON dbo.flights(departure_epoch);
CREATE INDEX IX_flights_status      ON dbo.flights(status);
GO

-- ─── seats ───────────────────────────────────────────────────────────────────
IF OBJECT_ID('dbo.seats', 'U') IS NULL
CREATE TABLE dbo.seats (
    seat_id         INT             NOT NULL IDENTITY(1,1) PRIMARY KEY,
    flight_id       INT             NOT NULL REFERENCES dbo.flights(flight_id),
    seat_number     NVARCHAR(5)     NOT NULL,   -- e.g. "12A"
    seat_class      NVARCHAR(10)    NOT NULL,   -- FIRST | ECONOMY
    status          NVARCHAR(12)    NOT NULL DEFAULT 'AVAILABLE',  -- AVAILABLE|LOCKED|RESERVED|SOLD|REFUNDED
    locked_until    BIGINT          NULL,       -- epoch hasta el que está bloqueado
    price           DECIMAL(10,2)   NOT NULL,
    -- sincronización
    node_id             INT             NOT NULL DEFAULT 1,
    lamport_ts          BIGINT          NOT NULL DEFAULT 0,
    vector_clock        NVARCHAR(50)    NOT NULL DEFAULT '[0,0,0]',
    last_update_epoch   BIGINT          NOT NULL DEFAULT 0
);
GO

CREATE INDEX IX_seats_flight_id ON dbo.seats(flight_id);
CREATE INDEX IX_seats_status    ON dbo.seats(status);
GO

-- ─── passengers ──────────────────────────────────────────────────────────────
IF OBJECT_ID('dbo.passengers', 'U') IS NULL
CREATE TABLE dbo.passengers (
    passenger_id    INT             NOT NULL IDENTITY(1,1) PRIMARY KEY,
    full_name       NVARCHAR(100)   NOT NULL,
    email           NVARCHAR(150)   NOT NULL,
    passport_number NVARCHAR(30)    NOT NULL,
    phone           NVARCHAR(20)    NULL,
    nationality     NCHAR(2)        NULL,
    -- sincronización
    node_id             INT             NOT NULL DEFAULT 1,
    lamport_ts          BIGINT          NOT NULL DEFAULT 0,
    vector_clock        NVARCHAR(50)    NOT NULL DEFAULT '[0,0,0]',
    last_update_epoch   BIGINT          NOT NULL DEFAULT 0
);
GO

CREATE UNIQUE INDEX IX_passengers_passport ON dbo.passengers(passport_number);
CREATE INDEX        IX_passengers_email    ON dbo.passengers(email);
GO

-- ─── tickets ─────────────────────────────────────────────────────────────────
IF OBJECT_ID('dbo.tickets', 'U') IS NULL
CREATE TABLE dbo.tickets (
    ticket_id           INT             NOT NULL IDENTITY(1,1) PRIMARY KEY,
    passenger_id        INT             NOT NULL REFERENCES dbo.passengers(passenger_id),
    flight_id           INT             NOT NULL REFERENCES dbo.flights(flight_id),
    seat_id             INT             NOT NULL REFERENCES dbo.seats(seat_id),
    status              NVARCHAR(12)    NOT NULL DEFAULT 'RESERVED',  -- RESERVED|PAID|REFUNDED|EXPIRED
    booking_epoch       BIGINT          NOT NULL,
    expiry_epoch        BIGINT          NOT NULL,   -- booking + 86400 (24 h)
    payment_epoch       BIGINT          NULL,
    total_price         DECIMAL(10,2)   NOT NULL,
    pdf_url             NVARCHAR(500)   NULL,
    -- sincronización
    node_id             INT             NOT NULL DEFAULT 1,
    lamport_ts          BIGINT          NOT NULL DEFAULT 0,
    vector_clock        NVARCHAR(50)    NOT NULL DEFAULT '[0,0,0]',
    last_update_epoch   BIGINT          NOT NULL DEFAULT 0
);
GO

CREATE INDEX IX_tickets_passenger ON dbo.tickets(passenger_id);
CREATE INDEX IX_tickets_flight    ON dbo.tickets(flight_id);
CREATE INDEX IX_tickets_status    ON dbo.tickets(status);
CREATE INDEX IX_tickets_expiry    ON dbo.tickets(expiry_epoch);
GO

-- ─── sync_log ─────────────────────────────────────────────────────────────────
IF OBJECT_ID('dbo.sync_log', 'U') IS NULL
CREATE TABLE dbo.sync_log (
    log_id              INT             NOT NULL IDENTITY(1,1) PRIMARY KEY,
    source_node         INT             NOT NULL,
    target_node         INT             NOT NULL,
    operation           NVARCHAR(10)    NOT NULL,   -- INSERT|UPDATE|DELETE
    table_name          NVARCHAR(50)    NOT NULL,
    record_id           INT             NOT NULL,
    payload             NVARCHAR(MAX)   NULL,       -- JSON del registro
    status              NVARCHAR(10)    NOT NULL DEFAULT 'PENDING',  -- PENDING|APPLIED|CONFLICT|FAILED
    lamport_ts          BIGINT          NOT NULL DEFAULT 0,
    vector_clock        NVARCHAR(50)    NOT NULL DEFAULT '[0,0,0]',
    created_epoch       BIGINT          NOT NULL,
    applied_epoch       BIGINT          NULL,
    -- sincronización
    node_id             INT             NOT NULL DEFAULT 1,
    last_update_epoch   BIGINT          NOT NULL DEFAULT 0
);
GO

CREATE INDEX IX_synclog_status  ON dbo.sync_log(status);
CREATE INDEX IX_synclog_source  ON dbo.sync_log(source_node);
CREATE INDEX IX_synclog_created ON dbo.sync_log(created_epoch);
GO

-- ─── Seed de aviones (compartido, igual en las 3 BDs) ────────────────────────
IF NOT EXISTS (SELECT 1 FROM dbo.aircraft WHERE aircraft_id = 1)
BEGIN
    -- A380-800 (IDs 1-6): 10 primera + 439 turista = 449, 4 motores
    INSERT INTO dbo.aircraft VALUES (1,'A380-800','Airbus',10,439,449,4,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (2,'A380-800','Airbus',10,439,449,4,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (3,'A380-800','Airbus',10,439,449,4,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (4,'A380-800','Airbus',10,439,449,4,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (5,'A380-800','Airbus',10,439,449,4,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (6,'A380-800','Airbus',10,439,449,4,1,0,'[0,0,0]',0);
    -- B777-300ER (IDs 7-24): 10 primera + 300 turista = 310, 2 motores
    INSERT INTO dbo.aircraft VALUES (7,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (8,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (9,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (10,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (11,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (12,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (13,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (14,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (15,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (16,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (17,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (18,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (19,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (20,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (21,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (22,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (23,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (24,'B777-300ER','Boeing',10,300,310,2,1,0,'[0,0,0]',0);
    -- A350-900 (IDs 25-35): 12 primera + 250 turista = 262, 2 motores
    INSERT INTO dbo.aircraft VALUES (25,'A350-900','Airbus',12,250,262,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (26,'A350-900','Airbus',12,250,262,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (27,'A350-900','Airbus',12,250,262,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (28,'A350-900','Airbus',12,250,262,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (29,'A350-900','Airbus',12,250,262,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (30,'A350-900','Airbus',12,250,262,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (31,'A350-900','Airbus',12,250,262,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (32,'A350-900','Airbus',12,250,262,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (33,'A350-900','Airbus',12,250,262,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (34,'A350-900','Airbus',12,250,262,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (35,'A350-900','Airbus',12,250,262,2,1,0,'[0,0,0]',0);
    -- B787-9 (IDs 36-50): 8 primera + 220 turista = 228, 2 motores
    INSERT INTO dbo.aircraft VALUES (36,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (37,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (38,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (39,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (40,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (41,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (42,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (43,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (44,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (45,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (46,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (47,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (48,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (49,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
    INSERT INTO dbo.aircraft VALUES (50,'B787-9','Boeing',8,220,228,2,1,0,'[0,0,0]',0);
END
GO
