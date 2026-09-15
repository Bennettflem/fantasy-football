from __future__ import annotations

from .data import Season


def _clean(name: str) -> str:
    name = " ".join(str(name).split())
    return name.title() if name.islower() else name


class Identity:
    """Maps ESPN owner IDs to people, and team-seasons to owners."""

    def __init__(self, seasons: dict[int, Season]):
        self.owner_name: dict[str, str] = {}
        self.team_owner: dict[tuple[int, int], str] = {}
        self.name_owner: dict[tuple[int, str], str] = {}
        self.owner_team: dict[tuple[int, str], str] = {}
        self.owner_team_id: dict[tuple[int, str], int] = {}
        self.latest_team: dict[str, tuple[int, str]] = {}
        self.years = sorted(seasons)

        for year in self.years:
            s = seasons[year]
            by_name: dict[str, str] = {}
            for _, m in s.members.iterrows():
                full = _clean(f"{m.get('first_name', '')} {m.get('last_name', '')}")
                if not full.strip():
                    full = str(m.get("display_name", m.member_id))
                self.owner_name[m.member_id] = full
                by_name[full.lower()] = m.member_id
            for _, t in s.teams.iterrows():
                oid = ""
                ids = str(t.get("owner_ids", "") or "")
                if ids and ids != "nan":
                    oid = ids.split("|")[0]
                if not oid:
                    first = _clean(str(t.owners).split("&")[0])
                    oid = by_name.get(first.lower(), first)
                    self.owner_name.setdefault(oid, first)
                team_id = int(t.team_id)
                team_name = str(t.team_name).strip()
                self.team_owner[(year, team_id)] = oid
                self.name_owner[(year, team_name)] = oid
                self.owner_team[(year, oid)] = team_name
                self.owner_team_id[(year, oid)] = team_id
                self.latest_team[oid] = (year, team_name)

    def owners(self) -> list[str]:
        return sorted(self.latest_team, key=lambda o: self.owner_name.get(o, o))

    def name(self, oid: str) -> str:
        return self.owner_name.get(oid, oid)

    def first(self, oid: str) -> str:
        return self.name(oid).split(" ")[0]

    def short(self, oid: str) -> str:
        """First name, plus last initial when another owner shares the first name."""
        first = self.first(oid)
        clash = [o for o in self.latest_team if o != oid and self.first(o).lower() == first.lower()]
        if clash:
            parts = self.name(oid).split(" ")
            return f"{first} {parts[-1][0]}." if len(parts) > 1 else first
        return first

    def team(self, oid: str, year: int | None = None) -> str:
        if year is not None and (year, oid) in self.owner_team:
            return self.owner_team[(year, oid)]
        return self.latest_team.get(oid, (0, ""))[1]

    def label(self, oid: str, year: int | None = None) -> str:
        team = self.team(oid, year)
        return f"{self.name(oid)} ({team})" if team else self.name(oid)

    def owner_of_team_name(self, year: int, team_name: str) -> str | None:
        return self.name_owner.get((year, str(team_name).strip()))

    def find(self, query: str) -> str:
        q = " ".join(query.lower().split())
        if not q:
            raise ValueError("Give an owner's first name, last name, or team name.")
        hits = set()
        for oid in self.latest_team:
            name = self.name(oid).lower()
            parts = name.split()
            if q == name or q in parts or name.startswith(q):
                hits.add(oid)
        if not hits:
            for (year, team_name), oid in self.name_owner.items():
                if q in team_name.lower():
                    hits.add(oid)
        if len(hits) == 1:
            return hits.pop()
        if not hits:
            raise ValueError(f"No owner matches '{query}'. Owners: " + ", ".join(self.name(o) for o in self.owners()))
        raise ValueError(f"'{query}' is ambiguous: " + ", ".join(sorted(self.name(o) for o in hits)))
