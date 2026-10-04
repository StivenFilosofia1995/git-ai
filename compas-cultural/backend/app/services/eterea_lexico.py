"""
Léxico de ETÉREA: los ejes del "ars combinatoria".

Cada pregunta se descompone en ejes independientes y la respuesta es la combinación:
  INTENCIÓN × QUÉ (tipo de plan) × CUÁNDO (fecha / franja / festividad) × DÓNDE (municipio /
  zona / barrio / lugar / cerca) × CUÁNTO (gratis / tope) × PARA QUIÉN × CAMPO (hora, precio…)
  × REFERENCIA ("el segundo", "ese").

Todo en minúsculas y sin tildes (se compara contra texto normalizado con `norm`).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional


def norm(s: Optional[str]) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def hay(t: str, *frases: str) -> bool:
    """¿Alguna frase aparece como palabras completas en el texto normalizado `t` (con espacios a los lados)?"""
    return any(f" {f} " in t for f in frases)


# ─── Intenciones sociales y del sitio ─────────────────────────────────────
SALUDOS = ("hola", "holi", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hey", "ey", "que mas",
           "quiubo", "q mas", "saludos", "alo", "hello", "hi")
GRACIAS = ("gracias", "muchas gracias", "mil gracias", "te agradezco", "genial gracias", "thanks", "listo gracias",
           "chevere", "bacano", "perfecto", "excelente", "super")
DESPEDIDAS = ("chao", "adios", "nos vemos", "hasta luego", "bye", "me voy", "hasta pronto")
COMO_ESTAS = ("como estas", "como vas", "como te va", "todo bien", "que tal")
QUIEN_ERES = ("quien eres", "quien sos", "que eres", "que sos", "como te llamas", "eres una ia", "sos una ia",
              "eres un bot", "sos un bot", "eres humano", "sos humana", "quien te hizo", "quien te creo")
QUE_PUEDES = ("que puedes hacer", "que podes hacer", "que sabes hacer", "como funciona", "como funcionas", "ayuda",
              "help", "que te puedo preguntar", "que preguntas", "como te uso", "instrucciones", "menu")
INSULTOS = ("idiota", "estupida", "estupido", "inutil", "malparida", "malparido", "gonorrea", "no sirves",
            "no servis", "no sirve", "basura", "tonta", "tonto", "mierda", "pesima", "pesimo")
CHISTE = ("chiste", "cuentame algo gracioso", "hazme reir", "algo chistoso")

SITIO = {
    "publicar": (("publicar", "subir mi evento", "subir un evento", "publico mi evento", "anunciar mi evento",
                  "promocionar mi evento", "agregar un evento", "agregar mi evento", "difundir mi evento",
                  "como publico", "quiero publicar", "poner mi evento"), "/publicar"),
    "registrar": (("registrar mi espacio", "registrar un espacio", "registrar mi colectivo", "registrar mi lugar",
                   "agregar mi espacio", "inscribir mi colectivo", "mi colectivo no aparece", "mi espacio no aparece",
                   "sumar mi colectivo", "registrar colectivo"), "/registrar"),
    "boletin": (("boletin", "newsletter", "correo semanal", "suscribirme", "suscribir", "recibir la agenda",
                 "agenda por correo", "me llegue la agenda", "mails", "correos"), "/login"),
    "baja": (("darme de baja", "no quiero mas correos", "desuscribir", "cancelar suscripcion", "dejar de recibir"),
             None),
    "cuenta": (("crear cuenta", "registrarme", "iniciar sesion", "login", "mi cuenta", "mi perfil",
                "contrasena", "olvide mi clave", "olvide la contrasena"), "/login"),
    "eliminar_cuenta": (("eliminar mi cuenta", "borrar mi cuenta", "borrar mis datos", "eliminar mis datos"),
                        "/eliminar-cuenta"),
    "guardados": (("guardados", "mis guardados", "favoritos", "guardar evento", "guardar un evento", "mis planes"),
                  "/guardados"),
    "app": (("app", "aplicacion", "descargar", "android", "iphone", "play store", "instalar"), "/descargar"),
    "aportar": (("aportar", "donar", "donacion", "vaki", "apoyar el proyecto", "colaborar con el proyecto",
                 "como apoyo", "como ayudo"), "/aportes"),
    "nosotros": (("quienes son", "quien esta detras", "sobre ustedes", "que es cultura eterea", "el proyecto",
                  "nosotros", "equipo"), "/nosotros"),
    "mapa": (("mapa", "ver el mapa", "mapa cultural"), "/mapa"),
    "privacidad": (("privacidad", "proteccion de datos", "mis datos", "habeas data", "ley 1581"),
                   "/proteccion-datos"),
    "contacto": (("contacto", "contactarlos", "escribirles", "correo de ustedes", "whatsapp", "telefono de ustedes",
                  "hablar con alguien", "reportar un error", "reportar error", "un evento esta mal",
                  "informacion incorrecta"), "/nosotros"),
}

FUERA_DE_TEMA = ("clima", "temperatura", "va a llover", "pronostico", "futbol", "partido de", "nacional",
                 "medellin dim", "dim", "receta", "cocinar", "politica", "presidente", "elecciones", "dolar",
                 "bitcoin", "tarea", "matematicas", "traduce", "traducir", "programar", "codigo", "noticias",
                 "trafico", "pico y placa", "horoscopo", "loteria")

# ─── Campos que se pueden preguntar de un evento o de un lugar ───────────
CAMPOS_EVENTO = {
    "hora": ("a que hora", "que hora", "hora", "horario", "a q hora", "cuando empieza", "cuando inicia",
             "a que horas", "empieza", "arranca"),
    "fecha": ("que dia", "cuando es", "cuando sera", "en que fecha", "fecha", "cuando"),
    "lugar": ("donde es", "donde sera", "en donde", "donde queda", "donde", "en que lugar", "que lugar",
              "lugar", "sitio"),
    "precio": ("cuanto cuesta", "cuanto vale", "cuanto es", "precio", "valor", "costo", "es gratis",
               "hay que pagar", "se paga", "cobran", "boleta cuesta"),
    "entradas": ("entradas", "boletas", "boleteria", "tiquetes", "tickets", "comprar", "reservar", "reserva",
                 "inscribirme", "inscripcion", "inscribir", "cupos", "registrarme al evento", "link", "enlace"),
    "llegar": ("como llego", "como llegar", "como voy", "ruta", "ubicacion", "direccion", "mapa", "en metro",
               "en bus", "parqueadero"),
    "descripcion": ("de que se trata", "de que trata", "que es", "info", "informacion", "mas info",
                    "detalles", "cuentame", "contame", "explicame", "descripcion", "que hacen", "de que va"),
    "duracion": ("hasta cuando", "cuanto dura", "a que hora termina", "cuando termina", "termina", "dura"),
    "publico": ("para ninos", "es para ninos", "para que edad", "edad", "puedo llevar", "es apto", "para quien"),
}
CAMPOS_LUGAR = {
    "direccion": ("donde queda", "direccion", "donde esta", "ubicacion", "en que barrio", "donde es"),
    "llegar": ("como llego", "como llegar", "como voy", "ruta"),
    "instagram": ("instagram", "insta", "ig", "redes", "redes sociales"),
    "web": ("pagina", "pagina web", "sitio web", "web", "link", "enlace"),
    "telefono": ("telefono", "celular", "numero", "whatsapp", "contacto"),
    "horario": ("horario", "a que hora abre", "a que hora cierra", "abre", "cierra", "abren", "cierran"),
    "descripcion": ("que es", "que hacen", "de que se trata", "info", "informacion", "cuentame", "contame",
                    "quienes son"),
}

# ─── Referencias a resultados anteriores ─────────────────────────────────
ORDINALES = {"primero": 0, "primer": 0, "primera": 0, "1": 0, "uno": 0, "segundo": 1, "segunda": 1, "2": 1,
             "dos": 1, "tercero": 2, "tercer": 2, "tercera": 2, "3": 2, "tres": 2, "cuarto": 3, "cuarta": 3,
             "4": 3, "quinto": 4, "quinta": 4, "5": 4, "sexto": 5, "sexta": 5, "6": 5}
DEICTICOS = ("ese", "esa", "eso", "ese evento", "ese plan", "ese lugar", "ese sitio", "el ultimo", "la ultima",
             "ultimo", "ultima", "este", "esta")

# ─── Recomendación, conteo y listados de lugares ─────────────────────────
RECOMENDAR = ("recomienda", "recomiendame", "recomendame", "recomendas", "recomiendas", "sugiere", "sugerime",
              "sugiereme", "sorprendeme", "sorprende", "que me recomiendas", "que hago", "que puedo hacer",
              "no se que hacer", "estoy aburrido", "estoy aburrida", "aburrido", "aburrida", "algo diferente",
              "algo distinto", "imperdible", "imperdibles", "lo mejor", "el mejor", "vale la pena", "plan bueno",
              "un plan", "dame un plan", "dame una idea", "una idea", "antojado", "antojada", "parche", "parchar",
              "a donde voy", "a donde ir", "pa donde", "que hay bueno")
CONTAR = ("cuantos", "cuantas", "cantidad de", "numero de", "cuanto evento", "cuantos eventos", "cuantos planes")
LUGARES_PREGUNTA = ("donde hay", "donde puedo", "lugares", "lugar para", "sitios", "sitio para", "espacios",
                    "espacio para", "que lugares", "que sitios", "conoces", "recomiendame un lugar",
                    "dime lugares", "colectivos", "colectivo", "grupos de", "academias", "academia",
                    "escuelas de", "escuela de", "donde aprender", "donde estudiar", "bibliotecas", "teatros",
                    "museos", "galerias", "casas de la cultura", "casa de la cultura", "bares", "librerias",
                    "uvas", "centros culturales")
# tipo de lugar → (tipos en `lugares.tipo`, raíces en el nombre)
TIPOS_LUGAR = {
    "teatros": ({"teatro"}, ("teatro",)),
    "bibliotecas": ({"biblioteca"}, ("biblioteca",)),
    "museos": ({"museo"}, ("museo",)),
    "galerías": ({"galeria"}, ("galeria",)),
    "casas de la cultura": ({"casa_cultura"}, ("casa de la cultura",)),
    "centros culturales": ({"centro_cultural"}, ("centro cultural",)),
    "colectivos": ({"colectivo"}, ()),
    "bares culturales": ({"bar", "cafe"}, ("bar ", "cafe")),
    "librerías": ({"libreria"}, ("libreria",)),
    "editoriales": ({"editorial"}, ("editorial",)),
    "UVA": ({"uva"}, ("uva ",)),
    "parques culturales": ({"parque_cultural", "parque"}, ("parque",)),
    "universidades": ({"universidad"}, ("universidad",)),
    "festivales": ({"festival"}, ("festival",)),
}
DISPARA_TIPO_LUGAR = {
    "teatros": ("teatro", "teatros", "sala de teatro", "salas de teatro"),
    "bibliotecas": ("biblioteca", "bibliotecas"),
    "museos": ("museo", "museos"),
    "galerías": ("galeria", "galerias"),
    "casas de la cultura": ("casa de la cultura", "casas de la cultura", "casa de cultura"),
    "centros culturales": ("centro cultural", "centros culturales"),
    "colectivos": ("colectivo", "colectivos", "grupo", "grupos", "agrupacion", "agrupaciones", "combo",
                   "parche cultural", "organizaciones"),
    "bares culturales": ("bar", "bares", "cafe", "cafes", "cafe bar"),
    "librerías": ("libreria", "librerias"),
    "editoriales": ("editorial", "editoriales"),
    "UVA": ("uva", "uvas"),
    "parques culturales": ("parque", "parques"),
    "universidades": ("universidad", "universidades", "u"),
}

# ─── Para quién ──────────────────────────────────────────────────────────
PUBLICOS = {
    "niños": (("ninos", "nino", "ninas", "nina", "infantil", "hijos", "hija", "hijo", "bebes", "bebe", "familia",
               "familiar", "chiquitos", "pequenos", "sobrinos", "primera infancia"),
              ("infantil", "nino", "ninas", "familia", "familiar", "primera infancia", "bebe", "pequenos")),
    "jóvenes": (("jovenes", "joven", "adolescentes", "adolescente", "pelados", "chicos", "universitarios"),
                ("joven", "jovenes", "adolescente", "juvenil")),
    "personas mayores": (("abuelos", "abuela", "abuelo", "adultos mayores", "adulto mayor", "tercera edad",
                          "personas mayores", "mayores"),
                         ("adulto mayor", "adultos mayores", "persona mayor", "personas mayores", "tercera edad")),
    "pareja": (("pareja", "novia", "novio", "cita", "date", "romantico", "romantica", "esposa", "esposo",
                "enamorados"), ()),
    "amigos": (("amigos", "amigas", "parceros", "parceras", "combo de amigos", "parche de amigos"), ()),
    "mascotas": (("mascota", "mascotas", "perro", "perros", "gato", "gatos", "perrito"),
                 ("mascota", "perro", "gato", "pet friendly", "animales")),
    "mujeres": (("mujeres", "mujer", "feminista", "feministas"), ("mujer", "mujeres", "femin")),
}
# Para una cita: planes que suelen funcionar
TIPOS_PAREJA = ("música", "cine", "teatro", "arte", "danza")

# ─── Cuándo: franjas, festividades, meses ────────────────────────────────
MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
         "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
         "ene": 1, "feb": 2, "mar": 3, "abr": 4, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "sept": 9, "oct": 10,
         "nov": 11, "dic": 12}
FRANJAS = {
    "en la manana": (6, 12, "en la mañana"), "por la manana": (6, 12, "en la mañana"),
    "temprano": (6, 12, "temprano"), "al mediodia": (11, 14, "al mediodía"),
    "en la tarde": (12, 18, "en la tarde"), "por la tarde": (12, 18, "en la tarde"),
    "en la noche": (17, 24, "en la noche"), "por la noche": (17, 24, "en la noche"),
    "nocturno": (17, 24, "en la noche"), "nocturnos": (17, 24, "en la noche"),
    "de noche": (17, 24, "en la noche"), "despues del trabajo": (17, 24, "después del trabajo"),
    "saliendo del trabajo": (17, 24, "después del trabajo"), "despues de clase": (16, 24, "después de clase"),
    "trasnocho": (21, 24, "tarde en la noche"), "madrugada": (0, 6, "de madrugada"),
}
FESTIVIDADES = {  # nombre → (mes, día inicial, días, etiqueta)
    "halloween": (10, 31, 1, "Halloween"), "dia de los ninos": (10, 31, 1, "el Día de los Niños"),
    "noche de brujas": (10, 31, 1, "Halloween"), "navidad": (12, 16, 10, "Navidad"),
    "novena": (12, 16, 9, "las novenas"), "novenas": (12, 16, 9, "las novenas"),
    "alumbrados": (12, 1, 31, "los alumbrados"), "fin de ano": (12, 26, 6, "fin de año"),
    "ano nuevo": (12, 31, 2, "año nuevo"), "amor y amistad": (9, 15, 7, "amor y amistad"),
    "feria de las flores": (8, 1, 10, "la Feria de las Flores"), "semana santa": (3, 29, 7, "Semana Santa"),
    "dia de la madre": (5, 8, 3, "el Día de la Madre"), "dia del padre": (6, 18, 3, "el Día del Padre"),
}

# Al pedir una festividad, lo que la nombra sube al principio (sin ocultar lo demás)
REALCE_FESTIVIDAD = {
    "halloween": ("halloween", "brujas", "disfraz", "terror", "miedo", "zombi", "calabaza", "monstruo"),
    "noche de brujas": ("halloween", "brujas", "disfraz", "terror", "miedo"),
    "dia de los ninos": ("nino", "ninos", "infantil", "familia", "disfraz"),
    "navidad": ("navidad", "navide", "novena", "pesebre", "villancico", "aguinaldo"),
    "novena": ("novena", "navidad", "pesebre"), "novenas": ("novena", "navidad", "pesebre"),
    "alumbrados": ("alumbrado", "luces", "navidad"),
    "amor y amistad": ("amor", "amistad", "romant", "pareja"),
    "feria de las flores": ("flores", "silleta", "feria", "trova"),
}

# ─── Precio ──────────────────────────────────────────────────────────────
GRATIS = ("gratis", "gratuito", "gratuita", "gratuitos", "gratuitas", "sin costo", "free", "entrada libre",
          "sin pagar", "no pagar", "de balde", "regalado", "sin plata", "no tengo plata", "estoy pelado",
          "estoy pelada", "sin un peso", "cero pesos")
BARATO = ("barato", "barata", "baratos", "baratas", "economico", "economica", "economicos", "poca plata",
          "bajo presupuesto", "que no sea caro", "no muy caro", "accesible", "accesibles")
TOPE_BARATO = 20000
VIRTUAL = ("virtual", "virtuales", "online", "en linea", "por zoom", "desde la casa", "desde casa", "streaming",
           "transmision")
SIN_INSCRIPCION = ("sin inscripcion", "sin registro", "sin reserva", "sin reservar", "llegar y entrar",
                   "entrada libre")

# ─── Cantidad / orden ────────────────────────────────────────────────────
TODOS = ("todos", "todas", "todo lo que hay", "la lista completa", "lista completa", "todo")
UNO_SOLO = ("uno solo", "solo uno", "un plan", "una opcion", "el mejor", "lo mejor", "uno")
PROXIMO = ("lo mas pronto", "el mas pronto", "el proximo", "la proxima", "el siguiente", "lo que sigue",
           "que viene ya", "ya mismo", "ahorita", "ahora")

# Palabras que no aportan al texto libre (se suman a las de eterea_buscador)
VACIAS_EXTRA = set("""quiero queremos podria podrias podes puedes sabes saber dime decime dame muestrame mostrame
cuentame contame alguno alguna ningun ninguna mucho mucha poco poca otro otra otros otras tambien entonces luego
despues antes durante ahora ahorita pues bueno vale listo gracias porfa favor cosas cosa onda nota chimba bacano
chevere parce parcero parcera mano llave ome oiga oye mira vea mijo mija hacer ir ver salir buscar encontrar
conocer visitar asistir disfrutar pasar rato tiempo libre vida ciudad aqui aca alla alli cual cuales quien quienes
cuanto cuanta cuantos cuantas mas menos muy tan algo nada evento eventos plan planes actividad actividades""".split())


def _palabras(*grupos) -> set[str]:
    out = set()
    for g in grupos:
        items = g.values() if isinstance(g, dict) else g
        for x in items:
            for frase in (x if isinstance(x, tuple) else (x,)):
                if isinstance(frase, str):
                    out.update(frase.split())
    return out


# Palabras que dirigen la conversación (no son tema de búsqueda): nunca van al texto libre
PALABRAS_DE_CONTROL = _palabras(
    SALUDOS, GRACIAS, DESPEDIDAS, COMO_ESTAS, QUIEN_ERES, QUE_PUEDES, RECOMENDAR, CONTAR, LUGARES_PREGUNTA,
    CAMPOS_EVENTO, CAMPOS_LUGAR, DEICTICOS, tuple(ORDINALES), GRATIS, BARATO, VIRTUAL, SIN_INSCRIPCION, TODOS,
    UNO_SOLO, PROXIMO, tuple(FRANJAS), tuple(FESTIVIDADES), tuple(MESES),
) | {"comuna", "zona", "barrio", "sector", "municipio", "mil", "pesos", "plata", "tengo", "hay", "puedo",
     "quisiera", "opciones", "ideas", "lista", "algun", "alguna", "alguno", "sea", "cosa", "pa", "pal"}

# Frases que son tipos de plan o de lugar: un lugar no puede "llamarse" así para el reconocedor
FRASES_DE_TIPO = {f for fr in DISPARA_TIPO_LUGAR.values() for f in fr} | \
                 {f for (d, _) in PUBLICOS.values() for f in d}
