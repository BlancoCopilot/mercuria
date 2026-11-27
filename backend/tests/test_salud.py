"""Clasificación de centros de salud de OpenStreetMap (sin base de datos)."""
from rastrohg.ingest.osm import _salud_de, health_tipo


def test_tipos():
    assert health_tipo({"amenity": "hospital", "name": "Hospital de Reyes"}) == "Hospital"
    assert health_tipo({"amenity": "clinic", "name": "Centro de Salud Sapecho"}) == "Centro de salud"
    assert health_tipo({"healthcare": "centre", "name": "Puesto de Salud Tomachi"}) == "Puesto de salud"
    assert health_tipo({"amenity": "doctors"}) == "Consultorio"
    assert health_tipo({"healthcare": "hospital", "amenity": "hospital"}) == "Hospital"


def test_excluye_lo_que_no_atiende_pacientes():
    assert health_tipo({"amenity": "pharmacy", "healthcare": "pharmacy", "name": "Farmacia Virgen del Carmen"}) is None
    assert health_tipo({"healthcare": "pharmacy", "name": "Botica Lucas"}) is None
    assert health_tipo({"amenity": "dentist", "healthcare": "dentist"}) is None
    assert health_tipo({"healthcare": "optometrist"}) is None
    assert health_tipo({"healthcare": "laboratory"}) is None


def test_salud_de_overpass():
    payload = {"elements": [
        {"type": "node", "id": 1, "lat": -15.5, "lon": -67.4, "tags": {"amenity": "clinic", "name": "C.S. Palos Blancos", "phone": "+591 2 123"}},
        {"type": "way", "id": 2, "center": {"lat": -14.3, "lon": -67.3}, "tags": {"amenity": "hospital"}},
        {"type": "node", "id": 3, "lat": -15.4, "lon": -67.8, "tags": {"healthcare": "pharmacy", "name": "Botica"}},
        {"type": "node", "id": 4, "tags": {"amenity": "clinic"}},                       # sin coordenadas
    ]}
    out = _salud_de(payload)
    assert [h["osm"] for h in out] == ["node/1", "way/2"]
    assert out[0]["phone"] == "+591 2 123" and out[0]["tipo"] == "Centro de salud"
    assert out[1]["name"] == "Hospital" and out[1]["lat"] == -14.3
