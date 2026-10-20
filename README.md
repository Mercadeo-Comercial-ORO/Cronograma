# Cronograma de activaciones · ORO

Landing con las próximas salidas de activaciones por ciudad (Organización Radial Olímpica · Mercadeo Comercial).

- Cada ciudad ingresa con su propia contraseña y solo ve sus actividades; la contraseña maestra ve todas.
- Los datos (`data.json`) van cifrados por ciudad (AES-GCM + PBKDF2). Las contraseñas **no** se guardan en este repositorio.
- Se actualiza automáticamente todos los días a las 7:00 a. m. (hora de Colombia) desde el tablero "Control de Propuestas ORO", con `tools/generar.py`.
- Las salidas del cliente Kimby (fechas, horario, PDV, dirección y barrio) se toman del tablero "Control Merch Kimby" (`--kimby`).
- `tools/sincronizar.py` copia las fechas de los tableros "Control Merch Kimby" y "Control Merch Buscapina" al tablero "Control de Propuestas ORO" (cronograma de propuestas) antes de generar la landing, para que ambos muestren siempre las mismas salidas.

## Activación Kimby (`/kimby/`)

Landing para el cliente Kimby con los resultados de la activación (pestaña "Kimby" del tablero "Control Merch Kimby"): avance, ventas, merch proyectado vs. entregado, entregas por ciudad y fecha, y merch disponible y en tránsito por ciudad.

- Una sola contraseña para el cliente. Los datos (`kimby/data.json`) van cifrados (AES-GCM + PBKDF2); la contraseña **no** se guarda en este repositorio.
- No incluye textos de informes, novedades, fotos, ubicaciones ni descargas.
- Se actualiza todos los lunes a las 11:55 a. m. (hora de Colombia) con `tools/kimby.py`.
