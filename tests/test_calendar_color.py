"""La couleur d'un événement d'agenda : posée, changée, lue, refusée.

Règle du 28 sept 2026 (REGLES.md §Agenda) : un rendez-vous qui demande un
déplacement se met en VERT, et le vert de Richard est le colorId 10 (Basilic),
lu le 28 sept sur son bloc physio du 26 oct, qu'il avait coloré à la main. Les
entraînements sont en 3 (mauve, « Workout »).

Rien ici ne touche le réseau : le ``service`` est remplacé par un faux qui
garde le corps envoyé à Google. Le passage par la façade REST est gardé dans
test_google_connecteur.py.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

import calendar_tools as agenda


class _Exec:
    def __init__(self, fn: Callable[[], Any]) -> None:
        self._fn = fn

    def execute(self) -> Any:
        return self._fn()


class _Evenements:
    """Un agenda d'un seul événement, qui répond comme Google.

    Les paramètres gardent les noms camelCase de l'API Google qu'ils imitent.
    """

    def __init__(self, existant: dict[str, Any] | None = None) -> None:
        self.existant = existant or {}
        self.envoye: dict[str, Any] = {}
        self.params: dict[str, Any] = {}
        self.appels = 0

    def _garder(self, body: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        self.appels += 1
        self.envoye = body
        self.params = params
        return {"id": "ev1", **body}

    def insert(self, calendarId: str, body: dict[str, Any], **params: Any) -> _Exec:  # noqa: N803
        return _Exec(lambda: self._garder(body, params))

    def get(self, calendarId: str, eventId: str) -> _Exec:  # noqa: N803
        self.appels += 1
        return _Exec(lambda: dict(self.existant))

    def update(
        self,
        calendarId: str,  # noqa: N803
        eventId: str,  # noqa: N803
        body: dict[str, Any],
        **params: Any,
    ) -> _Exec:
        return _Exec(lambda: self._garder(body, params))

    def list(self, **_: Any) -> _Exec:
        self.appels += 1
        return _Exec(lambda: {"items": [dict(self.existant)]})


Poser = Callable[..., _Evenements]


@pytest.fixture
def agenda_faux(monkeypatch: pytest.MonkeyPatch) -> Poser:
    def poser(existant: dict[str, Any] | None = None) -> _Evenements:
        evs = _Evenements(existant)

        class _Svc:
            def events(self) -> _Evenements:
                return evs

        monkeypatch.setattr(agenda, "service", lambda *a, **k: _Svc())
        return evs

    return poser


_BASE: dict[str, Any] = {
    "id": "ev1",
    "summary": "x",
    "start": {"dateTime": "2026-10-26T14:30:00-04:00"},
}
_DEBUT, _FIN = "2026-10-26T14:30:00", "2026-10-26T16:00:00"


def test_vert_a_la_creation_donne_le_basilic_de_richard(agenda_faux: Poser) -> None:
    evs = agenda_faux()
    out = agenda.create_event("x", _DEBUT, _FIN, color="vert")
    assert evs.envoye["colorId"] == "10"
    assert out["color_id"] == "10"
    assert out["color_name"] == "road"


@pytest.mark.parametrize(
    ("valeur", "attendu"),
    [
        ("3", "3"),
        ("workout", "3"),
        ("Mauve", "3"),
        ("basilic", "10"),
        (" 10 ", "10"),
        ("bleu", "9"),
        ("rouge", "11"),
        ("vert pâle", "2"),
        ("VERT PALE", "2"),
        (10, "10"),
        ("urgent", "11"),
        ("road", "10"),
        ("girls", "4"),
        ("Work Facturable", "9"),
        ("work", "8"),
        ("maison", "6"),
        (3, "3"),
    ],
)
def test_ids_noms_et_alias_sont_convertis(agenda_faux: Poser, valeur: Any, attendu: str) -> None:
    evs = agenda_faux()
    agenda.create_event("x", _DEBUT, _FIN, color=valeur)
    assert evs.envoye["colorId"] == attendu


def test_sans_couleur_le_corps_envoye_ne_change_pas(agenda_faux: Poser) -> None:
    evs = agenda_faux()
    out = agenda.create_event("x", _DEBUT, _FIN)
    assert "colorId" not in evs.envoye
    assert out["color_id"] is None
    assert out["color_name"] is None


@pytest.mark.parametrize(
    "mauvaise", ["12", "0", "chartreuse", "", "#51b749", "10; drop", 12, 0, True, 1.0, ["10"]]
)
def test_une_couleur_inconnue_est_refusee_avant_tout_appel(
    agenda_faux: Poser, mauvaise: Any
) -> None:
    evs = agenda_faux(_BASE)
    with pytest.raises(agenda.CouleurInconnueError, match="vert"):
        agenda.create_event("x", _DEBUT, _FIN, color=mauvaise)
    with pytest.raises(agenda.CouleurInconnueError, match="vert"):
        agenda.update_event("ev1", color=mauvaise)
    assert evs.appels == 0


def test_le_refus_ne_recopie_pas_la_valeur_recue(agenda_faux: Poser) -> None:
    agenda_faux()
    with pytest.raises(agenda.CouleurInconnueError) as refus:
        agenda.create_event("x", _DEBUT, _FIN, color="chartreuse-injectee")
    assert "chartreuse" not in str(refus.value)


def test_la_mise_a_jour_change_la_couleur(agenda_faux: Poser) -> None:
    evs = agenda_faux({**_BASE, "colorId": "3"})
    out = agenda.update_event("ev1", color="vert")
    assert evs.envoye["colorId"] == "10"
    assert out["color_id"] == "10"


def test_changer_seulement_la_couleur_n_avertit_personne(agenda_faux: Poser) -> None:
    """Une couleur est une affaire de Richard : aucun avis aux invités pour elle."""
    evs = agenda_faux({**_BASE, "colorId": "3"})
    agenda.update_event("ev1", color="vert")
    assert evs.params["sendUpdates"] == "none"


def test_couleur_avec_un_autre_changement_garde_l_avis_demande(agenda_faux: Poser) -> None:
    evs = agenda_faux(_BASE)
    agenda.update_event("ev1", color="vert", summary="y")
    assert evs.params["sendUpdates"] == "all"


def test_la_mise_a_jour_sans_couleur_garde_celle_qui_est_la(agenda_faux: Poser) -> None:
    evs = agenda_faux({**_BASE, "colorId": "3"})
    agenda.update_event("ev1", summary="y")
    assert evs.envoye["colorId"] == "3"


def test_defaut_retire_la_couleur(agenda_faux: Poser) -> None:
    evs = agenda_faux({**_BASE, "colorId": "10"})
    out = agenda.update_event("ev1", color="défaut")
    assert "colorId" not in evs.envoye
    assert out["color_id"] is None


def test_defaut_n_a_pas_de_sens_a_la_creation(agenda_faux: Poser) -> None:
    agenda_faux()
    with pytest.raises(agenda.CouleurInconnueError):
        agenda.create_event("x", _DEBUT, _FIN, color="defaut")


@pytest.mark.parametrize("verbose", [False, True])
def test_la_lecture_rend_la_couleur(agenda_faux: Poser, verbose: bool) -> None:
    agenda_faux({**_BASE, "colorId": "3"})
    (ev,) = agenda.list_events(time_min="2026-10-26T00:00:00", verbose=verbose)
    assert ev["color_id"] == "3"
    assert ev["color_name"] == "workout"


@pytest.mark.parametrize("outil", ["create_event", "update_event"])
@pytest.mark.parametrize("valeur", [True, False, 10.0, 1.5])
def test_l_annotation_refuse_booleen_et_reel_avant_l_outil(outil: str, valeur: Any) -> None:
    """Les façades MCP (distante et locale) valident par pydantic AVANT l'outil, en
    mode souple : avec `int`, True devenait 1 (lavande) et 10.0 devenait 10. C'est
    l'annotation StrictInt qui tient le même contrat que la façade REST."""
    from typing import get_type_hints

    from pydantic import TypeAdapter, ValidationError

    annotation = get_type_hints(getattr(agenda, outil), include_extras=True)["color"]
    adaptateur = TypeAdapter(annotation)
    assert adaptateur.validate_python(10) == 10
    assert adaptateur.validate_python("vert") == "vert"
    with pytest.raises(ValidationError):
        adaptateur.validate_python(valeur)


def test_une_couleur_sans_etiquette_se_lit_par_sa_couleur(agenda_faux: Poser) -> None:
    agenda_faux({**_BASE, "colorId": "5"})
    (ev,) = agenda.list_events(time_min="2026-10-26T00:00:00")
    assert ev["color_name"] == "jaune"


def test_la_description_donne_les_etiquettes_dans_l_ordre_de_priorite() -> None:
    """Un moteur choisit la couleur en lisant la description de cal_create_event :
    l'ordre qu'elle affiche doit être celui de la table, urgent puis road en tête."""
    doc = agenda.create_event.__doc__ or ""
    positions = [doc.index(f"{nom} ({cid})") for cid, nom in agenda._ETIQUETTES.items()]
    assert positions == sorted(positions)
    assert list(agenda._ETIQUETTES.values())[:2] == ["urgent", "road"]
