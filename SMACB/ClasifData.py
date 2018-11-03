from time import gmtime

from babel.numbers import parse_decimal


class ClasifData(object):

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
            entry = {}
            entry['team'] = cells[1].get_text()
            entry['socio'] = cells[2].get_text()
            entry['value'] = parse_decimal(cells[3].get_text(), locale="de")
            result[entry['team']] = entry
        return result

    def __repr__(self):
        return "{ " + ", ".join([" '{}' ({}): {}".format(self.data[k]['team'],
                                                         self.data[k]['socio'],
                                                         self.data[k]['value']) for k in
                                 sorted(self.data, key=self.data.get('value'), reverse=True)]) + "} "

    def values(self, excludeList=set()):
        return [self.data[x]['value'] for x in self.data if x not in excludeList]

    def asdict(self, excludeList=set()):
        return {x: self.data[x]['value'] for x in self.data if x not in excludeList}

    def __ne__(self, other):
        clavesEq = set(self.data.keys()).union(other.data.keys())

        for k in clavesEq:
            if k not in list(self.data.keys()) or k not in list(other.data.keys()):
                return True
            if self.data[k]['value'] != other.data[k]['value']:
                return True

        return False


def manipulaSocio(socioID):
    import re

    # PATTERN = r"^\s*(\S+)(\s+(\([^)]\)))?\s*$"
    PATTERN = r"^\s*(.+)\s+\(.*\)\s*$"

    match = re.match(PATTERN, socioID)

    if match is None:
        return socioID

    return match.group(1)
