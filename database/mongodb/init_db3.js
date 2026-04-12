// ============================================================
// DB3 — Asia + Oceanía (PEK, TYO, SIN, CAN)
// IDs: secuencia desde 500,000
// NUNCA usar Date objects: todas las fechas son epoch unix (Number)
// ============================================================

db = db.getSiblingDB('aerolineas_db3');

// ─── Colección: aircraft ─────────────────────────────────────────────────────
db.createCollection('aircraft');
db.aircraft.createIndex({ aircraft_id: 1 }, { unique: true });

// ─── Colección: flights ──────────────────────────────────────────────────────
db.createCollection('flights');
db.flights.createIndex({ flight_id: 1 }, { unique: true });
db.flights.createIndex({ origin: 1 });
db.flights.createIndex({ destination: 1 });
db.flights.createIndex({ departure_epoch: 1 });
db.flights.createIndex({ status: 1 });
db.flights.createIndex({ origin: 1, destination: 1, departure_epoch: 1 });

// ─── Colección: seats ────────────────────────────────────────────────────────
db.createCollection('seats');
db.seats.createIndex({ seat_id: 1 }, { unique: true });
db.seats.createIndex({ flight_id: 1 });
db.seats.createIndex({ status: 1 });
db.seats.createIndex({ flight_id: 1, status: 1 });

// ─── Colección: passengers ───────────────────────────────────────────────────
db.createCollection('passengers');
db.passengers.createIndex({ passenger_id: 1 }, { unique: true });
db.passengers.createIndex({ passport_number: 1 }, { unique: true });
db.passengers.createIndex({ email: 1 });

// ─── Colección: tickets ──────────────────────────────────────────────────────
db.createCollection('tickets');
db.tickets.createIndex({ ticket_id: 1 }, { unique: true });
db.tickets.createIndex({ passenger_id: 1 });
db.tickets.createIndex({ flight_id: 1 });
db.tickets.createIndex({ status: 1 });
db.tickets.createIndex({ expiry_epoch: 1 });

// ─── Colección: sync_log ─────────────────────────────────────────────────────
db.createCollection('sync_log');
db.sync_log.createIndex({ log_id: 1 }, { unique: true });
db.sync_log.createIndex({ status: 1 });
db.sync_log.createIndex({ source_node: 1 });
db.sync_log.createIndex({ created_epoch: 1 });

// ─── Secuencias (counters) ────────────────────────────────────────────────────
db.createCollection('counters');
db.counters.insertMany([
    { _id: 'flight_id',    seq: 500000 },
    { _id: 'seat_id',      seq: 500000 },
    { _id: 'passenger_id', seq: 500000 },
    { _id: 'ticket_id',    seq: 500000 },
    { _id: 'log_id',       seq: 500000 }
]);

// ─── Función helper para auto-increment (usada por el seed) ──────────────────
// db.counters.findOneAndUpdate({ _id: 'flight_id' }, { $inc: { seq: 1 } }, { returnDocument: 'after' }).seq

// ─── Seed de aviones (idéntico a SQL) ─────────────────────────────────────────
const aircraft = [];
// A380-800: IDs 1-6
for (let i = 1; i <= 6; i++) {
    aircraft.push({
        aircraft_id: i, model: 'A380-800', manufacturer: 'Airbus',
        seats_first: 10, seats_economy: 439, total_seats: 449, engines: 4,
        node_id: 3, lamport_ts: 0, vector_clock: '[0,0,0]', last_update_epoch: 0
    });
}
// B777-300ER: IDs 7-24
for (let i = 7; i <= 24; i++) {
    aircraft.push({
        aircraft_id: i, model: 'B777-300ER', manufacturer: 'Boeing',
        seats_first: 10, seats_economy: 300, total_seats: 310, engines: 2,
        node_id: 3, lamport_ts: 0, vector_clock: '[0,0,0]', last_update_epoch: 0
    });
}
// A350-900: IDs 25-35
for (let i = 25; i <= 35; i++) {
    aircraft.push({
        aircraft_id: i, model: 'A350-900', manufacturer: 'Airbus',
        seats_first: 12, seats_economy: 250, total_seats: 262, engines: 2,
        node_id: 3, lamport_ts: 0, vector_clock: '[0,0,0]', last_update_epoch: 0
    });
}
// B787-9: IDs 36-50
for (let i = 36; i <= 50; i++) {
    aircraft.push({
        aircraft_id: i, model: 'B787-9', manufacturer: 'Boeing',
        seats_first: 8, seats_economy: 220, total_seats: 228, engines: 2,
        node_id: 3, lamport_ts: 0, vector_clock: '[0,0,0]', last_update_epoch: 0
    });
}
db.aircraft.insertMany(aircraft);

print('DB3 inicializada correctamente. Colecciones e índices creados.');
print('Counters de secuencia iniciados desde 500,000.');
