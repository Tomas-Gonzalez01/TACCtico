# Funciones ETL de Kiara; no incluye EDA, score ni métricas.
# Notebook SHA256: 964861da39c99bf20fe46a219f2353120fc2f6c975dcb6fb9f7e6f1d49b7c092

import re
import pandas as pd
import numpy as np

def cargar(ruta):
    df = pd.read_csv(ruta)
    vacias = df.columns[df.isna().all()]
    return df.drop(columns=vacias)


def caracteristica(fila, nombre):
    """Devuelve el value de la caracteristica con ese name, o None."""
    for i in range(17):
        if fila.get(f"caracteristicas/{i}/name") == nombre:
            return fila.get(f"caracteristicas/{i}/value")
    return None


def aplanar_caracteristicas(df):
    df = df.copy()
    df["peso_neto_txt"] = df.apply(lambda f: caracteristica(f, "Peso neto"), axis=1)
    df["formato_venta"] = df.apply(lambda f: caracteristica(f, "Formato de venta"), axis=1)
    df["cant_unidades_car"] = pd.to_numeric(
        df.apply(lambda f: caracteristica(f, "Cantidad de unidades"), axis=1), errors="coerce")
    df["libre_gluten"] = df.apply(lambda f: caracteristica(f, "Es libre de gluten"), axis=1)
    return df

def limpiar_basico(df):
    df = df.copy()
    df["titulo"] = df["articuloTitulo"].str.strip()
    df["titulo_norm"] = (df["titulo"].str.lower()
                         .str.replace(r"\s+", " ", regex=True))
    df["precio"] = pd.to_numeric(df["nuevoPrecio"], errors="coerce")
    df["precio_anterior"] = pd.to_numeric(df["precioAnterior"], errors="coerce")
    df["descuento_pct"] = pd.to_numeric(
        df["precioDiscount"].str.extract(r"(\d+)")[0], errors="coerce")
    df["ventas_escalon"] = df["cantidadVendida"]   # viene en escalones, no es exacto
    df["vendedor"] = df["Vendedor"]
    df["marca"] = df["productoMarca"]
    df["reputacion"] = df["reputacionVendedor"]
    df["nivel_vendedor"] = df["estadoVendedorPotente"]   # platinum / gold / silver
    df["tiene_promo"] = df["promociones"].notna()
    df["tienda_oficial"] = df["esTiendaOficial"].astype(bool)
    df["link"] = df["zProductoLink"]
    return df

RE_PESO = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kilos?|kgs?|gramos|grs?|gms|g)\b", re.I)


def a_gramos(valor, unidad):
    v = float(valor.replace(",", "."))
    return v * 1000 if unidad.lower().startswith(("k")) else v


def peso_de_texto(texto):
    """Primer peso encontrado en un texto, en gramos (o NaN)."""
    if not isinstance(texto, str):
        return np.nan
    f = re.search(r"\b(1/4|1/2|3/4)\s*(?:kg|kilo)", texto, re.I)   # "1/4 Kg" = 250 g
    if f:
        return {"1/4": 250.0, "1/2": 500.0, "3/4": 750.0}[f.group(1)]
    m = RE_PESO.search(texto)
    return a_gramos(m.group(1), m.group(2)) if m else np.nan


def extraer_gramos(df):
    """Requiere la columna `unidades` (ver detectar_pack).
    Regla: el titulo manda; la caracteristica "Peso neto" se usa si el titulo no tiene peso.
    Ojo: en packs, "Peso neto" a veces ya es el total del bulto (12 x 500 g = 6000 g)."""
    df = df.copy()
    df["g_caracteristica"] = df["peso_neto_txt"].apply(peso_de_texto)
    df["g_titulo"] = df["titulo"].apply(peso_de_texto)
    c, t, u = df["g_caracteristica"], df["g_titulo"], df["unidades"]
    df["gramos_unidad"] = t.fillna(c)
    df["fuente_peso"] = np.select([t.notna(), c.notna()], ["titulo", "caracteristica"], default="sin_dato")
    ambas = c.notna() & t.notna()
    coincide = np.isclose(c, t) | np.isclose(c, t * u)   # c = unidad, o c = total del pack
    df["peso_discrepa"] = ambas & ~coincide                # estos hay que mirarlos a mano
    return df

PATRONES_PACK = [
    r"pack\s*(?:de\s*)?x?\s*(\d+)(?![.,\d])(?!\s*(?:kg|kgs|kilos?|gr|grs|g|gms)\b)",
    r"\bx\s*(\d+)\s*(?:u|un|unid|unidades)\b",
    r"\b(\d+)\s*(?:unid|unidades)\b",
    r"caja\s*(?:por\s*|de\s*|x\s*)?(\d+)(?![.,\d])(?!\s*(?:kg|kgs|kilos?|gr|grs|g|gms)\b)",
    r"(?<![-\d])\b(\d+)\s*u?\.?\s*x\s*\d+(?:[.,]\d+)?\s*(?:kg|kgs|gr|grs|gms|gs|g)\b",
    r"(?:kg|kgs|gr|grs|gms|g)\s*x\s*(\d+)\b(?!\s*(?:kg|kgs|gr|grs|g|gms)\b)",
    r"\bx\s*(\d+)\s*$",                      # "... 200g X3" al final del titulo
]


def unidades_de_titulo(titulo):
    t = titulo.lower()
    for pat in PATRONES_PACK:
        m = re.search(pat, t)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 100:
                return n
    return np.nan


RE_SOBRES = re.compile(r"(\d+)\s*sobres?\b", re.I)


def sobres_de_titulo(titulo):
    m = RE_SOBRES.search(titulo)
    return int(m.group(1)) if m else np.nan


def detectar_pack(df):
    df = df.copy()
    df["u_titulo"] = df["titulo"].apply(unidades_de_titulo)
    es_pack_car = df["formato_venta"].eq("Pack")
    u_car = df["cant_unidades_car"].where(es_pack_car)
    packs = df["u_titulo"].fillna(u_car).fillna(1)
    sobres = df["titulo"].apply(sobres_de_titulo).fillna(1)   # levadura: "50 sobres x 10 g"
    df["unidades"] = packs * sobres
    df["es_pack"] = packs > 1
    return df


def gramos_totales(df):
    """Si el peso viene solo de la caracteristica y es un pack, no se sabe si es por unidad
    o total del bulto: queda sin calcular (ambiguo) en vez de adivinar."""
    df = df.copy()
    ambiguo = df["fuente_peso"].eq("caracteristica") & (df["unidades"] > 1)
    df["fuente_peso"] = df["fuente_peso"].mask(ambiguo, "ambiguo_en_pack")
    df["gramos_totales"] = (df["gramos_unidad"] * df["unidades"]).mask(ambiguo)
    return df

def precio_por_100g(df):
    df = df.copy()
    df["precio_100g"] = df["precio"] / df["gramos_totales"] * 100
    return df

REGLAS_INSUMO = [  # el orden importa: la primera que coincide gana
    ("levadura_nutricional", r"levadura.*(?:nutricional|cerveza|nutrileva|copos|titan)|(?:nutricional|cerveza|copos|titan).*levadura", False),
    # las premezclas van ANTES que levadura/polvo: muchas premezclas dicen "con levadura" en el titulo
    ("premezcla_otra",       r"(?:pre-?\s?mezcla|mezcla).*(?:macaron|alfajor|\u00f1oqui|noqui|chipa|panqueque|"
                             r"merengue|cheesecake|cheese|brownie|empanada|tapita|fideo|pasta|queso)", False),
    ("premezcla_pizza",      r"(?:pre-?\s?mezcla|mezcla).*pizza|pizza.*(?:pre-?\s?mezcla|mezcla)", True),
    ("premezcla_pan",        r"(?:pre-?\s?mezcla|mezcla).*\bpan\b|\bpan\b.*(?:pre-?\s?mezcla|mezcla)", True),
    ("premezcla_budin",      r"(?:pre-?\s?mezcla|mezcla).*(?:bud[i\u00ed]n|bizcochuelo|bizcocho|cupcake|torta)|"
                             r"(?:bud[i\u00ed]n|bizcochuelo|bizcocho|cupcake|torta).*(?:pre-?\s?mezcla|mezcla)", True),
    ("premezcla_universal",  r"(?:pre-?\s?mezcla|mezcla).*(?:universal|multiuso)", True),
    ("premezcla_sin_clasificar", r"pre-?\s?mezcla|\bmezcla\b", False),   # premezcla que no es de las 3 recetas
    ("levadura",             r"levadura", True),
    ("polvo_hornear",        r"polvo\s+(?:para|de)\s+hornear", True),
    ("chips_chocolate",      r"\bchips?\b|chip's|\bdrops\b|\bgotas\b|\bgotitas\b|chunks", True),
]


def clasificar_insumo(df):
    df = df.copy()
    insumo, en_receta = [], []
    for t in df["titulo_norm"]:
        for nombre, pat, usa in REGLAS_INSUMO:
            if re.search(pat, t):
                insumo.append(nombre); en_receta.append(usa); break
        else:
            insumo.append("otro"); en_receta.append(False)
    df["insumo"] = insumo
    df["en_receta"] = en_receta
    return df

def tipo_vendedor(df):
    df = df.copy()
    nombre = df["vendedor"].fillna("").str.lower()
    df["tipo_vendedor"] = np.select(
        [df["tienda_oficial"],
         nombre.str.contains(r"distribuidora|mayorista|\bdist\b|\bsa\b|\bsrl\b|\bsas\b"),
         df["vendedor"].isna()],
        ["tienda_oficial", "distribuidora", "sin_dato"], default="otro_vendedor")
    return df

def marcar_outliers(df):
    df = df.copy()
    lp = np.log(df["precio_100g"])
    q1 = lp.groupby(df["insumo"]).transform(lambda x: x.quantile(0.25))
    q3 = lp.groupby(df["insumo"]).transform(lambda x: x.quantile(0.75))
    iqr = q3 - q1
    df["outlier_precio"] = (lp < q1 - 1.5 * iqr) | (lp > q3 + 1.5 * iqr)
    return df

def marcar_duplicados(df):
    df = df.copy()
    df["duplicado_titulo_vendedor"] = df.duplicated(["titulo_norm", "vendedor"], keep="first")
    return df


def calidad(df):
    n = len(df)
    util = df["precio_100g"].notna() & df["en_receta"] & ~df["duplicado_titulo_vendedor"]
    pasos = {
        "filas de entrada": n,
        "con gramos conocidos": int(df["gramos_unidad"].notna().sum()),
        "con precio por 100 g": int(df["precio_100g"].notna().sum()),
        "en una de las 3 recetas": int(df["en_receta"].sum()),
        "duplicados titulo+vendedor": int(df["duplicado_titulo_vendedor"].sum()),
        "pesos que discrepan (revisar)": int(df["peso_discrepa"].sum()),
        "pesos ambiguos en pack (sin calcular)": int(df["fuente_peso"].eq("ambiguo_en_pack").sum()),
        "outliers de precio por 100 g (revisar)": int(df["outlier_precio"].sum()),
        "FILAS UTILES para el analisis": int(util.sum()),
    }
    return pd.Series(pasos), util


def etl(ruta):
    df = cargar(ruta)
    df = aplanar_caracteristicas(df)
    df = limpiar_basico(df)
    df = detectar_pack(df)
    df = extraer_gramos(df)
    df = gramos_totales(df)
    df = precio_por_100g(df)
    df = clasificar_insumo(df)
    df = tipo_vendedor(df)
    df = marcar_duplicados(df)
    df = marcar_outliers(df)
    return df


COLUMNAS_SALIDA = [
    "idPublicacion", "busqueda", "insumo", "en_receta", "titulo", "marca", "vendedor",
    "tipo_vendedor", "reputacion", "nivel_vendedor", "tienda_oficial", "precio", "precio_anterior",
    "descuento_pct", "tiene_promo", "ventas_escalon", "gramos_unidad", "unidades",
    "es_pack", "gramos_totales", "precio_100g", "fuente_peso", "peso_discrepa",
    "duplicado_titulo_vendedor", "outlier_precio", "link",
]
