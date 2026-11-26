"""Motor estadístico de RastroHg.

Todo lo de este paquete es Python puro (numpy/scipy/h3): no toca la base de datos ni
Redis. Así se puede probar con datos sintéticos y reutilizar desde el worker, la API o
un notebook.
"""
