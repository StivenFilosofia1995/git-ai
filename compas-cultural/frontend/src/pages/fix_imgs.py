import os
import re

pages = ['Agenda.tsx', 'Aportes.tsx', 'Colectivos.tsx', 'Nosotros.tsx']

for p in pages:
    if os.path.exists(p):
        with open(p, 'r', encoding='utf-8') as f:
            content = f.read()

        # Reemplazar diferentes patrones de imagen ilustracion
        new_content = re.sub(
            r'<img\s+src="/medellin-ilustracion.png".*?/>',
            '<img src="/medellin-ilustracion.png" alt="" aria-hidden="true" className="absolute inset-0 w-full h-full object-contain object-bottom sm:object-right-bottom pointer-events-none select-none opacity-40 mix-blend-multiply" />',
            content,
            flags=re.DOTALL
        )
        if new_content != content:
            with open(p, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated {p}")
