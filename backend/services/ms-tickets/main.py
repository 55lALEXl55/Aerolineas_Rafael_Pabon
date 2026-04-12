"""
ms-tickets — Puerto 8005
Gestión de tickets: consulta, PDF, refund (delay 15 min de propagación).
"""
import io
import os
import time
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db1, get_db2, mongo_db
from models import TicketOut, RefundRequest

app = FastAPI(
    title="ms-tickets",
    description="Microservicio de tickets y PDF — Aerolíneas Rafael Pabón",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_ID = int(os.getenv("NODE_ID", "1"))


def _node_for(ticket_id: int) -> int:
    if ticket_id < 100000:
        return 1
    if ticket_id < 500000:
        return 2
    return 3


@app.get("/health")
async def health():
    return {"service": "ms-tickets", "status": "ok", "node_id": NODE_ID, "timestamp": int(time.time())}


# ─── Consulta de ticket ───────────────────────────────────────────────────────

@app.get("/tickets/{ticket_id}")
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
    row = db.execute(text("SELECT * FROM dbo.tickets WHERE ticket_id=:tid"), {"tid": ticket_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Ticket no encontrado")
    return dict(row)


@app.get("/tickets")
async def list_tickets_by_passport(
    passport_number: str = Query(...),
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Lista todos los tickets de un pasajero por número de pasaporte."""
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
            async for doc in mongo_db.tickets.find({"passenger_id": passenger["passenger_id"]}, {"_id": 0}):
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
    """
    Inicia el proceso de refund.
    Propaga con 15 min de delay (consistencia eventual modelada).
    RESERVED → REFUNDED → AVAILABLE (delay 15 min)
    """
    node = _node_for(ticket_id)
    now = int(time.time())
    refund_propagation_epoch = now + 900  # +15 min

    if node == 3:
        ticket = await mongo_db.tickets.find_one({"ticket_id": ticket_id})
        if not ticket:
            raise HTTPException(404, "Ticket no encontrado")
        if ticket["status"] not in ("PAID", "RESERVED"):
            raise HTTPException(409, f"No se puede hacer refund desde estado {ticket['status']}")
        await mongo_db.tickets.update_one(
            {"ticket_id": ticket_id},
            {"$set": {"status": "REFUNDED", "last_update_epoch": now}}
        )
        # Liberar asiento con delay modelado
        await mongo_db.seats.update_one(
            {"seat_id": ticket["seat_id"]},
            {"$set": {"status": "REFUNDED", "locked_until": refund_propagation_epoch, "last_update_epoch": now}}
        )
    else:
        db = db1 if node == 1 else db2
        row = db.execute(
            text("SELECT status, seat_id FROM dbo.tickets WHERE ticket_id=:tid"),
            {"tid": ticket_id}
        ).fetchone()
        if not row:
            raise HTTPException(404, "Ticket no encontrado")
        if row[0] not in ("PAID", "RESERVED"):
            raise HTTPException(409, f"No se puede hacer refund desde estado {row[0]}")
        db.execute(
            text("UPDATE dbo.tickets SET status='REFUNDED', last_update_epoch=:now WHERE ticket_id=:tid"),
            {"now": now, "tid": ticket_id}
        )
        db.execute(
            text("UPDATE dbo.seats SET status='REFUNDED', locked_until=:lu, last_update_epoch=:now WHERE seat_id=:sid"),
            {"lu": refund_propagation_epoch, "now": now, "sid": row[1]}
        )
        db.commit()

    return {
        "ticket_id": ticket_id,
        "status": "REFUNDED",
        "refund_epoch": now,
        "seat_available_after": refund_propagation_epoch,
        "message": "El asiento quedará disponible en ~15 minutos (consistencia eventual)"
    }


# ─── Generación de PDF ────────────────────────────────────────────────────────

@app.get("/tickets/{ticket_id}/pdf")
async def generate_pdf(
    ticket_id: int,
    db1: Session = Depends(get_db1),
    db2: Session = Depends(get_db2),
):
    """Genera un PDF con los detalles del ticket."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    node = _node_for(ticket_id)
    if node == 3:
        ticket = await mongo_db.tickets.find_one({"ticket_id": ticket_id}, {"_id": 0})
        passenger = await mongo_db.passengers.find_one({"passenger_id": ticket["passenger_id"]}, {"_id": 0}) if ticket else None
        flight = await mongo_db.flights.find_one({"flight_id": ticket["flight_id"]}, {"_id": 0}) if ticket else None
        seat = await mongo_db.seats.find_one({"seat_id": ticket["seat_id"]}, {"_id": 0}) if ticket else None
    else:
        db = db1 if node == 1 else db2
        ticket = db.execute(text("SELECT * FROM dbo.tickets WHERE ticket_id=:tid"), {"tid": ticket_id}).mappings().first()
        if not ticket:
            raise HTTPException(404, "Ticket no encontrado")
        ticket = dict(ticket)
        passenger = db.execute(text("SELECT * FROM dbo.passengers WHERE passenger_id=:pid"), {"pid": ticket["passenger_id"]}).mappings().first()
        passenger = dict(passenger) if passenger else {}

        fdb = db1 if ticket["flight_id"] < 100000 else db2
        flight = fdb.execute(text("SELECT * FROM dbo.flights WHERE flight_id=:fid"), {"fid": ticket["flight_id"]}).mappings().first()
        flight = dict(flight) if flight else {}
        seat = db.execute(text("SELECT * FROM dbo.seats WHERE seat_id=:sid"), {"sid": ticket["seat_id"]}).mappings().first()
        seat = dict(seat) if seat else {}

    if not ticket:
        raise HTTPException(404, "Ticket no encontrado")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("✈ Aerolíneas Rafael Pabón", styles["Title"]))
    story.append(Paragraph("Boleto Electrónico", styles["Heading2"]))
    story.append(Spacer(1, 0.5 * cm))

    data = [
        ["Campo", "Valor"],
        ["Ticket ID", str(ticket_id)],
        ["Estado", str(ticket.get("status", ""))],
        ["Pasajero", str((passenger or {}).get("full_name", ""))],
        ["Pasaporte", str((passenger or {}).get("passport_number", ""))],
        ["Vuelo", f"{(flight or {}).get('origin', '')} → {(flight or {}).get('destination', '')}"],
        ["Número de vuelo", str((flight or {}).get("flight_number", ""))],
        ["Asiento", f"{(seat or {}).get('seat_number', '')} ({(seat or {}).get('seat_class', '')})"],
        ["Precio total", f"${ticket.get('total_price', 0):.2f} USD"],
    ]

    table = Table(data, colWidths=[7 * cm, 10 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("FONTSIZE",   (0, 0), (-1, -1), 10),
        ("PADDING",    (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph("Rafael Pabón nunca se atrasa ni cambia precios.", styles["Italic"]))

    doc.build(story)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=ticket_{ticket_id}.pdf"}
    )
