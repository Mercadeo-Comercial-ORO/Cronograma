# Cronograma de activaciones · ORO

Landing con las próximas salidas de activaciones por ciudad (Organización Radial Olímpica · Mercadeo Comercial).

- Cada ciudad ingresa con su propia contraseña y solo ve sus actividades; la contraseña maestra ve todas.
- Los datos (`data.json`) van cifrados por ciudad (AES-GCM + PBKDF2). Las contraseñas **no** se guardan en este repositorio.
- Se actualiza automáticamente todos los días a las 7:00 a. m. (hora de Colombia) desde el tablero "Control de Propuestas ORO", con `tools/generar.py`.
