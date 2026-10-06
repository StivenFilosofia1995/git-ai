# ig_local — agenda de Instagram desde tu computador

Instagram no deja que el servidor lea los perfiles. Este programa los lee en **tu** PC,
con **tu** sesión, y sube las publicaciones a Cultura ETÉREA. El servidor extrae los
eventos con las reglas de siempre (`ig_precision`, sin IA) y los publica.

## Instalar (una vez)

```
cd compas-cultural/tools/ig_local
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env      # y pega SCRAPER_API_KEY (Railway → Variables)
```

## Usar

Doble clic en `traer_agenda.bat`, o:

```
python ig_local.py                 # 40 perfiles, rotando (los menos visitados primero)
python ig_local.py --max 15
python ig_local.py --solo birra.latina mulenzesalsabar
python ig_local.py --subir archivo.json   # subir una captura hecha por Claude
```

La primera vez se abre una ventana de Chromium: **inicia sesión en Instagram a mano**.
La sesión queda guardada en `perfil_navegador/` (no se sube a git).

## Cuidar tu cuenta

- Va despacio a propósito: 25–50 s entre perfiles, 40 por corrida (~30 min).
- Si Instagram pide una pausa, el programa se detiene solo. Retómalo al día siguiente.
- Mejor una cuenta secundaria que siga a los lugares, no tu cuenta personal principal.
- Una corrida al día alcanza: rota sola por los ~900 lugares.
