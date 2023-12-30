import re
from time import gmtime

from babel.numbers import parse_decimal

PATvalores = r'(?P<valor>\d+([,.]\d+)?)'


class ClasifData():

    def __init__(self, content, label=None, source=None):
        self.timestamp = gmtime()
        self.label = label
        self.source = source
        self.data = self.processClasifPage(content)

    def processClasifPage(self, content):
        result = {}
        table = content.find("table", {"class": "general"})
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            entry = {'team': cells[1].get_text(), 'socio': cells[2].get_text()}
            valueCell = cells[3].get_text()

            REvalor = re.match(PATvalores, valueCell)
            if REvalor:
                valorAincluir = REvalor['valor']
            else:
                raise ValueError(f"Valor '{valueCell}' no casa RE '{PATvalores}'")
            entry['value'] = parse_decimal(valorAincluir, locale="de")
            result[entry['team']] = entry
        return result

    def __repr__(self):
        return "{ " + ", ".join(
                [f" '{self.data[k]['team']}' ({self.data[k]['socio']}): {self.data[k]['value']}" for k in
                 sorted(self.data, key=self.data.get('value'), reverse=True)]) + "} "

    def values(self, excludeList=None):
        if excludeList is None:
            excludeList = set()
        return [v['value'] for k, v in self.data.items() if k not in excludeList]

    def asdict(self, excludeList=None):
        if excludeList is None:
            excludeList = set()
        return {k: v['value'] for k, v in self.data.items() if k not in excludeList}

    def __ne__(self, other):
        clavesEq = set(self.data.keys()).union(other.data.keys())

        for k in clavesEq:
            if (k not in self.data) or (k not in other.data):
                return True
            if self.data[k]['value'] != other.data[k]['value']:
                return True

        return False


def manipulaSocio(socioID):
    # PATTERN = r"^\s*(\S+)(\s+(\([^)]\)))?\s*$"
    PATTERN = r"^\s*(.+)\s+\(.*\)\s*$"

    match = re.match(PATTERN, socioID)

    if match is None:
        return socioID

    return match.group(1)
