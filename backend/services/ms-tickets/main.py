"""
ms-tickets — Puerto 8005
Gestión de tickets: boarding pass PDF profesional, Apple Wallet (.pkpass), refund.
"""
import hashlib
import io
import json
import os
import time
import zipfile
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db1, get_db2, mongo_db
from models import TicketOut, RefundRequest

app = FastAPI(
    title="ms-tickets",
    description="Microservicio de tickets y PDF — Aerolíneas Rafael Pabón",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_ID = int(os.getenv("NODE_ID", "1"))

AIRPORT_NAMES = {
    "ATL": "Atlanta, GA", "LAX": "Los Angeles, CA", "DFW": "Dallas, TX", "SAO": "São Paulo",
    "LON": "London, UK", "PAR": "Paris, FR", "FRA": "Frankfurt, DE", "IST": "Istanbul, TR",
    "MAD": "Madrid, ES", "AMS": "Amsterdam, NL", "DXB": "Dubai, UAE",
    "PEK": "Beijing, CN", "TYO": "Tokyo, JP", "SIN": "Singapore", "CAN": "Guangzhou, CN",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _node_for(ticket_id: int) -> int:
    if ticket_id < 100_000:
        return 1
    if ticket_id < 500_000:
        return 2
    return 3


def _epoch_to_date(epoch: int) -> str:
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime("%d %b %Y").upper()
    except Exception:
        return "N/A"


def _epoch_to_time(epoch: int) -> str:
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime("%H:%M")
    except Exception:
        return "00:00"


def _gate_from_flight(flight_id: int) -> str:
    letters = "ABCDEFGH"
    return f"{letters[flight_id % 8]}{(flight_id % 30) + 1}"


async def _fetch_ticket_data(ticket_id: int, db1: Session, db2: Session):
    """Obtiene ticket, pasajero, vuelo y asiento del nodo correcto."""
    node = _node_for(ticket_id)

    if node == 3:
        ticket = await mongo_db.tickets.find_one({"ticket_id": ticket_id}, {"_id": 0})
        if not ticket:
            raise HTTPException(404, "Ticket no encontrado")
        passenger = await mongo_db.passengers.find_one({"passenger_id": ticket["passenger_id"]}, {"_id": 0}) or {}
        flight = await mongo_db.flights.find_one({"flight_id": ticket["flight_id"]}, {"_id": 0}) or {}
        seat = await mongo_db.seats.find_one({"seat_id": ticket["seat_id"]}, {"_id": 0}) or {}
    else:
        db = db1 if node == 1 else db2
        row = db.execute(
            text("SELECT * FROM dbo.tickets WHERE ticket_id=:tid"), {"tid": ticket_id}
        ).mappings().first()
        if not row:
            raise HTTPException(404, "Ticket no encontrado")
        ticket = dict(row)

        p = db.execute(
            text("SELECT * FROM dbo.passengers WHERE passenger_id=:pid"),
            {"pid": ticket["passenger_id"]}
        ).mappings().first()
        passenger = dict(p) if p else {}

        fdb = db1 if int(ticket["flight_id"]) < 100_000 else db2
        f = fdb.execute(
            text("SELECT * FROM dbo.flights WHERE flight_id=:fid"),
            {"fid": ticket["flight_id"]}
        ).mappings().first()
        flight = dict(f) if f else {}

        s = db.execute(
            text("SELECT * FROM dbo.seats WHERE seat_id=:sid"),
            {"sid": ticket["seat_id"]}
        ).mappings().first()
        seat = dict(s) if s else {}

    return ticket, passenger, flight, seat


def _build_boarding_pass_pdf(
    ticket_id: int, pax_name: str, origin: str, destination: str,
    dep_epoch: int, flight_num: str, seat_num: str, seat_class: str,
    gate: str, price: float, node_id: int, lamport_ts: int,
) -> bytes:
    """Construye el PDF del boarding pass y devuelve bytes."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    import qrcode
    import qrcode.constants
    try:
        import barcode
        from barcode.writer import ImageWriter
        HAS_BARCODE = True
    except ImportError:
        HAS_BARCODE = False

    origin_city = AIRPORT_NAMES.get(origin, origin)
    dest_city   = AIRPORT_NAMES.get(destination, destination)
    date_str    = _epoch_to_date(dep_epoch)
    time_str    = _epoch_to_time(dep_epoch)

    # ── Tamaño boarding pass (210mm × 88mm) ────────────────────
    W, H = 210 * mm, 88 * mm
    HEADER_H   = 18 * mm
    FOOTER_H   = 9  * mm
    DIVIDER_X  = 136 * mm
    BODY_TOP   = H - HEADER_H
    BODY_BOT   = FOOTER_H

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(W, H))

    # ── Paleta ─────────────────────────────────────────────────
    NAVY  = (0.00, 0.20, 0.40)
    WHITE = (1.00, 1.00, 1.00)
    GOLD  = (1.00, 0.76, 0.03)
    LGRAY = (0.96, 0.96, 0.96)
    DGRAY = (0.40, 0.40, 0.40)

    def sf(*rgb): c.setFillColorRGB(*rgb)
    def ss(*rgb): c.setStrokeColorRGB(*rgb)

    # ── Header ─────────────────────────────────────────────────
    sf(*NAVY)
    c.rect(0, H - HEADER_H, W, HEADER_H, fill=1, stroke=0)
    sf(*WHITE)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(6 * mm, H - 11.5 * mm, "AEROLÍNEAS RAFAEL PABÓN")
    c.setFont("Helvetica", 8)
    c.drawRightString(W - 6 * mm, H - 11.5 * mm, "BOARDING PASS")
    # Gold accent
    sf(*GOLD)
    c.rect(0, H - HEADER_H - 2 * mm, W, 2 * mm, fill=1, stroke=0)

    # ── Body backgrounds ────────────────────────────────────────
    sf(*LGRAY)
    c.rect(0, BODY_BOT, DIVIDER_X, BODY_TOP - BODY_BOT, fill=1, stroke=0)
    sf(*WHITE)
    c.rect(DIVIDER_X, BODY_BOT, W - DIVIDER_X, BODY_TOP - BODY_BOT, fill=1, stroke=0)

    # ── LEFT SECTION ────────────────────────────────────────────
    LX = 6 * mm
    LY = BODY_TOP - 7 * mm

    # Passenger name
    sf(*NAVY)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(LX, LY, pax_name[:34])

    LY -= 7.5 * mm
    # FROM → TO (large IATA codes)
    sf(*NAVY)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(LX, LY, origin)
    sf(*DGRAY)
    c.setFont("Helvetica", 12)
    c.drawCentredString(LX + 44 * mm, LY + 8, "→")
    sf(*NAVY)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(LX + 56 * mm, LY, destination)

    LY -= 5 * mm
    # City names
    sf(*DGRAY)
    c.setFont("Helvetica", 7.5)
    c.drawString(LX, LY, origin_city)
    c.drawString(LX + 56 * mm, LY, dest_city)

    LY -= 8 * mm

    def draw_field(x, y, label, value, lsz=6.5, vsz=10):
        sf(*DGRAY)
        c.setFont("Helvetica", lsz)
        c.drawString(x, y + 6.5, label)
        sf(*NAVY)
        c.setFont("Helvetica-Bold", vsz)
        c.drawString(x, y, value)

    # DATE | TIME
    draw_field(LX,            LY, "DATE",   date_str[:11], vsz=9)
    draw_field(LX + 40 * mm,  LY, "TIME",   time_str,      vsz=11)

    LY -= 9 * mm
    # FLIGHT | SEAT | CLASS | GATE
    draw_field(LX,             LY, "FLIGHT",  f"RP{str(flight_num)[:6]}", vsz=9)
    draw_field(LX + 23 * mm,   LY, "SEAT",    seat_num,                   vsz=11)
    draw_field(LX + 40 * mm,   LY, "CLASS",   seat_class[:9],             vsz=8)
    draw_field(LX + 72 * mm,   LY, "GATE",    gate,                       vsz=11)

    # ── Dashed divider ─────────────────────────────────────────
    c.setDash([4, 3], 0)
    ss(*DGRAY)
    c.setLineWidth(0.5)
    c.line(DIVIDER_X, BODY_BOT + 2 * mm, DIVIDER_X, BODY_TOP - 2 * mm)
    c.setDash([], 0)

    # ── RIGHT SECTION ───────────────────────────────────────────
    RX = DIVIDER_X + 4 * mm
    RY = BODY_TOP - 5.5 * mm

    # Origin → Destination compact
    sf(*NAVY)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(RX, RY, origin)
    sf(*DGRAY)
    c.setFont("Helvetica", 9)
    c.drawString(RX + 15 * mm, RY + 4, "→")
    sf(*NAVY)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(RX + 21 * mm, RY, destination)

    RY -= 5.5 * mm
    # SEAT + GATE compact
    sf(*DGRAY)
    c.setFont("Helvetica", 6.5)
    c.drawString(RX,           RY + 5, "SEAT")
    c.drawString(RX + 14 * mm, RY + 5, "GATE")
    sf(*NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(RX,           RY, seat_num)
    c.drawString(RX + 14 * mm, RY, gate)

    RY -= 5 * mm
    # CLASS compact
    sf(*DGRAY)
    c.setFont("Helvetica", 6.5)
    c.drawString(RX, RY + 5, "CLASS")
    sf(*NAVY)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(RX, RY, seat_class)

    RY -= 4 * mm
    # Date compact
    sf(*DGRAY)
    c.setFont("Helvetica", 6.5)
    c.drawString(RX, RY + 5, "DATE")
    sf(*NAVY)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(RX, RY, date_str[:11])

    RY -= 3 * mm

    # ── QR Code ────────────────────────────────────────────────
    qr_payload = json.dumps({
        "t": ticket_id,
        "f": int(flight_num) if str(flight_num).isdigit() else 0,
        "s": seat_num,
        "p": pax_name[:20],
        "e": dep_epoch,
    }, separators=(",", ":"))
    qr = qrcode.QRCode(version=2, box_size=3, border=1,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    QR_SZ = 18 * mm
    # center QR in right panel
    right_center = DIVIDER_X + (W - DIVIDER_X) / 2
    c.drawImage(ImageReader(qr_buf),
                right_center - QR_SZ / 2, RY - QR_SZ, QR_SZ, QR_SZ)

    # ── Barcode ────────────────────────────────────────────────
    if HAS_BARCODE:
        try:
            bc = barcode.get("code128", str(ticket_id).zfill(10), writer=ImageWriter())
            bar_buf = io.BytesIO()
            bc.write(bar_buf, options={
                "write_text": False, "module_height": 7.0, "quiet_zone": 1.0,
            })
            bar_buf.seek(0)
            BAR_W = 64 * mm
            BAR_H = 9  * mm
            c.drawImage(ImageReader(bar_buf),
                        RX, BODY_BOT + 1 * mm, BAR_W, BAR_H,
                        preserveAspectRatio=False)
        except Exception:
            pass

    # ── Footer ─────────────────────────────────────────────────
    sf(*NAVY)
    c.rect(0, 0, W, FOOTER_H, fill=1, stroke=0)
    sf(*GOLD)
    c.setFont("Helvetica-Oblique", 6.5)
    c.drawCentredString(
        W / 2, 2.5 * mm,
        "Aerolíneas Rafael Pabón — nunca se atrasa, siempre el precio justo"
    )

    c.save()
    buf.seek(0)
    return buf.read()


def _build_wallet_pass(
    ticket_id: int, pax_name: str, origin: str, destination: str,
    dep_epoch: int, flight_num: str, seat_num: str, seat_class: str,
    gate: str, price: float, node_id: int, lamport_ts: int,
) -> bytes:
    """Construye un archivo .pkpass (ZIP) compatible con Apple Wallet."""
    from PIL import Image, ImageDraw, ImageFont

    date_str = _epoch_to_date(dep_epoch)

    pass_data = {
        "formatVersion": 1,
        "passTypeIdentifier": "pass.com.rafaelpabon.boarding",
        "serialNumber": str(ticket_id),
        "teamIdentifier": "RAFAELPABON",
        "organizationName": "Aerolíneas Rafael Pabón",
        "description": "Boarding Pass",
        "boardingPass": {
            "transitType": "PKTransitTypeAir",
            "primaryFields": [
                {"key": "origin",      "label": "DESDE", "value": origin},
                {"key": "destination", "label": "HACIA", "value": destination},
            ],
            "secondaryFields": [
                {"key": "passenger", "label": "PASAJERO", "value": pax_name},
                {"key": "seat",      "label": "ASIENTO",  "value": seat_num},
            ],
            "auxiliaryFields": [
                {"key": "date",   "label": "FECHA",  "value": date_str},
                {"key": "flight", "label": "VUELO",  "value": f"RP{flight_num}"},
                {"key": "gate",   "label": "PUERTA", "value": gate},
                {"key": "class",  "label": "CLASE",  "value": seat_class},
            ],
            "backFields": [
                {"key": "price",   "label": "PRECIO PAGADO",    "value": f"${price:.2f}"},
                {"key": "node",    "label": "PROCESADO EN",      "value": f"Nodo {node_id}"},
                {"key": "lamport", "label": "TIMESTAMP LÓGICO",  "value": str(lamport_ts)},
                {"key": "footer",  "label": "",
                 "value": "Rafael Pabón nunca se atrasa ni cambia precios."},
            ],
        },
        "backgroundColor":  "rgb(0, 51, 102)",
        "foregroundColor":  "rgb(255, 255, 255)",
        "labelColor":       "rgb(180, 210, 255)",
    }

    pass_bytes = json.dumps(pass_data, ensure_ascii=False, indent=2).encode("utf-8")

    # ── Generar icon.png y logo.png con Pillow ─────────────────
    def _make_icon(w: int, h: int, text: str) -> bytes:
        img  = Image.new("RGBA", (w, h), (0, 51, 102, 255))
        draw = ImageDraw.Draw(img)
        # Gold banner
        draw.rectangle([0, h // 2, w, h], fill=(255, 193, 7, 255))
        # Text placeholder
        draw.text((4, h // 4), text, fill=(255, 255, 255, 255))
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    icon_bytes  = _make_icon(87, 87, "RP")
    logo_bytes  = _make_icon(160, 50, "RP AIR")
    icon2_bytes = _make_icon(174, 174, "RP")  # icon@2x.png

    # ── manifest.json (SHA1 de cada archivo) ───────────────────
    manifest = {
        "pass.json":    hashlib.sha1(pass_bytes).hexdigest(),
        "icon.png":     hashlib.sha1(icon_bytes).hexdigest(),
        "icon@2x.png":  hashlib.sha1(icon2_bytes).hexdigest(),
        "logo.png":     hashlib.sha1(logo_bytes).hexdigest(),
    }
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")

    # ── ZIP → .pkpass ───────────────────────────────────────────
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pass.json",    pass_bytes)
        zf.writestr("manifest.json", manifest_bytes)
        zf.writestr("icon.png",     icon_bytes)
        zf.writestr("icon@2x.png",  icon2_bytes)
        zf.writestr("logo.png",     logo_bytes)

    zip_buf.seek(0)
    return zip_buf.read()


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"service": "ms-tickets", "status": "ok", "node_id": NODE_ID, "timestamp": int(time.time())}


# ─── Consulta por pasaporte (path param) ──────────────────────────────────────
# IMPORTANTE: esta ruta debe ir ANTES de /tickets/{ticket_id} para evitar
# que "passenger" sea interpretado como un ticket_id entero.

@app.get("/tickets/passenger/{passport}")
async def get_tickets_by_passport_path(
    passport: str,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Lista todos los tickets activos de un pasajero."""
    results = []
    sql = text("""
        SELECT t.ticket_id, t.flight_id, t.seat_id, t.status, t.booking_epoch,
               t.expiry_epoch, t.payment_epoch, t.total_price, t.node_id,
               t.lamport_ts, t.vector_clock, t.last_update_epoch,
               p.full_name, p.passport_number, p.email,
               f.origin, f.destination, f.departure_epoch, f.arrival_epoch,
               f.flight_number,
               s.seat_number, s.seat_class
        FROM dbo.tickets t
        JOIN dbo.passengers p ON t.passenger_id = p.passenger_id
        JOIN dbo.flights f    ON t.flight_id    = f.flight_id
        JOIN dbo.seats s      ON t.seat_id      = s.seat_id
        WHERE p.passport_number = :pp
          AND t.status NOT IN ('CANCELLED')
        ORDER BY t.booking_epoch DESC
    """)
    for db in [db1, db2]:
        try:
            rows = db.execute(sql, {"pp": passport}).mappings().all()
            results.extend([dict(r) for r in rows])
        except Exception:
            pass
    try:
        pax = await mongo_db.passengers.find_one({"passport_number": passport})
        if pax:
            pipeline = [
                {"$match": {"passenger_id": pax["passenger_id"]}},
                {"$lookup": {
                    "from": "flights", "localField": "flight_id",
                    "foreignField": "flight_id", "as": "flight"
                }},
                {"$lookup": {
                    "from": "seats", "localField": "seat_id",
                    "foreignField": "seat_id", "as": "seat"
                }},
                {"$unwind": {"path": "$flight", "preserveNullAndEmptyArrays": True}},
                {"$unwind": {"path": "$seat",   "preserveNullAndEmptyArrays": True}},
                {"$project": {"_id": 0}},
                {"$sort":  {"booking_epoch": -1}},
            ]
            async for doc in mongo_db.tickets.aggregate(pipeline):
                doc["full_name"]       = pax.get("full_name", "")
                doc["passport_number"] = pax.get("passport_number", "")
                doc["email"]           = pax.get("email", "")
                results.append(doc)
    except Exception:
        pass
    return results


@app.get("/tickets/flight/{flight_id}")
async def get_tickets_by_flight(
    flight_id: int,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Lista todos los tickets de un vuelo (para el dashboard y la vista de gestión)."""
    results = []

    if flight_id >= 500_000:
        pipeline = [
            {"$match": {"flight_id": flight_id}},
            {"$lookup": {"from": "passengers", "localField": "passenger_id",
                         "foreignField": "passenger_id", "as": "passenger"}},
            {"$lookup": {"from": "seats", "localField": "seat_id",
                         "foreignField": "seat_id", "as": "seat"}},
            {"$unwind": {"path": "$passenger", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$seat", "preserveNullAndEmptyArrays": True}},
            {"$project": {"_id": 0}},
        ]
        async for doc in mongo_db.tickets.aggregate(pipeline):
            results.append(doc)
        return results

    sql = text("""
        SELECT t.ticket_id, t.flight_id, t.seat_id, t.passenger_id, t.status,
               t.booking_epoch, t.expiry_epoch, t.payment_epoch, t.total_price,
               t.node_id, t.lamport_ts, t.vector_clock, t.last_update_epoch,
               p.full_name, p.passport_number, p.email,
               s.seat_number, s.seat_class
        FROM dbo.tickets t
        JOIN dbo.passengers p ON t.passenger_id = p.passenger_id
        JOIN dbo.seats s      ON t.seat_id = s.seat_id
        WHERE t.flight_id = :fid
        ORDER BY t.booking_epoch DESC
    """)
    db = db1 if flight_id < 100_000 else db2
    try:
        rows = db.execute(sql, {"fid": flight_id}).mappings().all()
        results.extend([dict(r) for r in rows])
    except Exception:
        pass
    return results


@app.get("/tickets/{ticket_id}", response_model=None)
async def get_ticket(
    ticket_id: int,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    node = _node_for(ticket_id)
    if node == 3:
        doc = await mongo_db.tickets.find_one({"ticket_id": ticket_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Ticket no encontrado")
        return doc
    db = db1 if node == 1 else db2
    row = db.execute(
        text("SELECT * FROM dbo.tickets WHERE ticket_id=:tid"), {"tid": ticket_id}
    ).mappings().first()
    if not row:
        raise HTTPException(404, "Ticket no encontrado")
    return dict(row)


@app.get("/tickets")
async def list_tickets_by_passport(
    passport_number: str = Query(...),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Lista todos los tickets de un pasajero (query param)."""
    results = []
    for db in [db1, db2]:
        try:
            rows = db.execute(text("""
                SELECT t.* FROM dbo.tickets t
                JOIN dbo.passengers p ON t.passenger_id = p.passenger_id
                WHERE p.passport_number = :pp
                ORDER BY t.booking_epoch DESC
            """), {"pp": passport_number}).mappings().all()
            results.extend([dict(r) for r in rows])
        except Exception:
            pass
    try:
        passenger = await mongo_db.passengers.find_one({"passport_number": passport_number})
        if passenger:
            async for doc in mongo_db.tickets.find(
                {"passenger_id": passenger["passenger_id"]}, {"_id": 0}
            ):
                results.append(doc)
    except Exception:
        pass
    return results


# ─── Refund ───────────────────────────────────────────────────────────────────

@app.post("/tickets/{ticket_id}/refund")
async def refund_ticket(
    ticket_id: int,
    req: RefundRequest,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Inicia refund con delay de propagación de 15 min (CAP AP)."""
    node = _node_for(ticket_id)
    now = int(time.time())
    refund_at = now + 900  # +15 min

    if node == 3:
        ticket = await mongo_db.tickets.find_one({"ticket_id": ticket_id})
        if not ticket:
            raise HTTPException(404, "Ticket no encontrado")
        if ticket["status"] not in ("PAID", "RESERVED"):
            raise HTTPException(409, f"No se puede hacer refund desde estado {ticket['status']}")
        await mongo_db.tickets.update_one(
            {"ticket_id": ticket_id},
            {"$set": {"status": "REFUNDED", "last_update_epoch": now}},
        )
        await mongo_db.seats.update_one(
            {"seat_id": ticket["seat_id"]},
            {"$set": {"status": "REFUNDED", "locked_until": refund_at, "last_update_epoch": now}},
        )
    else:
        db = db1 if node == 1 else db2
        row = db.execute(
            text("SELECT status, seat_id FROM dbo.tickets WHERE ticket_id=:tid"),
            {"tid": ticket_id},
        ).fetchone()
        if not row:
            raise HTTPException(404, "Ticket no encontrado")
        if row[0] not in ("PAID", "RESERVED"):
            raise HTTPException(409, f"No se puede hacer refund desde estado {row[0]}")
        db.execute(
            text("UPDATE dbo.tickets SET status='REFUNDED', last_update_epoch=:now WHERE ticket_id=:tid"),
            {"now": now, "tid": ticket_id},
        )
        db.execute(
            text("""UPDATE dbo.seats SET status='REFUNDED', locked_until=:lu,
                    last_update_epoch=:now WHERE seat_id=:sid"""),
            {"lu": refund_at, "now": now, "sid": row[1]},
        )
        db.commit()

    return {
        "ticket_id": ticket_id,
        "status": "REFUNDED",
        "refund_epoch": now,
        "seat_available_after": refund_at,
        "message": "El asiento quedará disponible en ~15 minutos (consistencia eventual)",
    }


# ─── Boarding Pass PDF ────────────────────────────────────────────────────────

@app.get("/tickets/{ticket_id}/pdf")
async def generate_boarding_pass(
    ticket_id: int,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Genera boarding pass PDF profesional con QR y código de barras."""
    ticket, passenger, flight, seat = await _fetch_ticket_data(ticket_id, db1, db2)

    pax_name    = (passenger.get("full_name") or "PASAJERO").upper()
    origin      = str(flight.get("origin") or "???").upper()
    destination = str(flight.get("destination") or "???").upper()
    dep_epoch   = int(flight.get("departure_epoch") or 0)
    flight_num  = str(flight.get("flight_number") or flight.get("flight_id") or ticket.get("flight_id", ""))
    seat_num    = str(seat.get("seat_number") or "??")
    raw_class   = str(seat.get("seat_class") or "").upper()
    seat_class  = "FIRST CLASS" if raw_class in ("FIRST", "PRIMERA", "FIRST CLASS") else "ECONOMY"
    gate        = _gate_from_flight(int(ticket.get("flight_id", 1)))
    price       = float(ticket.get("total_price") or 0)
    node_id     = int(ticket.get("node_id") or NODE_ID)
    lamport_ts  = int(ticket.get("lamport_ts") or 0)

    pdf_bytes = _build_boarding_pass_pdf(
        ticket_id, pax_name, origin, destination,
        dep_epoch, flight_num, seat_num, seat_class,
        gate, price, node_id, lamport_ts,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="boarding_pass_{ticket_id}.pdf"'},
    )


# ─── Apple Wallet ─────────────────────────────────────────────────────────────

@app.get("/tickets/{ticket_id}/wallet")
async def generate_wallet_pass(
    ticket_id: int,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Genera archivo .pkpass compatible con Apple Wallet / Google Wallet."""
    ticket, passenger, flight, seat = await _fetch_ticket_data(ticket_id, db1, db2)

    pax_name    = (passenger.get("full_name") or "PASAJERO").upper()
    origin      = str(flight.get("origin") or "???").upper()
    destination = str(flight.get("destination") or "???").upper()
    dep_epoch   = int(flight.get("departure_epoch") or 0)
    flight_num  = str(flight.get("flight_number") or flight.get("flight_id") or ticket.get("flight_id", ""))
    seat_num    = str(seat.get("seat_number") or "??")
    raw_class   = str(seat.get("seat_class") or "").upper()
    seat_class  = "FIRST CLASS" if raw_class in ("FIRST", "PRIMERA", "FIRST CLASS") else "ECONOMY"
    gate        = _gate_from_flight(int(ticket.get("flight_id", 1)))
    price       = float(ticket.get("total_price") or 0)
    node_id     = int(ticket.get("node_id") or NODE_ID)
    lamport_ts  = int(ticket.get("lamport_ts") or 0)

    pkpass_bytes = _build_wallet_pass(
        ticket_id, pax_name, origin, destination,
        dep_epoch, flight_num, seat_num, seat_class,
        gate, price, node_id, lamport_ts,
    )

    return Response(
        content=pkpass_bytes,
        media_type="application/vnd.apple.pkpass",
        headers={"Content-Disposition": f'attachment; filename="boarding_pass_{ticket_id}.pkpass"'},
    )


# ─── Demo ─────────────────────────────────────────────────────────────────────

@app.post("/tickets/generate-demo")
async def generate_demo():
    """Genera un ticket demo con datos ficticios y retorna el boarding pass PDF."""
    import random

    demo_routes = [
        ("ATL", "LON"), ("LAX", "TYO"), ("DFW", "MAD"),
        ("SAO", "FRA"), ("IST", "SIN"), ("PEK", "DXB"),
    ]
    demo_names = [
        "RAFAEL PABÓN TORRES", "VALENTINA GARCÍA RUIZ", "CARLOS MENDOZA SILVA",
        "SOFIA CHEN ZHANG", "OMAR AL-RASHID", "MARIA SANTOS COSTA",
    ]

    origin, destination = random.choice(demo_routes)
    pax_name = random.choice(demo_names)
    dep_epoch   = int(time.time()) + random.randint(86400, 604800)  # 1-7 días
    flight_num  = str(random.randint(1000, 9999))
    seat_num    = f"{random.randint(1, 40)}{random.choice('ABCDEF')}"
    seat_class  = random.choice(["ECONOMY", "FIRST CLASS"])
    gate        = f"{random.choice('ABCDEFGH')}{random.randint(1, 30)}"
    price       = round(random.uniform(150, 2500), 2)

    pdf_bytes = _build_boarding_pass_pdf(
        ticket_id=99999999,
        pax_name=pax_name,
        origin=origin,
        destination=destination,
        dep_epoch=dep_epoch,
        flight_num=flight_num,
        seat_num=seat_num,
        seat_class=seat_class,
        gate=gate,
        price=price,
        node_id=1,
        lamport_ts=42,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="boarding_pass_demo.pdf"'},
    )
