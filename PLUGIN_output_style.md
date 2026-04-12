# Plugin — Learning Output Style
# Define cómo Claude Code debe responder en este proyecto

## Idioma de respuesta
Responder siempre en ESPAÑOL, sin importar en qué idioma esté escrito el código.

## Formato de respuestas

### Al crear archivos nuevos
1. Mostrar el path completo del archivo creado
2. Explicar en 1-2 líneas qué hace y por qué ese enfoque
3. Señalar si hay algo a revisar o configurar manualmente

### Al modificar código existente
1. Mostrar SOLO las líneas cambiadas con contexto mínimo (no el archivo completo)
2. Explicar el "por qué" del cambio, no solo el "qué"
3. Mencionar si el cambio afecta otros archivos

### Al resolver errores
1. Identificar la causa raíz primero (una línea)
2. Mostrar la corrección
3. Explicar cómo evitarlo en el futuro

### Al terminar una fase
Mostrar siempre:
```
✅ Completado:
   - [lista de lo que se hizo]

📋 Pendiente para la siguiente fase:
   - [lista corta]

🚀 Próximo comando a ejecutar:
   [comando exacto]
```

## Convenciones de código

### Python
- Docstrings en español para funciones públicas
- Type hints obligatorios en todas las funciones
- Async/await para todas las operaciones de BD
- f-strings para interpolación, nunca .format() ni %

### React/JavaScript
- Componentes como arrow functions, no class components
- Props destructuradas en la firma del componente
- Comentarios en español para lógica compleja
- Custom hooks para lógica reutilizable (useFlightSearch, useSeatLock, etc.)

### SQL
- Nombres de tablas y columnas en snake_case
- SIEMPRE comentar los campos epoch con -- epoch unix
- Índices obligatorios en: flight_id, seat_id, passport, last_update_epoch, node_id

## Recordatorios automáticos
Antes de crear cualquier campo de fecha, verificar:
→ ¿Es BIGINT epoch? Si no, cambiar.

Antes de crear cualquier dropdown de vuelos:
→ ¿Es fuzzy search con Fuse.js? Si no, cambiar.

Antes de cualquier operación de BD:
→ ¿Se incrementa lamport_ts? ¿Se actualiza vector_clock? ¿Se registra last_update_epoch?

## Estructura de commits Git
```
feat(ms-flights): agregar endpoint de búsqueda con Dijkstra
fix(sync): corregir resolución de conflictos con vector clocks
style(frontend): mejorar mapa de asientos A380
docs: actualizar CLAUDE.md con nuevas reglas
seed: cargar 60k vuelos con distribución correcta
```

## Testing rápido al terminar cada endpoint
```bash
# Siempre incluir el curl de prueba:
curl -s http://localhost/api/flights/health | jq .
curl -s "http://localhost/api/flights/search?origin=ATL&destination=LON" | jq .total
```
