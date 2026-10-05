"""
config/wind_turbine_database.py
================================
Base de datos de aerogeneradores para el modelo eolico.

La filosofia es deliberadamente equivalente a ``config/pv_database.py``:
el catalogo concentra los datos de fabricante y el modelo de simulacion los
consume sin hardcodear aerogeneradores en la interfaz.

IMPORTANTE SOBRE LAS CURVAS
---------------------------
* ``manufacturer_table``: valores tabulados directamente en el documento.
* ``datasheet_graph_digitized``: valores digitalizados de la grafica del
  datasheet. Son apropiados para simulacion energetica, pero no deben
  interpretarse como una tabla certificada del fabricante.
* ``derived_from_curve``: parametro inferido de la propia curva (por ejemplo,
  la primera velocidad que alcanza Pnom).
* ``not_provided``: el dato no aparece de forma utilizable en el material
  suministrado. No se inventa un valor.

El factor de capacidad (FC) NO pertenece a esta base de datos: depende del
perfil de viento y del horizonte de simulacion. Se calculara como

    FC = E / (P_instalada * Delta_t)

en el modulo de simulacion.

Las velocidades de viento se consideran a altura de buje/nacelle. La v1 del
modelo no realiza correccion por altura.
"""

from __future__ import annotations

from copy import deepcopy
from math import pi
from typing import Dict, List, Optional, Tuple


CUSTOM_KEY = "Personalizado"
DEFAULT_REFERENCE_AIR_DENSITY = 1.225  # kg/m3

PowerPoint = Tuple[float, float]  # (m/s, kW)


def _area_from_diameter(diameter_m: float) -> float:
    return pi * (diameter_m / 2.0) ** 2


def _plateau(start: int, end: int, power_kw: float) -> List[PowerPoint]:
    return [(float(v), float(power_kw)) for v in range(start, end + 1)]


# ---------------------------------------------------------------------------
# Curvas de potencia a densidad de referencia
# ---------------------------------------------------------------------------

# Nordex N117/2400: columna rho = 1.225 kg/m3 de la tabla del fabricante.
# Datos exactos del documento suministrado (0.5 m/s).
_NORDEX_N117_2400_CURVE: List[PowerPoint] = [
    (3.0, 25), (3.5, 82), (4.0, 154), (4.5, 244),
    (5.0, 354), (5.5, 486), (6.0, 643), (6.5, 827),
    (7.0, 1038), (7.5, 1272), (8.0, 1525), (8.5, 1794),
    (9.0, 2037), (9.5, 2211), (10.0, 2326), (10.5, 2386),
    (11.0, 2400), (11.5, 2400), (12.0, 2400), (12.5, 2400),
    (13.0, 2400), (13.5, 2400), (14.0, 2400), (14.5, 2400),
    (15.0, 2400), (15.5, 2400), (16.0, 2400), (16.5, 2400),
    (17.0, 2400), (17.5, 2400), (18.0, 2400), (18.5, 2400),
    (19.0, 2400), (19.5, 2400), (20.0, 2400),
]


# Tabla completa del fabricante para distintas densidades de aire (kg/m3).
# Permite que el futuro modelo use interpolacion 2D en lugar de una correccion
# generica cuando se seleccione el N117/2400.
_NORDEX_N117_DENSITY_CURVES: Dict[float, List[PowerPoint]] = {1.0: [(3.0, 13),
       (3.5, 60),
       (4.0, 119),
       (4.5, 193),
       (5.0, 282),
       (5.5, 389),
       (6.0, 516),
       (6.5, 665),
       (7.0, 838),
       (7.5, 1029),
       (8.0, 1235),
       (8.5, 1449),
       (9.0, 1666),
       (9.5, 1864),
       (10.0, 2044),
       (10.5, 2206),
       (11.0, 2306),
       (11.5, 2367),
       (12.0, 2395),
       (12.5, 2400),
       (13.0, 2400),
       (13.5, 2400),
       (14.0, 2400),
       (14.5, 2400),
       (15.0, 2400),
       (15.5, 2400),
       (16.0, 2400),
       (16.5, 2400),
       (17.0, 2400),
       (17.5, 2400),
       (18.0, 2400),
       (18.5, 2400),
       (19.0, 2400),
       (19.5, 2400),
       (20.0, 2400)],
 1.025: [(3.0, 15),
         (3.5, 63),
         (4.0, 123),
         (4.5, 198),
         (5.0, 290),
         (5.5, 400),
         (6.0, 530),
         (6.5, 684),
         (7.0, 860),
         (7.5, 1056),
         (8.0, 1267),
         (8.5, 1487),
         (9.0, 1710),
         (9.5, 1916),
         (10.0, 2106),
         (10.5, 2240),
         (11.0, 2330),
         (11.5, 2382),
         (12.0, 2399),
         (12.5, 2400),
         (13.0, 2400),
         (13.5, 2400),
         (14.0, 2400),
         (14.5, 2400),
         (15.0, 2400),
         (15.5, 2400),
         (16.0, 2400),
         (16.5, 2400),
         (17.0, 2400),
         (17.5, 2400),
         (18.0, 2400),
         (18.5, 2400),
         (19.0, 2400),
         (19.5, 2400),
         (20.0, 2400)],
 1.05: [(3.0, 16),
        (3.5, 65),
        (4.0, 127),
        (4.5, 204),
        (5.0, 298),
        (5.5, 411),
        (6.0, 544),
        (6.5, 702),
        (7.0, 883),
        (7.5, 1083),
        (8.0, 1299),
        (8.5, 1525),
        (9.0, 1754),
        (9.5, 1967),
        (10.0, 2151),
        (10.5, 2270),
        (11.0, 2351),
        (11.5, 2393),
        (12.0, 2400),
        (12.5, 2400),
        (13.0, 2400),
        (13.5, 2400),
        (14.0, 2400),
        (14.5, 2400),
        (15.0, 2400),
        (15.5, 2400),
        (16.0, 2400),
        (16.5, 2400),
        (17.0, 2400),
        (17.5, 2400),
        (18.0, 2400),
        (18.5, 2400),
        (19.0, 2400),
        (19.5, 2400),
        (20.0, 2400)],
 1.075: [(3.0, 17),
         (3.5, 67),
         (4.0, 131),
         (4.5, 210),
         (5.0, 306),
         (5.5, 422),
         (6.0, 559),
         (6.5, 720),
         (7.0, 905),
         (7.5, 1110),
         (8.0, 1332),
         (8.5, 1563),
         (9.0, 1799),
         (9.5, 2017),
         (10.0, 2182),
         (10.5, 2291),
         (11.0, 2363),
         (11.5, 2395),
         (12.0, 2400),
         (12.5, 2400),
         (13.0, 2400),
         (13.5, 2400),
         (14.0, 2400),
         (14.5, 2400),
         (15.0, 2400),
         (15.5, 2400),
         (16.0, 2400),
         (16.5, 2400),
         (17.0, 2400),
         (17.5, 2400),
         (18.0, 2400),
         (18.5, 2400),
         (19.0, 2400),
         (19.5, 2400),
         (20.0, 2400)],
 1.1: [(3.0, 19),
       (3.5, 70),
       (4.0, 134),
       (4.5, 216),
       (5.0, 314),
       (5.5, 433),
       (6.0, 573),
       (6.5, 738),
       (7.0, 928),
       (7.5, 1137),
       (8.0, 1364),
       (8.5, 1601),
       (9.0, 1844),
       (9.5, 2058),
       (10.0, 2215),
       (10.5, 2319),
       (11.0, 2378),
       (11.5, 2398),
       (12.0, 2400),
       (12.5, 2400),
       (13.0, 2400),
       (13.5, 2400),
       (14.0, 2400),
       (14.5, 2400),
       (15.0, 2400),
       (15.5, 2400),
       (16.0, 2400),
       (16.5, 2400),
       (17.0, 2400),
       (17.5, 2400),
       (18.0, 2400),
       (18.5, 2400),
       (19.0, 2400),
       (19.5, 2400),
       (20.0, 2400)],
 1.125: [(3.0, 20),
         (3.5, 72),
         (4.0, 138),
         (4.5, 221),
         (5.0, 322),
         (5.5, 443),
         (6.0, 587),
         (6.5, 756),
         (7.0, 950),
         (7.5, 1164),
         (8.0, 1396),
         (8.5, 1639),
         (9.0, 1889),
         (9.5, 2098),
         (10.0, 2246),
         (10.5, 2341),
         (11.0, 2390),
         (11.5, 2400),
         (12.0, 2400),
         (12.5, 2400),
         (13.0, 2400),
         (13.5, 2400),
         (14.0, 2400),
         (14.5, 2400),
         (15.0, 2400),
         (15.5, 2400),
         (16.0, 2400),
         (16.5, 2400),
         (17.0, 2400),
         (17.5, 2400),
         (18.0, 2400),
         (18.5, 2400),
         (19.0, 2400),
         (19.5, 2400),
         (20.0, 2400)],
 1.15: [(3.0, 21),
        (3.5, 75),
        (4.0, 142),
        (4.5, 227),
        (5.0, 330),
        (5.5, 454),
        (6.0, 601),
        (6.5, 774),
        (7.0, 972),
        (7.5, 1191),
        (8.0, 1428),
        (8.5, 1678),
        (9.0, 1928),
        (9.5, 2129),
        (10.0, 2268),
        (10.5, 2355),
        (11.0, 2395),
        (11.5, 2400),
        (12.0, 2400),
        (12.5, 2400),
        (13.0, 2400),
        (13.5, 2400),
        (14.0, 2400),
        (14.5, 2400),
        (15.0, 2400),
        (15.5, 2400),
        (16.0, 2400),
        (16.5, 2400),
        (17.0, 2400),
        (17.5, 2400),
        (18.0, 2400),
        (18.5, 2400),
        (19.0, 2400),
        (19.5, 2400),
        (20.0, 2400)],
 1.175: [(3.0, 22),
         (3.5, 77),
         (4.0, 146),
         (4.5, 233),
         (5.0, 338),
         (5.5, 465),
         (6.0, 615),
         (6.5, 792),
         (7.0, 994),
         (7.5, 1218),
         (8.0, 1460),
         (8.5, 1716),
         (9.0, 1964),
         (9.5, 2157),
         (10.0, 2287),
         (10.5, 2365),
         (11.0, 2397),
         (11.5, 2400),
         (12.0, 2400),
         (12.5, 2400),
         (13.0, 2400),
         (13.5, 2400),
         (14.0, 2400),
         (14.5, 2400),
         (15.0, 2400),
         (15.5, 2400),
         (16.0, 2400),
         (16.5, 2400),
         (17.0, 2400),
         (17.5, 2400),
         (18.0, 2400),
         (18.5, 2400),
         (19.0, 2400),
         (19.5, 2400),
         (20.0, 2400)],
 1.2: [(3.0, 24),
       (3.5, 79),
       (4.0, 150),
       (4.5, 238),
       (5.0, 346),
       (5.5, 475),
       (6.0, 629),
       (6.5, 810),
       (7.0, 1016),
       (7.5, 1245),
       (8.0, 1493),
       (8.5, 1755),
       (9.0, 2001),
       (9.5, 2184),
       (10.0, 2306),
       (10.5, 2375),
       (11.0, 2398),
       (11.5, 2400),
       (12.0, 2400),
       (12.5, 2400),
       (13.0, 2400),
       (13.5, 2400),
       (14.0, 2400),
       (14.5, 2400),
       (15.0, 2400),
       (15.5, 2400),
       (16.0, 2400),
       (16.5, 2400),
       (17.0, 2400),
       (17.5, 2400),
       (18.0, 2400),
       (18.5, 2400),
       (19.0, 2400),
       (19.5, 2400),
       (20.0, 2400)],
 1.225: [(3.0, 25),
         (3.5, 82),
         (4.0, 154),
         (4.5, 244),
         (5.0, 354),
         (5.5, 486),
         (6.0, 643),
         (6.5, 827),
         (7.0, 1038),
         (7.5, 1272),
         (8.0, 1525),
         (8.5, 1794),
         (9.0, 2037),
         (9.5, 2211),
         (10.0, 2326),
         (10.5, 2386),
         (11.0, 2400),
         (11.5, 2400),
         (12.0, 2400),
         (12.5, 2400),
         (13.0, 2400),
         (13.5, 2400),
         (14.0, 2400),
         (14.5, 2400),
         (15.0, 2400),
         (15.5, 2400),
         (16.0, 2400),
         (16.5, 2400),
         (17.0, 2400),
         (17.5, 2400),
         (18.0, 2400),
         (18.5, 2400),
         (19.0, 2400),
         (19.5, 2400),
         (20.0, 2400)],
 1.25: [(3.0, 26),
        (3.5, 84),
        (4.0, 157),
        (4.5, 250),
        (5.0, 362),
        (5.5, 497),
        (6.0, 657),
        (6.5, 845),
        (7.0, 1060),
        (7.5, 1299),
        (8.0, 1557),
        (8.5, 1833),
        (9.0, 2073),
        (9.5, 2239),
        (10.0, 2345),
        (10.5, 2396),
        (11.0, 2400),
        (11.5, 2400),
        (12.0, 2400),
        (12.5, 2400),
        (13.0, 2400),
        (13.5, 2400),
        (14.0, 2400),
        (14.5, 2400),
        (15.0, 2400),
        (15.5, 2400),
        (16.0, 2400),
        (16.5, 2400),
        (17.0, 2400),
        (17.5, 2400),
        (18.0, 2400),
        (18.5, 2400),
        (19.0, 2400),
        (19.5, 2400),
        (20.0, 2400)],
 1.275: [(3.0, 27),
         (3.5, 87),
         (4.0, 161),
         (4.5, 255),
         (5.0, 370),
         (5.5, 507),
         (6.0, 670),
         (6.5, 862),
         (7.0, 1082),
         (7.5, 1326),
         (8.0, 1590),
         (8.5, 1866),
         (9.0, 2097),
         (9.5, 2255),
         (10.0, 2353),
         (10.5, 2397),
         (11.0, 2400),
         (11.5, 2400),
         (12.0, 2400),
         (12.5, 2400),
         (13.0, 2400),
         (13.5, 2400),
         (14.0, 2400),
         (14.5, 2400),
         (15.0, 2400),
         (15.5, 2400),
         (16.0, 2400),
         (16.5, 2400),
         (17.0, 2400),
         (17.5, 2400),
         (18.0, 2400),
         (18.5, 2400),
         (19.0, 2400),
         (19.5, 2400),
         (20.0, 2400)],
 1.3: [(3.0, 29),
       (3.5, 89),
       (4.0, 165),
       (4.5, 261),
       (5.0, 378),
       (5.5, 518),
       (6.0, 684),
       (6.5, 879),
       (7.0, 1103),
       (7.5, 1352),
       (8.0, 1623),
       (8.5, 1898),
       (9.0, 2121),
       (9.5, 2272),
       (10.0, 2361),
       (10.5, 2398),
       (11.0, 2400),
       (11.5, 2400),
       (12.0, 2400),
       (12.5, 2400),
       (13.0, 2400),
       (13.5, 2400),
       (14.0, 2400),
       (14.5, 2400),
       (15.0, 2400),
       (15.5, 2400),
       (16.0, 2400),
       (16.5, 2400),
       (17.0, 2400),
       (17.5, 2400),
       (18.0, 2400),
       (18.5, 2400),
       (19.0, 2400),
       (19.5, 2400),
       (20.0, 2400)]}

# Vestas V164-7.0 MW: digitalizacion de la curva del datasheet (pagina 7).
_VESTAS_V164_7000_CURVE: List[PowerPoint] = [
    (4.0, 100), (5.0, 460), (6.0, 920), (7.0, 1610),
    (8.0, 2540), (9.0, 3730), (10.0, 5000), (11.0, 6000),
    (12.0, 6730), (13.0, 7000),
    *_plateau(14, 25, 7000),
]

# Siemens 3.6 MW / 120 m: digitalizacion de la "Sales power curve" del
# extracto suministrado. La identificacion comercial SWT-3.6-120 se infiere de
# la combinacion 3.6 MW + rotor 120 m + pala B58 + controlador WTC 3.
_SIEMENS_SWT_36_120_CURVE: List[PowerPoint] = [
    (3.0, 0), (4.0, 170), (5.0, 330), (6.0, 550),
    (7.0, 850), (8.0, 1180), (9.0, 1600), (10.0, 2130),
    (11.0, 2840), (12.0, 3300), (13.0, 3480), (14.0, 3550),
    (15.0, 3600),
    *_plateau(16, 25, 3600),
]

# Vestas V90-3.0 MW: digitalizacion de la curva del datasheet (pagina 2).
_VESTAS_V90_3000_CURVE: List[PowerPoint] = [
    (3.5, 0), (4.0, 80), (5.0, 190), (6.0, 360),
    (7.0, 590), (8.0, 900), (9.0, 1300), (10.0, 1730),
    (11.0, 2150), (12.0, 2550), (13.0, 2840), (14.0, 2960),
    (15.0, 3000),
    *_plateau(16, 25, 3000),
]

# EWT DW61-1MW: digitalizacion de la curva del datasheet. Por coherencia con
# el cut-in publicado, la simulacion debe forzar P=0 para v < 3 m/s.
_EWT_DW61_1000_CURVE: List[PowerPoint] = [
    # Digitalização refinada da curva DW61-1MW do datasheet.
    (3.0, 70), (4.0, 130), (5.0, 220), (6.0, 335),
    (7.0, 480), (8.0, 630), (9.0, 755), (10.0, 860),
    (11.0, 940), (12.0, 990), (13.0, 1000),
    *_plateau(14, 25, 1000),
]

# WEG AGW 147/4.2: digitalizacion de la curva del catalogo (pagina 2).
_WEG_AGW147_4200_CURVE: List[PowerPoint] = [
    (3.0, 0), (4.0, 250), (5.0, 500), (6.0, 950),
    (7.0, 1550), (8.0, 2400), (9.0, 3300), (10.0, 4000),
    (11.0, 4200),
    *_plateau(12, 20, 4200),
]


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
TURBINE_DB: Dict[str, dict] = {
    "Nordex N117/2400": {
        "spec": dict(
            manufacturer="Nordex",
            model="N117/2400",
            rated_power_kw=2400.0,
            rotor_diameter_m=117.0,
            swept_area_m2=round(_area_from_diameter(117.0), 1),
            hub_height_m=91.0,
            hub_height_options_m=[91.0],
            wind_class_iec="IEC III / class 3 (descrito en la propuesta)",
            cut_in_mps=3.0,
            cut_in_range_mps=None,
            rated_wind_speed_mps=11.0,
            rated_wind_speed_range_mps=None,
            cut_out_mps=None,
            recut_in_mps=None,
            reference_air_density_kg_m3=1.225,
            power_regulation=None,
            generator="2.5 MW platform de-rated a 2.4 MW",
            frequency_hz=None,
            design_lifetime_years=None,
            notes=(
                "Curva primaria tomada de la columna rho=1.225 kg/m3. El documento "
                "incluye ademas curvas tabuladas entre rho=1.000 y 1.300 kg/m3. "
                "Cut-in=3.0 m/s se toma como inicio de la tabla; el cut-out no se "
                "publica explicitamente en el material suministrado."
            ),
        ),
        "curve": dict(
            points=_NORDEX_N117_2400_CURVE,
            source_type="manufacturer_table",
            reference_density_kg_m3=1.225,
            min_wind_mps=3.0,
            max_wind_mps=20.0,
            density_correction="manufacturer_density_table",
            density_curves=_NORDEX_N117_DENSITY_CURVES,
            density_table_min_kg_m3=1.000,
            density_table_max_kg_m3=1.300,
            density_table_step_kg_m3=0.025,
            notes=(
                "Tabla IEC 61400-12-1. Se conserva la tabla completa de rho=1.000 a "
                "1.300 kg/m3; la curva primaria corresponde a rho=1.225 kg/m3."
            ),
        ),
        "quality": dict(
            cut_in="derived_from_curve_start",
            rated_wind_speed="derived_from_curve_first_rated_point",
            cut_out="not_provided",
            power_curve="exact_manufacturer_table",
        ),
        "source": dict(
            document="2.4MW CREO.pdf",
            pages=[12, 18, 19, 20, 21],
            reference="Nordex N117/2400 Power Curves, Rev. 00, 2011-01-06",
        ),
    },

    "Vestas V164-7.0 MW": {
        "spec": dict(
            manufacturer="Vestas",
            model="V164-7.0 MW",
            rated_power_kw=7000.0,
            rotor_diameter_m=164.0,
            swept_area_m2=21124.0,
            hub_height_m=None,
            hub_height_options_m=[],
            wind_class_iec="IEC S",
            cut_in_mps=4.0,
            cut_in_range_mps=None,
            rated_wind_speed_mps=13.0,
            rated_wind_speed_range_mps=None,
            cut_out_mps=25.0,
            recut_in_mps=None,
            reference_air_density_kg_m3=DEFAULT_REFERENCE_AIR_DENSITY,
            power_regulation="Pitch regulated, variable speed",
            generator="Permanent magnet; full-scale converter",
            frequency_hz=[50],
            design_lifetime_years=25,
            notes=(
                "Aerogenerador offshore. Altura de buje site-specific. El datasheet "
                "publica cut-in=4 m/s; Vnom~13 m/s y cut-out~25 m/s se derivan de "
                "la grafica de potencia suministrada. La densidad de referencia no "
                "se explicita junto a la grafica; se adopta 1.225 kg/m3 como referencia "
                "del modelo y queda marcada como supuesto."
            ),
        ),
        "curve": dict(
            points=_VESTAS_V164_7000_CURVE,
            source_type="datasheet_graph_digitized",
            reference_density_kg_m3=DEFAULT_REFERENCE_AIR_DENSITY,
            min_wind_mps=4.0,
            max_wind_mps=25.0,
            density_correction="equivalent_wind_speed",
            notes="Digitalizacion aproximada de la grafica de la pagina 7.",
        ),
        "quality": dict(
            cut_in="manufacturer_spec",
            rated_wind_speed="derived_from_curve",
            cut_out="derived_from_curve_endpoint",
            reference_density="model_default_not_stated_next_to_curve",
            power_curve="digitized_from_manufacturer_graph",
        ),
        "source": dict(
            document="7MW.pdf",
            pages=[6, 7],
            reference="Vestas V164-7.0 MW brochure, 03/2011-EN",
        ),
    },

    "Siemens SWT-3.6-120": {
        "spec": dict(
            manufacturer="Siemens",
            model="SWT-3.6-120",
            rated_power_kw=3600.0,
            rotor_diameter_m=120.0,
            swept_area_m2=11300.0,
            hub_height_m=90.0,
            hub_height_options_m=[90.0],
            wind_class_iec=None,
            cut_in_mps=3.0,
            cut_in_range_mps=[3.0, 5.0],
            rated_wind_speed_mps=13.0,
            rated_wind_speed_range_mps=[12.0, 13.0],
            cut_out_mps=25.0,
            recut_in_mps=None,
            reference_air_density_kg_m3=1.225,
            power_regulation="Pitch regulation with variable speed",
            generator="Asynchronous, 3,600 kW, IP54",
            frequency_hz=None,
            design_lifetime_years=None,
            notes=(
                "El extracto suministrado no muestra el nombre comercial en las dos paginas. "
                "La identificacion SWT-3.6-120 se infiere de 3.6 MW, rotor 120 m, pala B58 "
                "y controlador WTC 3. El datasheet informa cut-in 3-5 m/s y potencia nominal "
                "a 12-13 m/s; para el modelo se usa el extremo inferior de cut-in (3 m/s) "
                "y 13 m/s como Vnom representativa."
            ),
        ),
        "curve": dict(
            points=_SIEMENS_SWT_36_120_CURVE,
            source_type="datasheet_graph_digitized",
            reference_density_kg_m3=1.225,
            min_wind_mps=3.0,
            max_wind_mps=25.0,
            density_correction="equivalent_wind_speed",
            notes=(
                "Sales power curve digitalizada. El documento declara condiciones estandar: "
                "15 C, 1013 mbar y rho=1.225 kg/m3."
            ),
        ),
        "quality": dict(
            model_identification="inferred_from_supplied_specs",
            cut_in="manufacturer_range; lower_bound_used_by_model",
            rated_wind_speed="manufacturer_range; upper_bound_used_as_representative",
            cut_out="manufacturer_spec",
            power_curve="digitized_from_manufacturer_graph",
        ),
        "source": dict(
            document="3.6MW.pdf",
            pages=[1, 2],
            reference="Technical specifications / Sales power curve extract supplied by user",
        ),
    },

    "Vestas V90-3.0 MW": {
        "spec": dict(
            manufacturer="Vestas",
            model="V90-3.0 MW",
            rated_power_kw=3000.0,
            rotor_diameter_m=90.0,
            swept_area_m2=6362.0,
            hub_height_m=None,
            hub_height_options_m=[65.0, 80.0, 105.0],
            wind_class_iec="IEC IA / IEC IIA",
            cut_in_mps=3.5,
            cut_in_range_mps=None,
            rated_wind_speed_mps=15.0,
            rated_wind_speed_range_mps=None,
            cut_out_mps=25.0,
            recut_in_mps=20.0,
            reference_air_density_kg_m3=DEFAULT_REFERENCE_AIR_DENSITY,
            power_regulation="Pitch regulated, variable speed",
            generator="4-pole doubly fed generator",
            frequency_hz=[50, 60],
            design_lifetime_years=None,
            notes=(
                "Especificaciones operativas publicadas: cut-in 3.5 m/s, rated 15 m/s, "
                "cut-out 25 m/s y re-cut-in 20 m/s. La densidad 1.225 kg/m3 aparece en "
                "el documento para condiciones de ruido; para la curva se usa como "
                "referencia estandar del modelo."
            ),
        ),
        "curve": dict(
            points=_VESTAS_V90_3000_CURVE,
            source_type="datasheet_graph_digitized",
            reference_density_kg_m3=DEFAULT_REFERENCE_AIR_DENSITY,
            min_wind_mps=3.5,
            max_wind_mps=25.0,
            density_correction="equivalent_wind_speed",
            notes="Digitalizacion aproximada de la curva de potencia de la pagina 2.",
        ),
        "quality": dict(
            cut_in="manufacturer_spec",
            rated_wind_speed="manufacturer_spec",
            cut_out="manufacturer_spec",
            recut_in="manufacturer_spec",
            power_curve="digitized_from_manufacturer_graph",
        ),
        "source": dict(
            document="3MW.pdf",
            pages=[1, 2],
            reference="Vestas V90-3.0 MW Facts and figures",
        ),
    },

    "EWT DW61-1MW": {
        "spec": dict(
            manufacturer="EWT",
            model="DW61-1MW",
            rated_power_kw=1000.0,
            rotor_diameter_m=61.0,
            swept_area_m2=round(_area_from_diameter(61.0), 1),
            hub_height_m=None,
            hub_height_options_m=[46.0, 69.0],
            wind_class_iec="IEC IIIA",
            cut_in_mps=3.0,
            cut_in_range_mps=None,
            rated_wind_speed_mps=13.0,
            rated_wind_speed_range_mps=None,
            cut_out_mps=25.0,
            recut_in_mps=None,
            reference_air_density_kg_m3=1.225,
            power_regulation="Direct drive; power curve per manufacturer",
            generator="Direct drive platform",
            frequency_hz=None,
            design_lifetime_years=None,
            notes=(
                "Diseñado para sitios de bajo viento. El fabricante declara la curva para "
                "15 C, rho=1.225 kg/m3, shear 1/7, sitio no complejo, sin inclinacion de flujo "
                "y palas limpias. Vnom~13 m/s se deriva de la grafica."
            ),
        ),
        "curve": dict(
            points=_EWT_DW61_1000_CURVE,
            source_type="datasheet_graph_digitized",
            reference_density_kg_m3=1.225,
            min_wind_mps=3.0,
            max_wind_mps=25.0,
            density_correction="equivalent_wind_speed",
            notes="Curva DW61-1MW digitalizada de la pagina 1.",
        ),
        "quality": dict(
            cut_in="manufacturer_spec",
            rated_wind_speed="derived_from_curve",
            cut_out="manufacturer_spec",
            power_curve="digitized_from_manufacturer_graph",
        ),
        "source": dict(
            document="1MW.pdf",
            pages=[1],
            reference="EWT DW61 datasheet",
        ),
    },

    "WEG AGW 147 / 4.2": {
        "spec": dict(
            manufacturer="WEG",
            model="AGW 147 / 4.2",
            rated_power_kw=4200.0,
            rotor_diameter_m=147.0,
            swept_area_m2=16972.0,
            hub_height_m=None,
            hub_height_options_m=[120.0, 125.0],
            wind_class_iec="IEC S (Vave=9.0 m/s; Iref=0.14; Vref=37.5 m/s)",
            cut_in_mps=3.0,
            cut_in_range_mps=None,
            rated_wind_speed_mps=11.0,
            rated_wind_speed_range_mps=None,
            cut_out_mps=None,
            recut_in_mps=None,
            reference_air_density_kg_m3=1.225,
            power_regulation="Velocidade variavel com controle de passo por acionamento eletrico",
            generator="Sincrono de imas permanentes; direct drive; full power converter",
            frequency_hz=[50, 60],
            design_lifetime_years=20,
            notes=(
                "Catalogo Rev. 02 (04/2023). A curva e a PAE usam 100% de disponibilidade, "
                "0% de perdas; PAE com Weibull k=3.0 e rho=1.225 kg/m3. Cut-in~3 m/s e "
                "Vnom~11 m/s sao derivados da grafica. O cut-out nao e informado no material."
            ),
        ),
        "curve": dict(
            points=_WEG_AGW147_4200_CURVE,
            source_type="datasheet_graph_digitized",
            reference_density_kg_m3=1.225,
            min_wind_mps=3.0,
            max_wind_mps=20.0,
            density_correction="equivalent_wind_speed",
            notes="Curva de potencia digitalizada da pagina 2 do catalogo WEG.",
        ),
        "quality": dict(
            cut_in="derived_from_curve_start",
            rated_wind_speed="derived_from_curve",
            cut_out="not_provided",
            power_curve="digitized_from_manufacturer_graph",
        ),
        "source": dict(
            document="WEG-aerogeradores-agw-147-4.2-50077448-catalogo-portugues.pdf",
            pages=[2],
            reference="WEG AGW 147 / 4.2, Cod. 50077448, Rev. 02, 04/2023",
        ),
    },
}


# ---------------------------------------------------------------------------
# Frontera eléctrica de las curvas
# ---------------------------------------------------------------------------
# La V1 trata las curvas como potencia eléctrica del aerogenerador y no vuelve
# a descontar eficiencias internas de rotor/transmisión/generador. Cuando el
# documento suministrado indica el punto de medición, se conserva aquí; en los
# demás casos no se inventa un punto físico exacto.
_POWER_BOUNDARY = {
    "Nordex N117/2400": {
        "quantity": "electrical_active_power",
        "measurement_point": "low_voltage_side_660_vac",
        "measurement_point_label": "Baixa tensão · 660 VAC",
        "internal_turbine_losses_reapplied": False,
        "downstream_grid_losses_included": False,
        "confidence": "manufacturer_spec",
    },
    "Vestas V164-7.0 MW": {
        "quantity": "manufacturer_electrical_power_curve",
        "measurement_point": None,
        "measurement_point_label": "Não explicitado no material fornecido",
        "internal_turbine_losses_reapplied": False,
        "downstream_grid_losses_included": False,
        "confidence": "measurement_point_not_provided",
    },
    "Siemens SWT-3.6-120": {
        "quantity": "manufacturer_electrical_power_curve",
        "measurement_point": None,
        "measurement_point_label": "Não explicitado no extrato fornecido",
        "internal_turbine_losses_reapplied": False,
        "downstream_grid_losses_included": False,
        "confidence": "measurement_point_not_provided",
    },
    "Vestas V90-3.0 MW": {
        "quantity": "manufacturer_electrical_power_curve",
        "measurement_point": None,
        "measurement_point_label": "Não explicitado no material fornecido",
        "internal_turbine_losses_reapplied": False,
        "downstream_grid_losses_included": False,
        "confidence": "measurement_point_not_provided",
    },
    "EWT DW61-1MW": {
        "quantity": "manufacturer_electrical_power_curve",
        "measurement_point": None,
        "measurement_point_label": "Não explicitado no material fornecido",
        "internal_turbine_losses_reapplied": False,
        "downstream_grid_losses_included": False,
        "confidence": "measurement_point_not_provided",
    },
    "WEG AGW 147 / 4.2": {
        "quantity": "manufacturer_electrical_power_curve",
        "measurement_point": None,
        "measurement_point_label": "Curva elétrica do fabricante; ponto exato não explicitado",
        "internal_turbine_losses_reapplied": False,
        "downstream_grid_losses_included": False,
        "confidence": "measurement_point_not_provided",
    },
}
for _key, _boundary in _POWER_BOUNDARY.items():
    TURBINE_DB[_key]["power_boundary"] = _boundary



# ---------------------------------------------------------------------------
# API de la base de datos
# ---------------------------------------------------------------------------
def list_manufacturers() -> List[str]:
    """Fabricantes disponibles (+ opcion personalizada futura)."""
    manufacturers = sorted({entry["spec"]["manufacturer"] for entry in TURBINE_DB.values()})
    return manufacturers + [CUSTOM_KEY]


def list_models(manufacturer: Optional[str] = None) -> List[str]:
    """Lista las claves de catalogo, opcionalmente filtradas por fabricante."""
    if manufacturer is None:
        return list(TURBINE_DB.keys())
    if manufacturer == CUSTOM_KEY:
        return [CUSTOM_KEY]
    return [
        key for key, entry in TURBINE_DB.items()
        if entry["spec"]["manufacturer"] == manufacturer
    ]


def get_turbine(key: str) -> dict:
    """Devuelve una copia profunda para evitar modificar el catalogo global."""
    if key not in TURBINE_DB:
        raise KeyError(f"Aerogenerador no encontrado: {key!r}")
    return deepcopy(TURBINE_DB[key])


def get_power_curve(key: str) -> List[PowerPoint]:
    """Curva (velocidad m/s, potencia kW) del aerogenerador seleccionado."""
    return list(get_turbine(key)["curve"]["points"])


def specific_power_w_m2(key: str) -> float:
    """Potencia especifica nominal del rotor [W/m2]."""
    entry = TURBINE_DB[key]
    return entry["spec"]["rated_power_kw"] * 1000.0 / entry["spec"]["swept_area_m2"]


def catalog_summary(key: str) -> dict:
    """Resumen listo para alimentar la futura pagina 'Catalogo de aerogeneradores'."""
    entry = get_turbine(key)
    spec = entry["spec"]
    return {
        "key": key,
        "manufacturer": spec["manufacturer"],
        "model": spec["model"],
        "rated_power_kw": spec["rated_power_kw"],
        "rotor_diameter_m": spec["rotor_diameter_m"],
        "swept_area_m2": spec["swept_area_m2"],
        "specific_power_w_m2": specific_power_w_m2(key),
        "hub_height_m": spec["hub_height_m"],
        "hub_height_options_m": spec["hub_height_options_m"],
        "cut_in_mps": spec["cut_in_mps"],
        "cut_in_range_mps": spec["cut_in_range_mps"],
        "rated_wind_speed_mps": spec["rated_wind_speed_mps"],
        "rated_wind_speed_range_mps": spec["rated_wind_speed_range_mps"],
        "cut_out_mps": spec["cut_out_mps"],
        "reference_air_density_kg_m3": spec["reference_air_density_kg_m3"],
        "curve_source_type": entry["curve"]["source_type"],
        "source_document": entry["source"]["document"],
    }


def validate_database() -> List[str]:
    """Valida invariantes basicas del catalogo. Retorna una lista de errores."""
    errors: List[str] = []
    for key, entry in TURBINE_DB.items():
        spec = entry.get("spec", {})
        curve = entry.get("curve", {})
        points = curve.get("points", [])

        if not points:
            errors.append(f"{key}: curva vacia")
            continue

        speeds = [float(v) for v, _ in points]
        powers = [float(p) for _, p in points]

        if any(b <= a for a, b in zip(speeds, speeds[1:])):
            errors.append(f"{key}: velocidades no estrictamente crecientes")
        if min(powers) < 0:
            errors.append(f"{key}: potencia negativa")
        if max(powers) > float(spec["rated_power_kw"]) * 1.01:
            errors.append(f"{key}: curva supera Pnom en mas de 1%")
        if abs(max(powers) - float(spec["rated_power_kw"])) > max(10.0, float(spec["rated_power_kw"]) * 0.01):
            errors.append(f"{key}: la curva no alcanza aproximadamente Pnom")

    return errors


__all__ = [
    "CUSTOM_KEY",
    "DEFAULT_REFERENCE_AIR_DENSITY",
    "TURBINE_DB",
    "list_manufacturers",
    "list_models",
    "get_turbine",
    "get_power_curve",
    "specific_power_w_m2",
    "catalog_summary",
    "validate_database",
]
