from time import gmtime

from .LoggedValue import LoggedValue


class LoggedDict:
    def __init__(self, exclusions: set = None):

        if exclusions is not None and not isinstance(exclusions, (set, list, tuple)):
            raise TypeError(f"LoggedDict: expected set/list/tuple for exclusions: {exclusions}")

        self.current = dict()
        self.exclusions = exclusions or set()
        self.timestamp = gmtime()

    def __getitem__(self, item):
        return self.current.__getitem__(item).get()

    def __setitem__(self, k, v):
        if k in self.exclusions:
            raise KeyError(f"Key '{k}' in exclusions: {sorted(self.exclusions)}")
        currVal = self.current.get(k, LoggedValue())  # default=
        changes = currVal.set(v)

        self.current[k] = currVal
        return changes

    def get(self, key, default=None):
        return self.current.get(key, default).get()

    def getValue(self, key):
        return self.current.get(key)

    def update(self, newValues, timestamp=None):
        changeTime = timestamp or gmtime()
        result = []
        newValIter = newValues
        if isinstance(newValues, dict):
            newValIter = newValues.items()

        for k, v in newValIter:
            if k in self.exclusions:
                continue
            v1 = self.current.get(k, LoggedValue(timestamp=changeTime))
            r1 = v1.set(v, changeTime)
            if r1:
                self.current[k] = v1
            result.append(r1)

        return any(result)

    def purge(self, keys2delete, timestamp=None):
        changeTime = timestamp or gmtime()
        result = []

        for k in keys2delete:
            if k in self.exclusions:
                continue
            if k in self.current:
                r1 = self.current[k].clear(timestamp=changeTime)
                result.append(r1)

        return any(result)

    def addExclusion(self, *kargs):
        self.exclusions.update(set(kargs))
        # TOTHINK: Qué hacer con los valores almacenados y que han quedado excluidos?

    def removeExclusion(self, *kargs):
        self.exclusions.remove(set(kargs).intersection(self.exclusions))

    def __len__(self):
        currData = [k for k, v in self.current.items() if not v.isDeleted()]
        return len(currData)


class DictOfLoggedDict:
    def __init__(self, exclusions: set = None):

        if exclusions is not None and not isinstance(exclusions, (set, list, tuple)):
            raise TypeError(f"DictOfLoggedDict: expected set/list/tuple for exclusions: {exclusions}")

        self.current = dict()
        self.exclusions = exclusions or set()
        self.timestamp = gmtime()

    def __getitem__(self, item):
        return self.current.__getitem__(item)

    def __setitem__(self, k, v):
        currVal = self.current.get(k, LoggedDict(exclusions=self.exclusions))
        changes = currVal.update(v)

        self.current[k] = currVal
        return changes

    def get(self, key, default=None):
        return self.current.get(key, default)

    def update(self, newValues, timestamp=None):
        changeTime = timestamp or gmtime()
        result = []

        if not isinstance(newValues, dict):
            raise TypeError("LoggedDict.DictOfLoggedDict.update: expected dict")

        for k, v in newValues.items():
            currVal = self.current.get(k, LoggedDict(exclusions=self.exclusions))

            r1 = currVal.update(v, timestamp=changeTime)

            if r1:
                self.current[k] = currVal

            result.append(r1)

        return any(result)

    def purge(self, keys2delete, timestamp=None):
        changeTime = timestamp or gmtime()
        result = []

        for k in keys2delete:
            if k in self.exclusions:
                continue
            if k in self.current:
                r1 = self.current[k].clear(timestamp=changeTime)
                result.append(r1)

        return any(result)

    def addExclusion(self, *kargs):
        self.exclusions.update(set(kargs))

        for k in self.current:
            self.current[k].addExclusion(set(kargs))
        # TOTHINK: Qué hacer con los valores almacenados y que han quedado excluidos?

    def removeExclusion(self, *kargs):
        self.exclusions.remove(set(kargs).intersection(self.exclusions))

        for k in self.current:
            self.current[k].removeExclusion(set(kargs))

    def __len__(self):
        return len(self.current)
